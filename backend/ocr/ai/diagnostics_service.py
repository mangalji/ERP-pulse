"""AI-powered diagnostics for persisted NetSuite validation errors."""

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
                            "additionalProperties": False,
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
                "additionalProperties": False,
            },
        }
    },
    "required": ["diagnostics"],
    "additionalProperties": False,
}


NETSUITE_DIAGNOSTIC_PROMPT = """
You are a senior NetSuite Solution Architect and technical consultant
with decades of hands-on experience designing, implementing,
troubleshooting, and integrating NetSuite systems for complex businesses.

You specialize in NetSuite transaction processing, validation rules,
subsidiaries, items, vendors, accounting structures, SuiteScript, SuiteTalk,
REST APIs, SuiteQL, field mappings, and NetSuite business rules.

The application is trying to validate a business document before posting
it to NetSuite. The information below contains the actual validation
error(s) returned during that process.

Analyze the supplied information and, for every supplied error:

1. Explain what the error means in simple, practical terms.
2. Identify the most likely reasons for the error using only the supplied
   context and established NetSuite behavior.
3. Provide all materially relevant ways the user could resolve the issue.
4. When the context supports a clear preference, mark the most appropriate
   solution as recommended and explain why it is preferable.
5. Provide practical steps the user can follow in NetSuite or in the
   document/mapping configuration.
6. Distinguish confirmed facts from likely causes and assumptions.
7. Do not invent NetSuite configuration, relationships, permissions, or
   account-specific facts that were not supplied.
8. If the supplied information is insufficient to determine the exact cause,
   state what should be checked rather than guessing.
9. Do not recommend changing valid business data merely to bypass an error.
10. Do not claim that any change has already been made.
11. Your response will be shown directly to a non-technical business user.
    Use very simple, clear language and focus on what the user needs to know
    and do. Do not expose internal error codes, internal IDs, field IDs, API
    names, HTTP status codes, programming terms, database/server terms, raw
    provider messages, or implementation details.
12. Do not repeat the supplied raw error text verbatim. Translate it into a
    short, plain-language explanation.
13. Avoid unnecessary technical NetSuite terminology. When a NetSuite term is
    necessary, explain it in everyday business language.
14. Write solution steps as practical actions a normal business user can
    understand. If an administrator is required, say so clearly instead of
    giving low-level technical instructions.

Preserve each supplied error_reference exactly so the application can show
the diagnosis next to the corresponding validation error. The reference is
internal metadata and must never be mentioned to the user.

Return one diagnostic object for each supplied error. If multiple solutions
are materially valid, include all of them. Prefer one recommended solution
only when the context supports a defensible preference.

Actual NetSuite validation information:
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
    validation_results: list[OCRValidationResult],
) -> tuple[list[str], dict[str, Any]]:
    expected_references: list[str] = []
    validation_information: list[dict[str, Any]] = []

    for validation in validation_results:
        raw_errors = validation.errors if isinstance(validation.errors, list) else []
        errors = []

        for error_index, error in enumerate(raw_errors[:MAX_ERRORS_PER_RESULT]):
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

        raw_items = validation.items if isinstance(validation.items, list) else []
        items = []
        for item in raw_items[:MAX_ERRORS_PER_RESULT]:
            if not isinstance(item, Mapping):
                continue
            # The complete item object can be large. Keep the diagnostic
            # context useful while excluding unnecessary payload noise.
            items.append(
                _sanitize(
                    {
                        key: item.get(key)
                        for key in (
                            "extracted_name",
                            "line_index",
                            "matched",
                            "ambiguous",
                            "netsuite_id",
                            "item_subsidiary",
                            "transaction_subsidiary",
                            "transaction_subsidiary_id",
                        )
                        if key in item
                    }
                )
            )

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
        raise ValueError("AI diagnostic response was not an object.")

    raw_diagnostics = raw_response.get("diagnostics")
    if not isinstance(raw_diagnostics, list):
        raise ValueError("AI diagnostic response did not contain diagnostics.")

    expected_set = set(expected_references)
    by_reference: dict[str, dict[str, Any]] = {}

    for item in raw_diagnostics:
        if not isinstance(item, Mapping):
            continue

        reference = _safe_string(item.get("error_reference") or "").strip()
        if reference not in expected_set or reference in by_reference:
            continue

        solutions = []
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
                        "title": _safe_string(solution.get("title") or ""),
                        "steps": [
                            _safe_string(step)
                            for step in steps[:MAX_STEPS_PER_SOLUTION]
                        ],
                        "recommended": bool(solution.get("recommended")),
                        "reason": _safe_string(solution.get("reason") or ""),
                    }
                )

        diagnostic = {
            "error_reference": reference,
            "title": _safe_string(item.get("title") or "Something needs your attention"),
            "what_happened": _safe_string(item.get("what_happened") or ""),
            "likely_reasons": [
                _safe_string(reason)
                for reason in (item.get("likely_reasons") or [])[:10]
            ],
            "possible_solutions": solutions,
            "additional_checks": [
                _safe_string(check)
                for check in (item.get("additional_checks") or [])[:10]
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
            raise ValueError("No validation results were supplied.")

        if len(validation_ids) > MAX_VALIDATION_RESULTS:
            raise ValueError(
                f"A maximum of {MAX_VALIDATION_RESULTS} validation results can be analyzed at once."
            )

        normalized_ids = []
        for validation_id in validation_ids:
            try:
                normalized_id = str(UUID(str(validation_id)))
            except (ValueError, TypeError, AttributeError):
                raise ValueError("One or more validation results are invalid.")

            if normalized_id not in normalized_ids:
                normalized_ids.append(normalized_id)

        try:
            connection_uuid = UUID(str(connection_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("The NetSuite connection is invalid.")

        validations = list(
            OCRValidationResult.objects
            .filter(
                id__in=normalized_ids,
                connection_id=connection_uuid,
                document__company=company,
            )
            .select_related("document")
        )

        found_ids = {str(validation.id) for validation in validations}
        if found_ids != set(normalized_ids):
            raise ValueError(
                "One or more validation results are unavailable for this company or NetSuite connection."
            )

        expected_references, validation_information = _build_validation_information(
            validations
        )

        if not expected_references:
            return {
                "diagnostics": [],
                "validation_ids": normalized_ids,
                "count": 0,
            }

        provider = ai_configuration_service.resolve_provider(
            company=company
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
            "Generating NetSuite validation diagnostics — company=%s validations=%s errors=%s provider=%s model=%s",
            getattr(company, "id", None),
            len(normalized_ids),
            len(expected_references),
            getattr(provider, "__class__", type(provider)).__name__,
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
                "AI diagnostic response did not include every validation error."
            )

        return {
            "diagnostics": diagnostics,
            "validation_ids": normalized_ids,
            "count": len(diagnostics),
        }


net_suite_diagnostics_service = NetSuiteDiagnosticsService()
