"""AI-powered explanations for persisted NetSuite validation errors."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from ocr.ai.service import ai_configuration_service
from ocr.models import OCRValidationResult

logger = logging.getLogger(__name__)

DIAGNOSTICS_TIMEOUT = 18.0
MAX_VALIDATION_RESULTS = 50
MAX_ERRORS_PER_RESULT = 20
MAX_STRING_LENGTH = 3000
MAX_SOLUTIONS = 8
MAX_STEPS_PER_SOLUTION = 10

SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "client_secret",
    }
)

DIAGNOSTIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagnostics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "error_reference": {"type": "string"},
                    "title": {"type": "string"},
                    "what_happened": {"type": "string"},
                    "likely_reasons": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "possible_solutions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "steps": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "recommended": {"type": "boolean"},
                                "reason": {"type": "string"},
                            },
                            "required": [
                                "title",
                                "steps",
                                "recommended",
                                "reason",
                            ],
                            # "additionalProperties": False,
                        },
                    },
                    "additional_checks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "error_reference",
                    "title",
                    "what_happened",
                    "likely_reasons",
                    "possible_solutions",
                    "additional_checks",
                ],
                # "additionalProperties": False,
            },
        }
    },
    "required": ["diagnostics"],
    # "additionalProperties": False,
}


NETSUITE_DIAGNOSTIC_PROMPT = """
You are a senior NetSuite Solution Architect and technical consultant.

You are helping a non-technical business user understand why a Vendor Bill
failed validation before it could be posted to NetSuite.

The validation engine has ALREADY determined that the supplied validation
errors are real. Your job is only to explain those errors and provide
practical resolution guidance.

For every supplied validation error:

1. Explain what the error means in simple business language.
2. Explain the confirmed problem using the supplied data.
3. Identify likely reasons only when supported by the supplied context or
   well-established NetSuite behavior.
4. Provide all materially relevant ways to resolve the issue.
5. Give practical steps the user can follow.
6. Clearly distinguish confirmed facts from likely reasons.
7. Do not invent account-specific configuration, permissions, relationships,
   records, subsidiaries, field IDs, or other facts.
8. Do not claim that any change has already been made.
9. Do not suggest changing valid business data merely to bypass validation.
10. Do not tell the user that validation should have passed.
11. The response will be shown directly to a business user.
12. Do not expose internal error codes, internal IDs, field IDs, API names,
    HTTP status codes, programming terms, database/server details, or
    raw provider errors.
13. Do not repeat the raw validation message verbatim. Translate it into
    understandable language.
14. If the supplied information is insufficient to determine the exact cause,
    say what should be checked instead of guessing.
15. If an administrator is required, explicitly say that an administrator
    should perform the action.
16. Preserve error_reference exactly. It is internal metadata and must not
    be mentioned to the user.

Return one diagnostic object for every supplied validation error.

Validation information:
{{validation_information}}
"""


def _safe_string(value: Any) -> str:
    return str(value)[:MAX_STRING_LENGTH]


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[truncated]"

    if isinstance(value, str):
        return _safe_string(value)

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}

        for key, item in value.items():
            key_text = str(key)

            if key_text.lower() in SENSITIVE_KEYS:
                continue

            sanitized[key_text[:100]] = _sanitize(
                item,
                depth=depth + 1,
            )

        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [
            _sanitize(item, depth=depth + 1)
            for item in list(value)[:50]
        ]

    return _safe_string(value)


def _build_validation_information(
    validations: list[OCRValidationResult],
) -> tuple[list[str], dict[str, Any]]:
    expected_references: list[str] = []
    validation_information: list[dict[str, Any]] = []

    for validation in validations:
        raw_errors = (
            validation.errors
            if isinstance(validation.errors, list)
            else []
        )

        errors = []

        for error_index, error in enumerate(
            raw_errors[:MAX_ERRORS_PER_RESULT]
        ):
            reference = f"{validation.id}:{error_index}"

            expected_references.append(reference)

            errors.append(
                {
                    "error_reference": reference,
                    "error": _sanitize(error),
                }
            )

        if not errors:
            continue

        raw_items = (
            validation.items
            if isinstance(validation.items, list)
            else []
        )

        items = []

        for item in raw_items[:MAX_ERRORS_PER_RESULT]:
            if not isinstance(item, Mapping):
                continue

            relevant = {
                key: item.get(key)
                for key in (
                    "extracted_name",
                    "line_index",
                    "matched",
                    "ambiguous",
                    "netsuite_id",
                    "item_name",
                    "item_subsidiary",
                    "transaction_subsidiary",
                    "transaction_subsidiary_id",
                    "candidates",
                )
                if key in item
            }

            items.append(_sanitize(relevant))

        validation_information.append(
            {
                "validation_id": str(validation.id),
                "document_id": str(validation.document_id),
                "record_type": "vendor_bill",
                "vendor": {
                    "extracted_name": validation.vendor_extracted_name,
                    "matched": validation.vendor_matched,
                    "netsuite_id": validation.vendor_netsuite_id,
                },
                "errors": errors,
                "items": items,
            }
        )

    return expected_references, {
        "record_type": "vendor_bill",
        "validations": validation_information,
    }


def _normalize_diagnostics(
    raw_response: Any,
    *,
    expected_references: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(raw_response, Mapping):
        raise ValueError(
            "AI diagnostic response was not an object."
        )

    raw_diagnostics = raw_response.get("diagnostics")

    if not isinstance(raw_diagnostics, list):
        raise ValueError(
            "AI diagnostic response did not contain diagnostics."
        )

    expected_set = set(expected_references)
    by_reference: dict[str, dict[str, Any]] = {}

    for item in raw_diagnostics:
        if not isinstance(item, Mapping):
            continue

        reference = _safe_string(
            item.get("error_reference") or ""
        ).strip()

        if reference not in expected_set:
            continue

        if reference in by_reference:
            continue

        solutions: list[dict[str, Any]] = []

        raw_solutions = item.get("possible_solutions")

        if isinstance(raw_solutions, list):
            for solution in raw_solutions[:MAX_SOLUTIONS]:
                if not isinstance(solution, Mapping):
                    continue

                steps = solution.get("steps")

                if not isinstance(steps, list):
                    steps = []

                solutions.append(
                    {
                        "title": _safe_string(
                            solution.get("title") or ""
                        ),
                        "steps": [
                            _safe_string(step)
                            for step in steps[:MAX_STEPS_PER_SOLUTION]
                        ],
                        "recommended": bool(
                            solution.get("recommended")
                        ),
                        "reason": _safe_string(
                            solution.get("reason") or ""
                        ),
                    }
                )

        diagnostic = {
            "error_reference": reference,
            "title": _safe_string(
                item.get("title")
                or "Something needs your attention"
            ),
            "what_happened": _safe_string(
                item.get("what_happened") or ""
            ),
            "likely_reasons": [
                _safe_string(reason)
                for reason in (
                    item.get("likely_reasons") or []
                )[:10]
            ],
            "possible_solutions": solutions,
            "additional_checks": [
                _safe_string(check)
                for check in (
                    item.get("additional_checks") or []
                )[:10]
            ],
        }

        recommended_seen = False

        for solution in diagnostic["possible_solutions"]:
            if solution["recommended"]:
                if recommended_seen:
                    solution["recommended"] = False
                else:
                    recommended_seen = True

        by_reference[reference] = diagnostic

    return [
        by_reference[reference]
        for reference in expected_references
        if reference in by_reference
    ]


class NetSuiteDiagnosticsService:

    def diagnose(
        self,
        *,
        company,
        connection_id: str,
        validation_ids: list[str],
    ) -> dict[str, Any]:

        if not validation_ids:
            raise ValueError(
                "No validation results were supplied."
            )

        if len(validation_ids) > MAX_VALIDATION_RESULTS:
            raise ValueError(
                f"A maximum of {MAX_VALIDATION_RESULTS} "
                "validation results can be analyzed at once."
            )

        normalized_ids = []

        for validation_id in validation_ids:
            try:
                normalized_id = str(
                    UUID(str(validation_id))
                )
            except (
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:
                raise ValueError(
                    "One or more validation results are invalid."
                ) from exc

            if normalized_id not in normalized_ids:
                normalized_ids.append(normalized_id)

        try:
            connection_uuid = UUID(str(connection_id))
        except (
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            raise ValueError(
                "The NetSuite connection is invalid."
            ) from exc

        validations = list(
            OCRValidationResult.objects
            .filter(
                id__in=normalized_ids,
                connection_id=connection_uuid,
                document__company=company,
            )
            .select_related("document")
        )

        found_ids = {
            str(validation.id)
            for validation in validations
        }

        if found_ids != set(normalized_ids):
            raise ValueError(
                "One or more validation results are unavailable "
                "for this company or NetSuite connection."
            )

        expected_references, validation_information = (
            _build_validation_information(validations)
        )

        if not expected_references:
            return {
                "diagnostics": [],
                "validation_ids": normalized_ids,
                "count": 0,
            }

        provider = (
            ai_configuration_service.resolve_provider(
                company=company
            )
        )

        prompt = NETSUITE_DIAGNOSTIC_PROMPT.replace(
            "{{validation_information}}",
            json.dumps(
                validation_information,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

        logger.info(
            "Generating NetSuite validation diagnostics — "
            "company=%s validations=%s errors=%s provider=%s model=%s",
            getattr(company, "id", None),
            len(normalized_ids),
            len(expected_references),
            getattr(
                provider,
                "__class__",
                type(provider),
            ).__name__,
            getattr(provider, "model", None),
        )

        raw_response = provider.generate_structured_json(
            prompt=prompt,
            schema=DIAGNOSTIC_SCHEMA,
            timeout=DIAGNOSTICS_TIMEOUT,
        )

        diagnostics = _normalize_diagnostics(
            raw_response,
            expected_references=expected_references,
        )

        if len(diagnostics) != len(expected_references):
            raise ValueError(
                "AI diagnostic response did not include "
                "every validation error."
            )

        return {
            "diagnostics": diagnostics,
            "validation_ids": normalized_ids,
            "count": len(diagnostics),
        }


net_suite_diagnostics_service = NetSuiteDiagnosticsService()