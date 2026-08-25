"""
Notebook-compatible Gemini document extraction service.

This service ports the extraction logic from the approved Colab prototype
into the AGSuite ERP application without changing the existing OCR upload
storage layer or the asynchronous IDP pipeline.

Step 1 scope:
    PDF/image -> Gemini -> structured JSON

NetSuite mapping/posting, Excel generation, Celery, and the existing
OpenCV preprocessing pipeline are intentionally outside this service.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings

from ocr.exceptions import (
    GeminiConnectionException,
    GeminiRateLimitException,
    GeminiTimeoutException,
    GeminiValidationException,
)
from ocr.utils import logger


MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

FIELD_DESCRIPTIONS = {
    "invoice_number": "The invoice or document number/ID",
    "invoice_date": "Invoice date, format YYYY-MM-DD if possible",
    "due_date": "Payment due date, format YYYY-MM-DD if possible",
    "vendor_name": "Name of the vendor/supplier issuing the invoice",
    "customer_name": "Name of the customer/bill-to party",
    "subsidiary": "Company subsidiary or business unit, if mentioned",
    "currency": "3-letter currency code, e.g. USD, INR, EUR",
    "subtotal": "Subtotal amount before tax (number only, no currency symbol)",
    "tax_amount": "Total tax amount (number only)",
    "tax_rate": "Tax rate as a percentage if stated, e.g. 18 for 18%",
    "total_amount": "Grand total / amount due (number only)",
    "payment_terms": "Payment terms if stated, e.g. Net 30",
}

LINE_ITEM_FIELDS = {
    "description": "Item / service description",
    "quantity": "Quantity (number only)",
    "unit_price": "Price per unit (number only)",
    "amount": "Line item total amount (number only)",
}

# Human-readable labels for the standard fields, used by the dynamic
# extraction configuration UI (Phase 2) and by the API field catalogue.
FIELD_LABELS = {
    "invoice_number": "Invoice Number",
    "invoice_date": "Invoice Date",
    "due_date": "Due Date",
    "vendor_name": "Vendor Name",
    "customer_name": "Customer Name",
    "subsidiary": "Subsidiary",
    "currency": "Currency",
    "subtotal": "Subtotal",
    "tax_amount": "Tax Amount",
    "tax_rate": "Tax Rate (%)",
    "total_amount": "Total Amount",
    "payment_terms": "Payment Terms",
}

LINE_ITEM_LABELS = {
    "description": "Description",
    "quantity": "Quantity",
    "unit_price": "Unit Price",
    "amount": "Amount",
}

# Custom-field datatype vocabulary (Phase 2). This metadata is preserved
# end-to-end so the safe JSON representation never loses the intended type:
# the schema uses an appropriate JSON type, the prompt carries formatting
# instructions, and the field config (requested_fields_json /
# OCRExtractionTemplate.fields_config) stores the original datatype.
VALID_DATA_TYPES = frozenset({"text", "number", "date", "boolean", "currency"})


def _normalize_text(value: Any) -> Any:
    """Normalize a text value to a stripped string or None."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value.strip() or None
    return str(value).strip() or None


def _try_numeric(cleaned: str) -> int | float | None:
    """Helper to parse a numeric string."""
    try:
        if "." in cleaned:
            return float(cleaned)
        return int(cleaned)
    except (ValueError, TypeError):
        return None


def _normalize_number(value: Any) -> Any:
    """Normalize a number value to int/float or None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "").replace(",", "")
        return _try_numeric(cleaned)
    return None


def _normalize_currency(value: Any) -> Any:
    """Normalize a currency value to a numeric amount or None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 2)
    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace(",", "")
            .replace("₹", "")
            .replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .replace("%", "")
        )
        try:
            return round(float(cleaned), 2)
        except (ValueError, TypeError):
            return None
    return None


def _normalize_boolean(value: Any) -> Any:
    """Normalize a boolean value or None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _normalize_date(value: Any) -> Any:
    """
    Normalize a date value to ISO YYYY-MM-DD or None.

    Only unambiguous year-first formats are accepted:
    - YYYY-MM-DD (ISO)
    - YYYY/MM/DD (year-first with slashes)

    Ambiguous formats like DD/MM/YYYY or MM/DD/YYYY are rejected
    because there is no reliable context to determine the intended
    interpretation.
    """
    if isinstance(value, str):
        text = value.strip()
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            try:
                datetime.strptime(text, '%Y-%m-%d')
                return text
            except ValueError:
                return None
        if re.match(r'^\d{4}/\d{2}/\d{2}$', text):
            try:
                datetime.strptime(text, '%Y/%m/%d')
                parts = text.split('/')
                return f"{parts[0]}-{parts[1]}-{parts[2]}"
            except ValueError:
                return None
    return None


def _coerce_data_type(value: Any) -> str:
    """
    Validate and normalize a datatype string.

    Raises ValueError for unsupported or missing datatypes instead of
    silently falling back to "text". This ensures invalid configurations
    are rejected early with a clear error message.
    """
    data_type = str(value or "").strip().lower()
    if not data_type:
        raise ValueError("Datatype is required.")
    if data_type not in VALID_DATA_TYPES:
        raise ValueError(
            f"Invalid datatype '{data_type}'. "
            f"Supported datatypes: {', '.join(sorted(VALID_DATA_TYPES))}."
        )
    return data_type


# Central authoritative datatype registry. Every supported datatype is
# described in exactly one place here. The same registry is used for:
#   - JSON schema type selection
#   - Prompt format hints
#   - Server-side value normalization
#   - Configuration validation
DATATYPE_REGISTRY: dict[str, dict[str, Any]] = {
    "text": {
        "json_schema_type": "string",
        "prompt_hint": "",
        "normalize": _normalize_text,
    },
    "number": {
        "json_schema_type": "number",
        "prompt_hint": " Return a plain number (no currency symbol or thousands separators).",
        "normalize": _normalize_number,
    },
    "date": {
        "json_schema_type": "string",
        "prompt_hint": " Return as an ISO YYYY-MM-DD string.",
        "normalize": _normalize_date,
    },
    "boolean": {
        "json_schema_type": "boolean",
        "prompt_hint": " Return true or false only.",
        "normalize": _normalize_boolean,
    },
    "currency": {
        "json_schema_type": "number",
        "prompt_hint": " Return the numeric amount only (no currency symbol or code).",
        "normalize": _normalize_currency,
    },
}

# Declared datatype for each standard header/line field. Custom fields
# declare their own datatype in the configuration.
FIELD_DATA_TYPES = {
    "invoice_number": "text",
    "invoice_date": "date",
    "due_date": "date",
    "vendor_name": "text",
    "customer_name": "text",
    "subsidiary": "text",
    "currency": "text",
    "subtotal": "number",
    "tax_amount": "number",
    "tax_rate": "number",
    "total_amount": "number",
    "payment_terms": "text",
}

LINE_ITEM_DATA_TYPES = {
    "description": "text",
    "quantity": "number",
    "unit_price": "number",
    "amount": "currency",
}


def _json_schema_type(
    data_type: str,
    *,
    key: str | None = None,
    is_line_field: bool = False,
) -> str:
    """
    Gemini structured-output JSON type for a declared datatype.

    Standard numeric fields keep the exact ``number`` type used by the
    static ``EXTRACTION_SCHEMA`` (subtotal/tax_amount/tax_rate/total_amount
    and quantity/unit_price/amount) so the default (no dynamic config)
    extraction path is byte-for-byte unchanged. A custom field's JSON type
    follows its declared datatype via the central registry: number -> number,
    boolean -> boolean, currency -> number, text/date -> string. The original
    *logical* datatype (date, currency, ...) is carried separately in the
    field config so it is never lost.
    """
    numeric_set = _NUMERIC_LINE_FIELDS if is_line_field else _NUMERIC_STANDARD_FIELDS
    if key in numeric_set:
        return "number"
    registry_entry = DATATYPE_REGISTRY.get(data_type)
    if registry_entry:
        return registry_entry["json_schema_type"]
    return "string"


def _type_format_hint(data_type: str) -> str:
    """Prompt fragment instructing Gemini how to render a datatype."""
    registry_entry = DATATYPE_REGISTRY.get(data_type)
    if registry_entry:
        return registry_entry["prompt_hint"]
    return ""


def _normalize_datatype(value: Any, data_type: str) -> Any:
    """
    Server-side type normalization for an extracted field value.

    Never raises on a single bad value — an invalid individual field
    becomes None and extraction continues. This is critical for future
    custom fields where the AI may return a value in an unexpected format.

    Mapping:
      text     -> str (or None)
      number   -> int/float (or None)
      date     -> ISO YYYY-MM-DD str (or None)
      boolean  -> bool (or None)
      currency -> int/float (or None)
    """
    if value is None or value == "":
        return None

    try:
        normalized_type = _coerce_data_type(data_type)
    except ValueError:
        return None

    registry_entry = DATATYPE_REGISTRY.get(normalized_type)
    if registry_entry and "normalize" in registry_entry:
        return registry_entry["normalize"](value)

    return value


def _apply_datatype_normalization(
    result: dict[str, Any],
    header_types: dict[str, str],
    line_types: dict[str, str],
    line_keys: tuple[str, ...],
) -> dict[str, Any]:
    """
    Apply server-side datatype normalization to the extraction result.

    Never throws on a single bad value — an invalid individual field
    becomes None and extraction continues. Custom fields are handled
    generically from the resolved field config.
    """
    normalized = dict(result)

    for key, data_type in header_types.items():
        if key in normalized:
            normalized[key] = _normalize_datatype(normalized[key], data_type)

    raw_items = normalized.get("line_items")
    if isinstance(raw_items, list) and line_keys:
        normalized_items = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                normalized_items.append(raw_item)
                continue
            cleaned = dict(raw_item)
            for key in line_keys:
                if key in cleaned:
                    cleaned[key] = _normalize_datatype(
                        cleaned[key], line_types.get(key, "text")
                    )
            normalized_items.append(cleaned)
        normalized["line_items"] = normalized_items

    return normalized


def get_standard_field_catalog() -> dict[str, Any]:
    """
    Catalogue of the standard extraction fields for the dynamic
    configuration UI (Phase 2). Returns header and line field descriptors
    with their labels and declared datatypes.
    """
    return {
        "header_fields": [
            {
                "key": key,
                "label": FIELD_LABELS.get(key, key),
                "data_type": FIELD_DATA_TYPES.get(key, "text"),
            }
            for key in FIELD_DESCRIPTIONS
        ],
        "line_fields": [
            {
                "key": key,
                "label": LINE_ITEM_LABELS.get(key, key),
                "data_type": LINE_ITEM_DATA_TYPES.get(key, "text"),
            }
            for key in LINE_ITEM_FIELDS
        ],
        "supports_line_items": True,
    }


def _slugify_field_key(label: str) -> str:
    """Turn an arbitrary custom-field label into a safe JSON key."""
    slug = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    return slug or "custom_field"


# Dynamic extraction configuration (Phase 2 — see OCRBatch.requested_fields_json
# and OCRExtractionTemplate). A caller can select a subset of the standard
# fields below, drop line_items entirely, and/or add custom fields with an
# AI description/instruction and a header-or-line scope.
#
# requested_fields shape:
#   {
#     "standard_fields": ["invoice_number", ..., "line_items"],
#     "custom_fields": [
#       {"key": "po_number", "label": "Purchase Order Number",
#        "description": "The PO/reference number on this invoice.",
#        "scope": "header"},
#       {"key": "batch_number", "label": "Batch Number",
#        "description": "Manufacturing/lot batch number for this line.",
#        "scope": "line"},
#     ],
#   }
def resolve_field_config(
    requested_fields: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str], bool, dict[str, str], dict[str, str]]:
    """
    Resolve a (possibly partial/absent) dynamic extraction configuration.

    Falling back to the exact existing default field set — every standard
    header field plus line_items — whenever requested_fields is falsy or
    malformed is intentional: this is what makes every existing caller
    that does not pass requested_fields behave exactly as before.

    Returns
    -------
    (header_fields, line_fields, include_line_items, header_types,
     line_types) where header_fields/line_fields map field key -> AI
    instruction/description and header_types/line_types map field key ->
    declared datatype ("text" / "number" / "date" / "boolean" /
    "currency").

    Raises
    ------
    ValueError
        If a line-scoped custom field is configured while line_items
        extraction is disabled — that combination is invalid and must not
        be silently accepted (see Phase 2 rule).
        If an explicit (non-empty) configuration requests nothing — i.e.
        both standard_fields and custom_fields are empty — it is rejected
        rather than silently upgraded to the full default set. An absent
        or empty ``{}`` config remains the legacy default-extraction
        signal and is handled by the caller.
        If a custom field's key collides with a standard/custom field it
        is rejected with a clear error instead of being silently dropped.
    """
    # An absent or empty ``{}`` config is the legacy "use defaults" signal
    # (handled here and by callers). A *non-empty* config that requests
    # nothing explicitly is invalid and must not be silently coerced into
    # the full default field set.
    if not isinstance(requested_fields, dict) or not requested_fields:
        return (
            dict(FIELD_DESCRIPTIONS),
            dict(LINE_ITEM_FIELDS),
            True,
            dict(FIELD_DATA_TYPES),
            dict(LINE_ITEM_DATA_TYPES),
        )

    selected_standard = requested_fields.get("standard_fields")
    custom_fields = requested_fields.get("custom_fields") or []
    if (not isinstance(selected_standard, list) or not selected_standard) and not custom_fields:
        raise ValueError(
            "Extraction configuration must include at least one standard "
            "field or one custom field."
        )

    if not isinstance(selected_standard, list) or not selected_standard:
        selected_standard = list(FIELD_DESCRIPTIONS.keys()) + ["line_items"]

    include_line_items = "line_items" in selected_standard

    header_fields = {
        key: description
        for key, description in FIELD_DESCRIPTIONS.items()
        if key in selected_standard
    }
    line_fields = dict(LINE_ITEM_FIELDS) if include_line_items else {}
    header_types = {
        key: FIELD_DATA_TYPES.get(key, "text") for key in header_fields
    }
    line_types = {
        key: LINE_ITEM_DATA_TYPES.get(key, "text") for key in line_fields
    }

    reserved_keys = frozenset(FIELD_DESCRIPTIONS) | {"line_items"} | frozenset(LINE_ITEM_FIELDS)
    seen_keys = set(header_fields) | set(line_fields)

    for idx, custom in enumerate(requested_fields.get("custom_fields") or []):
        if not isinstance(custom, dict):
            raise ValueError(
                f"custom_fields[{idx}] must be a dict, "
                f"got {type(custom).__name__}"
            )

        label = str(custom.get("label") or custom.get("key") or "").strip()
        if not label:
            raise ValueError(
                f"custom_fields[{idx}] must have a non-empty label or key"
            )

        key = _slugify_field_key(str(custom.get("key") or label))

        if key in reserved_keys:
            raise ValueError(
                f"Custom field '{label}' conflicts with a standard field "
                f"name ('{key}'). Use a different label."
            )
        if key in seen_keys:
            raise ValueError(
                f"Duplicate custom field '{label}' (resolved key '{key}'). "
                "Each custom field must have a unique label."
            )

        description = str(custom.get("description") or label).strip()
        data_type = _coerce_data_type(custom.get("data_type"))
        scope = "line" if custom.get("scope") == "line" else "header"

        if scope == "line":
            if not include_line_items:
                # A line-level custom field is meaningless without
                # line_items extraction enabled — reject the configuration
                # outright rather than dropping the field silently.
                raise ValueError(
                    f"Custom line-item field '{label}' requires line_items "
                    "extraction to be enabled."
                )
            line_fields[key] = description
            line_types[key] = data_type
        else:
            header_fields[key] = description
            header_types[key] = data_type

        seen_keys.add(key)

    if not header_fields and not include_line_items:
        # Never send Gemini an empty contract — fall back to the safe
        # default rather than extracting nothing at all.
        return (
            dict(FIELD_DESCRIPTIONS),
            dict(LINE_ITEM_FIELDS),
            True,
            dict(FIELD_DATA_TYPES),
            dict(LINE_ITEM_DATA_TYPES),
        )

    return header_fields, line_fields, include_line_items, header_types, line_types


_NUMERIC_STANDARD_FIELDS = frozenset({"subtotal", "tax_amount", "tax_rate", "total_amount"})
_NUMERIC_LINE_FIELDS = frozenset({"quantity", "unit_price", "amount"})


def _field_json_type(key: str, *, is_line_field: bool) -> str:
    """
    JSON schema type for one field.

    Standard numeric fields keep their existing number type. Every custom
    field defaults to string — full NetSuite-side type inference (date,
    boolean, currency, etc.) is a Phase 4 custom-field-creation concern,
    not an OCR-extraction-contract concern, and a string is always a safe,
    lossless container for whatever Gemini reads off the document.
    """
    numeric_set = _NUMERIC_LINE_FIELDS if is_line_field else _NUMERIC_STANDARD_FIELDS
    return "number" if key in numeric_set else "string"


# Canonical output contract used by the AGSuite ERP OCR feature.
# This is intentionally the same contract used by the approved notebook.
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "invoice_number": {"type": "string", "nullable": True},
        "invoice_date": {"type": "string", "nullable": True},
        "due_date": {"type": "string", "nullable": True},
        "vendor_name": {"type": "string", "nullable": True},
        "customer_name": {"type": "string", "nullable": True},
        "subsidiary": {"type": "string", "nullable": True},
        "currency": {"type": "string", "nullable": True},
        "subtotal": {"type": "number", "nullable": True},
        "tax_amount": {"type": "number", "nullable": True},
        "tax_rate": {"type": "number", "nullable": True},
        "total_amount": {"type": "number", "nullable": True},
        "payment_terms": {"type": "string", "nullable": True},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "nullable": True},
                    "quantity": {"type": "number", "nullable": True},
                    "unit_price": {"type": "number", "nullable": True},
                    "amount": {"type": "number", "nullable": True},
                },
                "required": [
                    "description",
                    "quantity",
                    "unit_price",
                    "amount",
                ],
            },
        },
    },
    "required": [
        "invoice_number",
        "invoice_date",
        "due_date",
        "vendor_name",
        "customer_name",
        "subsidiary",
        "currency",
        "subtotal",
        "tax_amount",
        "tax_rate",
        "total_amount",
        "payment_terms",
        "line_items",
    ],
    
}

TOP_LEVEL_FIELDS = tuple(FIELD_DESCRIPTIONS.keys())
LINE_ITEM_OUTPUT_FIELDS = tuple(LINE_ITEM_FIELDS.keys())

# These fields are high-value signals for a bad extraction. A null here does
# not automatically mean the field exists, but it triggers a verification pass
# so the model must explicitly re-check the document.
VERIFICATION_FIELDS = (
    "invoice_number",
    "invoice_date",
    "vendor_name",
    "currency",
    "subtotal",
    "total_amount",
)

VERIFICATION_PROMPT_TEMPLATE = """You are the verification and correction stage of an
accounting document extraction system.

Re-read the attached document in full.

PROPOSED EXTRACTION:
{primary_json}

Return ONLY this JSON structure:
{{
  "needs_correction": true or false,
  "corrections": [
    {{
      "field": "top-level field name or line_items",
      "reason": "brief reason based on visible document evidence",
      "corrected_value": "corrected value"
    }}
  ]
}}

Rules:
- A null field is acceptable ONLY when the requested value is genuinely absent
  or cannot be reliably determined from the document.
- If the value is visibly present anywhere in the document and the proposed
  extraction returned null, report a correction.
- Re-check all visible top-level fields, including header, company/entity,
  metadata, table, memo, account and total sections.
- Re-check every clearly separated line-item/source row.
- If the proposed line_items list is missing, merged, or incomplete, report
  one correction for "line_items" containing the COMPLETE corrected array.
- Preserve source-row order and complete descriptions.
- Do not invent values.
- Do not report a correction merely because an equivalent non-null value is
  formatted differently.
- If the proposed extraction is correct, return:
  {{
    "needs_correction": false,
    "corrections": []
  }}
"""


AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "needs_correction": {"type": "boolean"},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "reason": {"type": "string"},
                    "corrected_value": {},
                },
                "required": [
                    "field",
                    "reason",
                    "corrected_value",
                ],
                
            },
        },
    },
    "required": [
        "needs_correction",
        "corrections",
    ],
    
}


def _build_schema(
    header_fields: dict[str, str],
    line_fields: dict[str, str],
    include_line_items: bool,
    header_types: dict[str, str] | None = None,
    line_types: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build a Gemini response_schema from a resolved field configuration.

    Structurally identical to the static EXTRACTION_SCHEMA below when
    given the full default field set — same properties, same required
    list, same nested line_items object — so the default (no dynamic
    configuration) extraction path is unaffected.

    Custom fields carry their declared datatype via header_types /
    line_types so the schema uses the appropriate JSON primitive (number
    vs string vs boolean) without losing the logical type.
    """
    header_types = header_types or {}
    line_types = line_types or {}

    properties: dict[str, Any] = {
        key: {
            "type": _json_schema_type(header_types.get(key, "text"), key=key, is_line_field=False),
            "nullable": True,
        }
        for key in header_fields
    }
    required = list(header_fields.keys())

    if include_line_items:
        line_properties = {
            key: {
                "type": _json_schema_type(line_types.get(key, "text"), key=key, is_line_field=True),
                "nullable": True,
            }
            for key in line_fields
        }
        properties["line_items"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": line_properties,
                "required": list(line_fields.keys()),
            },
        }
        required.append("line_items")

    return {"type": "object", "properties": properties, "required": required}


def _json_object_schema() -> dict[str, Any]:
    return EXTRACTION_SCHEMA


def _audit_schema() -> dict[str, Any]:
    return AUDIT_SCHEMA


def _normalize_result(
    data: dict[str, Any],
    header_keys: tuple[str, ...] | None = None,
    line_keys: tuple[str, ...] | None = None,
    include_line_items: bool = True,
) -> dict[str, Any]:
    """
    Normalize the model response to the output contract.

    Missing top-level keys are explicitly represented as None and line_items
    is always a list (when requested). This keeps the API/DB contract stable
    without inventing any values.

    header_keys/line_keys default to the static TOP_LEVEL_FIELDS/
    LINE_ITEM_OUTPUT_FIELDS — every existing call site that doesn't pass a
    dynamic field configuration keeps behaving exactly as before.
    """
    resolved_header_keys = header_keys if header_keys is not None else TOP_LEVEL_FIELDS
    resolved_line_keys = line_keys if line_keys is not None else LINE_ITEM_OUTPUT_FIELDS

    normalized = {
        key: data.get(key)
        for key in resolved_header_keys
    }

    if not include_line_items:
        return normalized

    raw_items = data.get("line_items")
    normalized_items = []

    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue

            normalized_items.append(
                {
                    key: raw_item.get(key)
                    for key in resolved_line_keys
                }
            )

    normalized["line_items"] = normalized_items
    return normalized


def _verification_is_needed(
    data: dict[str, Any],
    header_keys: tuple[str, ...] | None = None,
) -> bool:
    """
    Decide whether the first extraction deserves a second verification pass.

    High-value missing fields always trigger verification. A non-empty
    line-item set also triggers verification because missing/merged rows were
    an observed failure mode in the supplied test documents.

    header_keys, when given, restricts the high-value field check to fields
    the caller actually requested — a standard field the user deliberately
    removed from a dynamic configuration should never force an unnecessary
    verification pass. Defaults to checking every VERIFICATION_FIELDS entry,
    exactly as before, when no dynamic configuration is in play.
    """
    fields_to_check = VERIFICATION_FIELDS
    if header_keys is not None:
        fields_to_check = tuple(f for f in VERIFICATION_FIELDS if f in header_keys)

    if any(data.get(field) is None for field in fields_to_check):
        return True

    if data.get("line_items"):
        return True

    return False


_OVERWRITABLE_TEXTUAL_STANDARD_FIELDS = frozenset({
    "invoice_number", "invoice_date", "due_date",
    "vendor_name", "customer_name", "subsidiary",
    "currency", "payment_terms",
})


def _merge_corrected_result(
    candidate: dict[str, Any],
    audit: dict[str, Any],
    header_keys: tuple[str, ...] | None = None,
    line_keys: tuple[str, ...] | None = None,
    include_line_items: bool = True,
) -> dict[str, Any]:
    """
    Apply only evidence-backed corrections.

    A verifier is never allowed to erase a non-null primary value merely by
    returning null. Scalar corrections are applied when the primary value is
    null. Line items are replaced only when the verifier found a larger or
    clearly corrected row set; individual missing fields in line items are
    filled from the verifier when the primary field is null.

    header_keys/line_keys default to the static field sets, exactly as
    before, when no dynamic configuration is passed. When a dynamic
    configuration IS passed, every _normalize_result call below must also
    receive it — otherwise a reduced/custom field set would silently get
    reinflated back to the full default set on every merge, which would
    corrupt the intended dynamic contract.
    """
    resolved_header_keys = header_keys if header_keys is not None else TOP_LEVEL_FIELDS
    resolved_line_keys = line_keys if line_keys is not None else LINE_ITEM_OUTPUT_FIELDS

    merged = _normalize_result(
        candidate, resolved_header_keys, resolved_line_keys, include_line_items,
    )

    if not isinstance(audit, dict) or not audit.get("needs_correction"):
        return merged

    corrections = audit.get("corrections")
    if not isinstance(corrections, list):
        return merged

    for correction in corrections:
        if not isinstance(correction, dict):
            continue

        field = correction.get("field")
        corrected_value = correction.get("corrected_value")

        if field in resolved_header_keys:
            # Primary non-null values are retained unless the verifier can
            # provide a concrete replacement. A null verifier value is never
            # allowed to destroy a concrete primary value.
            if merged.get(field) is None and corrected_value is not None:
                merged[field] = corrected_value
            elif (
                merged.get(field) is not None
                and corrected_value is not None
                and field in _OVERWRITABLE_TEXTUAL_STANDARD_FIELDS
            ):
                # For known textual/date standard fields, a concrete
                # verifier correction can replace the primary only when
                # explicitly reported. Numeric fields and custom fields
                # (unknown type) remain conservative, fill-if-null only.
                merged[field] = corrected_value

        elif field == "line_items" and include_line_items and isinstance(corrected_value, list):
            candidate_items = merged.get("line_items") or []

            # Prefer the verifier when it found more source rows.
            if len(corrected_value) > len(candidate_items):
                merged["line_items"] = _normalize_result(
                    {"line_items": corrected_value},
                    resolved_header_keys,
                    resolved_line_keys,
                    include_line_items,
                )["line_items"]
                continue

            # Otherwise fill missing fields and prefer longer descriptions.
            if len(corrected_value) == len(candidate_items):
                merged_items = []
                for index, candidate_item in enumerate(candidate_items):
                    verifier_item = corrected_value[index]
                    merged_item = dict(candidate_item)

                    for key in resolved_line_keys:
                        candidate_value = merged_item.get(key)
                        verifier_value = (
                            verifier_item.get(key)
                            if isinstance(verifier_item, dict)
                            else None
                        )

                        if candidate_value is None and verifier_value is not None:
                            merged_item[key] = verifier_value
                        elif (
                            key == "description"
                            and isinstance(candidate_value, str)
                            and isinstance(verifier_value, str)
                            and len(verifier_value) > len(candidate_value)
                        ):
                            merged_item[key] = verifier_value

                    merged_items.append(merged_item)

                merged["line_items"] = merged_items

    return _normalize_result(
        merged, resolved_header_keys, resolved_line_keys, include_line_items,
    )


def build_prompt(
    header_fields: dict[str, str] | None = None,
    line_fields: dict[str, str] | None = None,
    include_line_items: bool = True,
    header_types: dict[str, str] | None = None,
    line_types: dict[str, str] | None = None,
) -> str:
    """
    Build the extraction prompt from a resolved field configuration.

    Defaults to the full standard field set — identical to the original,
    static prompt text — so EXTRACTION_PROMPT below is unaffected. A
    dynamic configuration (Phase 2) passes its own header_fields/
    line_fields/include_line_items and, optionally, the declared datatype
    of each field so formatting instructions can be embedded for custom
    fields and non-default types.
    """
    resolved_header_fields = header_fields if header_fields is not None else FIELD_DESCRIPTIONS
    resolved_line_fields = line_fields if line_fields is not None else LINE_ITEM_FIELDS
    resolved_header_types = header_types or {}
    resolved_line_types = line_types or {}

    field_lines = "\n".join(
        f'- "{key}": {description}{_type_format_hint(resolved_header_types.get(key, "text"))}'
        for key, description in resolved_header_fields.items()
    )

    if include_line_items:
        item_lines = "\n".join(
            f'  - "{key}": {description}{_type_format_hint(resolved_line_types.get(key, "text"))}'
            for key, description in resolved_line_fields.items()
        )
        line_items_section = f"""
Line-item fields:
{item_lines}
"""
        line_item_rules = """- For line_items, extract EVERY clearly separated source row.
- Preserve source-row order.
- Never merge, collapse, skip, or summarize separate rows.
- Preserve the COMPLETE visible row information in description.
- Do not shorten or paraphrase descriptions.
- Before finalizing, recount source rows and compare that count with line_items.
- Keep line_items=[] only when no clearly separated source rows exist."""
    else:
        line_items_section = ""
        line_item_rules = (
            "- This extraction does not request line items. Do not include "
            "a line_items field in the response."
        )

    return f"""You are the PRIMARY extraction stage of a production accounting document extraction system.
Read the attached document in full. The document may be an invoice, receipt, purchase order,
payment voucher, journal voucher, bank transfer voucher, credit note, debit note, or another
business document. Layouts vary widely.

Top-level fields:
{field_lines}
{line_items_section}
Rules:
- Respond with ONLY one valid JSON object.
- Use EXACTLY the requested field names and structure.
- NEVER invent or guess a value.
- Use null ONLY when the requested value is genuinely absent or cannot be determined
  from the document after inspecting the entire document.
- Do not return null merely because the value is in a different section, table, metadata area,
  footer, memo, account row, or company/entity block.
- Inspect the entire document before deciding a field is null.
- Numbers must be plain JSON numbers.
{line_item_rules}
- Before finalizing, re-scan the document once more for top-level fields that are still null.
- The output contract must remain exactly the same.
"""

EXTRACTION_PROMPT = build_prompt()

def parse_json_response(text: str) -> dict:
    """Parse Gemini's JSON response, tolerating accidental fences/extra text."""
    if not isinstance(text, str) or not text.strip():
        raise GeminiValidationException("Gemini returned an empty response.")

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiValidationException(
            f"Failed to parse Gemini response as JSON: {exc}"
        ) from exc

    if not isinstance(result, dict):
        raise GeminiValidationException("Gemini response is not a JSON object.")

    return result


class NotebookGeminiExtractor:
    """Gemini extractor implementing the approved notebook's core logic."""

    def __init__(self) -> None:
        self.model = getattr(
            settings,
            "OCR_GEMINI_MODEL",
            "gemini-2.5-flash",
        )
        self.timeout = getattr(settings, "OCR_TIMEOUT", 180)
        self.max_retries = getattr(settings, "OCR_MAX_RETRIES", 3)
        self.retry_delay = getattr(settings, "OCR_RETRY_DELAY", 1.0)
        self._genai = None

    def _get_genai(self):
        if self._genai is None:
            try:
                from google import genai
            except ImportError as exc:
                raise GeminiConnectionException(
                    "google-genai is not installed. "
                    "Run: pip install google-genai"
                ) from exc
            self._genai = genai
        return self._genai

    def extract(
        self,
        file_path: str | Path,
        mime_type: str | None = None,
        requested_fields: dict[str, Any] | None = None,
    ) -> dict:
        """
        Read the original file bytes and extract structured JSON with Gemini.

        requested_fields, when given, is the dynamic extraction
        configuration (Phase 2) — a subset of standard fields plus any
        custom fields with their own AI description and header/line scope.
        Omitting it (the default) extracts the full standard field set,
        exactly as before.
        """
        (
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
        ) = resolve_field_config(requested_fields)
        header_keys = tuple(header_fields.keys())
        line_keys = tuple(line_fields.keys())
        schema = _build_schema(
            header_fields, line_fields, include_line_items, header_types, line_types
        )
        prompt = build_prompt(
            header_fields, line_fields, include_line_items, header_types, line_types
        )

        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise GeminiConnectionException(f"OCR source file not found: {path}")

        extension = path.suffix.lower()
        media_type = mime_type or MEDIA_TYPES.get(extension)
        if media_type not in MEDIA_TYPES.values():
            raise GeminiValidationException(
                f"Unsupported OCR file type: {extension or media_type}"
            )

        try:
            file_bytes = path.read_bytes()
        except OSError as exc:
            raise GeminiConnectionException(
                f"Unable to read OCR source file: {exc}"
            ) from exc

        if not file_bytes:
            raise GeminiValidationException("Uploaded file is empty.")

        request_id = uuid.uuid4().hex[:8]
        logger.info(
            "Notebook Gemini extraction started — request_id=%s file=%s model=%s",
            request_id,
            path.name,
            self.model,
        )

        genai = self._get_genai()
        client = self._create_client(genai)
        file_part = genai.types.Part.from_bytes(
            data=file_bytes,
            mime_type=media_type,
        )

        last_exception: Exception | None = None
        start = time.perf_counter()

        # Same retry shape as the supplied notebook: 3 retries + initial call.
        for attempt in range(self.max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=[file_part, prompt],
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0,
                        seed=42,
                    ),
                )

                response_text = getattr(response, "text", None)
                result = _normalize_result(
                    parse_json_response(response_text or ""),
                    header_keys,
                    line_keys,
                    include_line_items,
                )
                if _verification_is_needed(result, header_keys):
                    audit = self._verify_extraction(
                        genai=genai,
                        client=client,
                        file_part=file_part,
                        candidate=result,
                        request_id=request_id,
                        )
                    if audit is not None:
                        result = _merge_corrected_result(
                            result, audit, header_keys, line_keys, include_line_items,
                            )

                result = _apply_datatype_normalization(
                    result, header_types, line_types, line_keys
                )

                logger.info(
                    "Notebook Gemini extraction completed — request_id=%s "
                    "attempt=%d duration_ms=%.2f",
                    request_id,
                    attempt + 1,
                    (time.perf_counter() - start) * 1000,
                )
                return result

            except GeminiValidationException:
                raise
            except Exception as exc:
                last_exception = exc
                error_text = str(exc)
                error_lower = error_text.lower()

                if ("429" in error_lower or "resource_exhausted" in error_lower or "quota" in error_lower):
                    classified = GeminiRateLimitException(
                        f"Gemini API rate limit exceeded: {error_text}"
                    )
                    wait_seconds = 15
                elif ("timeout" in error_lower or "deadline" in error_lower):
                    classified = GeminiTimeoutException(
                        f"Gemini API request timed out: {error_text}"
                    )
                    wait_seconds = 3
                elif(
                    "connection" in error_lower
                    or "connect" in error_lower
                    or "network" in error_lower
                    or "503" in error_lower
                    or "502" in error_lower
                    or "500" in error_lower
                     ):
                    classified = GeminiConnectionException(
                        f" Gemini API request failed: {error_text}"
                        )
                    wait_seconds = 3

                else:
                    classified = GeminiValidationException(
                        f"Gemini API request failed: {error_text}"
                    )
                    wait_seconds = 0

                logger.warning(
                    "Notebook Gemini extraction failed — request_id=%s "
                    "attempt=%d/%d error=%s",
                    request_id,
                    attempt + 1,
                    self.max_retries + 1,
                    error_text,
                )

                if attempt >= self.max_retries:
                    raise classified from last_exception

                time.sleep(wait_seconds * (attempt + 1))

        # Defensive fallback; the loop always returns or raises.
        raise GeminiConnectionException(
            f"Gemini extraction failed: {last_exception}"
        ) from last_exception

    def _verify_extraction(self,*,genai,client,file_part,candidate: dict,request_id: str) -> dict | None:
        """
        Re-read the original document and return evidence-backed corrections.

        The verifier does not replace the entire primary result blindly.
        It returns only corrections that are supported by the document.
        """

        verification_prompt = VERIFICATION_PROMPT_TEMPLATE.format(
            primary_json=json.dumps(
                candidate,
                ensure_ascii=False,
            )
        )

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    file_part,
                    verification_prompt,
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_audit_schema(),
                    temperature=0,
                    seed=43,
                ),
            )

            response_text = getattr(
                response,
                "text",
                None,
            )
    
            audit = parse_json_response(
                response_text or ""
            )
    
            if not isinstance(audit, dict):
                logger.warning(
                    "OCR verification returned invalid shape — request_id=%s",
                    request_id,
                )
                return None
    
            logger.info(
                "Notebook Gemini verification completed — "
                "request_id=%s corrections=%s",
                request_id,
                len(
                    audit.get("corrections", [])
                )
                if isinstance(
                    audit.get("corrections"),
                    list,
                )
                else 0,
            )
    
            return audit

        except Exception as exc:
            logger.warning(
                "Notebook Gemini verification skipped — "
                "request_id=%s error=%s",
                request_id,
                exc,
            )
            return None


    def _create_client(self, genai):
        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            raise GeminiConnectionException(
                "GEMINI_API_KEY is not configured."
            )

        try:
            return genai.Client(
                api_key=api_key,
                http_options={"timeout": self.timeout * 1000},
            )
        except Exception as exc:
            raise GeminiConnectionException(
                f"Failed to create Gemini client: {exc}"
            ) from exc


notebook_gemini_extractor = NotebookGeminiExtractor()