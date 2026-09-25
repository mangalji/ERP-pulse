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
from ocr.ai.providers import AIProviderError
from ocr.ai.service import ai_configuration_service

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


def _json_schema_type(data_type: str, *, key: str | None = None, is_line_field: bool = False) -> str:
    """Return the JSON primitive implied by the configured datatype."""
    registry_entry = DATATYPE_REGISTRY.get(_coerce_data_type(data_type))
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
    Catalogue of standard extraction fields for the dynamic
    File Template configuration UI.
    """
    return {
        "header_fields": [
            {
                "key": key,
                "label": FIELD_LABELS.get(key, key),
                "questionaire": FIELD_DESCRIPTIONS.get(key, ""),
                "data_type": FIELD_DATA_TYPES.get(key, "text"),
                "scope": "header",
                "standard": True,
            }
            for key in FIELD_DESCRIPTIONS
        ],
        "line_fields": [
            {
                "key": key,
                "label": LINE_ITEM_LABELS.get(key, key),
                "questionaire": LINE_ITEM_FIELDS.get(key, ""),
                "data_type": LINE_ITEM_DATA_TYPES.get(key, "text"),
                "scope": "line",
                "standard": True,
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


def resolve_field_config(
    requested_fields: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str], bool, dict[str, str], dict[str, str]]:
    """Resolve the mandatory template into the exact AI field contract."""
    if not isinstance(requested_fields, dict) or not requested_fields:
        raise ValueError("An extraction template is required for OCR processing.")

    selected_standard = requested_fields.get("standard_fields") or []
    custom_fields = requested_fields.get("custom_fields") or []
    overrides = requested_fields.get("standard_field_overrides") or {}
    if not isinstance(selected_standard, list):
        raise ValueError("standard_fields must be a list.")
    if not isinstance(custom_fields, list):
        raise ValueError("custom_fields must be a list.")
    if not isinstance(overrides, dict):
        raise ValueError("standard_field_overrides must be a JSON object.")
    if not selected_standard and not custom_fields:
        raise ValueError("Extraction template must contain at least one field.")

    header_fields: dict[str, str] = {}
    line_fields: dict[str, str] = {}
    header_types: dict[str, str] = {}
    line_types: dict[str, str] = {}
    reserved_keys = frozenset(FIELD_DESCRIPTIONS) | frozenset(LINE_ITEM_FIELDS) | {"line_items"}

    for raw_key in selected_standard:
        key = str(raw_key).strip()
        if not key or key == "line_items":
            continue
        if key in FIELD_DESCRIPTIONS:
            description = FIELD_DESCRIPTIONS[key]
            data_type = FIELD_DATA_TYPES.get(key, "text")
            default_scope = "header"
        elif key in LINE_ITEM_FIELDS:
            description = LINE_ITEM_FIELDS[key]
            data_type = LINE_ITEM_DATA_TYPES.get(key, "text")
            default_scope = "line"
        else:
            raise ValueError(f"Unknown standard field '{key}'.")
        override = overrides.get(key) or {}
        if not isinstance(override, dict):
            raise ValueError(f"standard_field_overrides['{key}'] must be an object.")
        description = str(override.get("questionaire") or override.get("description") or description).strip()
        if not description:
            raise ValueError(f"Questionaire is required for field '{key}'.")
        data_type = _coerce_data_type(override.get("data_type") or data_type)
        scope = override.get("scope") or default_scope
        if scope not in {"header", "line"}:
            raise ValueError(f"Invalid scope for field '{key}'.")
        if scope == "line":
            line_fields[key] = description
            line_types[key] = data_type
        else:
            header_fields[key] = description
            header_types[key] = data_type

    seen_keys = set(header_fields) | set(line_fields)
    for idx, custom in enumerate(custom_fields):
        if not isinstance(custom, dict):
            raise ValueError(f"custom_fields[{idx}] must be a dict, got {type(custom).__name__}")
        label = str(custom.get("label") or custom.get("key") or "").strip()
        if not label:
            raise ValueError(f"custom_fields[{idx}] must have a non-empty label or key")
        key = _slugify_field_key(str(custom.get("key") or label))
        if key in reserved_keys:
            raise ValueError(f"Custom field '{label}' conflicts with a standard field name ('{key}').")
        if key in seen_keys:
            raise ValueError(f"Duplicate custom field '{label}' (resolved key '{key}').")
        description = str(custom.get("questionaire") or custom.get("description") or "").strip()
        if not description:
            raise ValueError(f"Questionaire is required for custom field '{label}'.")
        data_type = _coerce_data_type(custom.get("data_type"))
        scope = custom.get("scope") or "header"
        if scope not in {"header", "line"}:
            raise ValueError(f"Invalid scope for custom field '{label}'.")
        if scope == "line":
            line_fields[key] = description
            line_types[key] = data_type
        else:
            header_fields[key] = description
            header_types[key] = data_type
        seen_keys.add(key)

    include_line_items = bool(line_fields) or "line_items" in selected_standard
    if include_line_items and not line_fields:
        raise ValueError("Line-item extraction was requested but no line fields are configured.")
    return header_fields, line_fields, include_line_items, header_types, line_types


VERIFICATION_PROMPT_TEMPLATE = """You are the verification stage of a production document extraction system.

Re-read the attached document in full and verify EVERY requested field against the source document before accepting the proposed result.

REQUESTED FIELD CONTRACT:
{field_contract}

PROPOSED EXTRACTION:
{primary_json}

Return ONLY the requested verification JSON structure.

Rules:
- Check every requested field, not just fields you recognize.
- Use each field's questionaire to understand exactly what information is required.
- Search the entire document again: headers, body, tables, footers, totals, metadata, notes, and entity blocks.
- For line fields, re-check every clearly separated source row and preserve source-row order.
- Do not invent or infer unsupported values.
- A value is acceptable only when supported by visible document evidence.
- If the proposed value is wrong or missing and the document contains the correct value, provide an evidence-backed correction.
- If the requested value genuinely cannot be determined, keep it null.
- Do not change a correct value merely because another equivalent formatting is possible.
- Before returning, perform one final field-by-field comparison between the proposed result and the document.
"""


# AUDIT_SCHEMA: dict[str, Any] = {
#     "type": "object",
#     "properties": {
#         "needs_correction": {"type": "boolean"},
#         "corrections": {
#             "type": "array",
#             "items": {
#                 "type": "object",
#                 "properties": {
#                     "field": {"type": "string"},
#                     "reason": {"type": "string"},
#                     "corrected_value": {
#                         "anyOf": [
#                             {"type": "string"},
#                             {"type": "number"},
#                             {"type": "boolean"},
#                             {"type": "null"},
#                             {
#                                 "type": "array",
#                                 "items": {
#                                     "type": "object",
#                                     "additionalProperties": True,
#                                 },
#                             },
#                         ]
#                     },
#                 },
#                 "required": [
#                     "field",
#                     "reason",
#                     "corrected_value",
#                 ],
                
#             },
#         },
#     },
#     "required": [
#         "needs_correction",
#         "corrections",
#     ],
    
# }

def _build_audit_schema(
    line_fields: dict[str, str],
    line_types: dict[str, str],
    include_line_items: bool,
) -> dict[str, Any]:
    corrected_value_types = [
        {"type": "string"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "null"},
    ]

    if include_line_items:
        line_properties = {
            key: {
                "type": _json_schema_type(
                    line_types.get(key, "text"),
                    key=key,
                    is_line_field=True,
                ),
            }
            for key in line_fields
        }

        corrected_value_types.append(
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": line_properties,
                    "required": list(line_fields.keys()),
                },
            }
        )

    return {
        "type": "object",
        "properties": {
            "needs_correction": {
                "type": "boolean",
            },
            "corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                        },
                        "reason": {
                            "type": "string",
                        },
                        "corrected_value": {
                            "anyOf": corrected_value_types,
                        },
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


# def _audit_schema() -> dict[str, Any]:
#     return AUDIT_SCHEMA

def _audit_schema(
    line_fields: dict[str, str],
    line_types: dict[str, str],
    include_line_items: bool,
) -> dict[str, Any]:
    return _build_audit_schema(
        line_fields=line_fields,
        line_types=line_types,
        include_line_items=include_line_items,
    )

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

    header_keys/line_keys are always supplied from the selected template.
    """
    if header_keys is None or line_keys is None:
        raise ValueError("Resolved OCR field keys are required.")
    resolved_header_keys = header_keys
    resolved_line_keys = line_keys

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
    if header_keys is None or line_keys is None:
        raise ValueError("Resolved OCR field keys are required.")
    resolved_header_keys = header_keys
    resolved_line_keys = line_keys

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
            elif merged.get(field) is not None and corrected_value is not None:
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
                        elif candidate_value is not None and verifier_value is not None:
                            merged_item[key] = verifier_value

                    merged_items.append(merged_item)

                merged["line_items"] = merged_items

    return _normalize_result(
        merged, resolved_header_keys, resolved_line_keys, include_line_items,
    )


def build_prompt(
    header_fields: dict[str, str],
    line_fields: dict[str, str],
    include_line_items: bool,
    header_types: dict[str, str],
    line_types: dict[str, str],
) -> str:
    """Build the extraction prompt entirely from the resolved template contract."""
    field_lines = "\n".join(
        f'- "{key}": {description}{_type_format_hint(header_types.get(key, "text"))}'
        for key, description in header_fields.items()
    )
    if include_line_items:
        item_lines = "\n".join(
            f'  - "{key}": {description}{_type_format_hint(line_types.get(key, "text"))}'
            for key, description in line_fields.items()
        )
        line_items_section = f"\nLine-item fields:\n{item_lines}\n"
        line_item_rules = """- Extract EVERY clearly separated source row.
- Preserve source-row order.
- Never merge, collapse, skip, or summarize separate rows.
- Preserve complete visible row information in the requested fields.
- Before finalizing, recount source rows and compare that count with line_items."""
    else:
        line_items_section = ""
        line_item_rules = "- Do not return line_items because no line fields were requested."
    return f"""You are the PRIMARY extraction stage of a production business-document extraction system.
Read the attached document in full. Layouts vary widely across invoices, receipts, purchase orders, vouchers, credit notes, debit notes, and other business documents.

Top-level fields requested by the user's template:
{field_lines}
{line_items_section}
Rules:
- Respond with ONLY one valid JSON object.
- Use EXACTLY the requested field names and structure.
- Use each field's questionaire/instruction as the definition of what information to extract.
- NEVER invent or guess a value.
- Use null only when the requested value is genuinely absent or cannot be determined from the document.
- Inspect the entire document before deciding a field is null.
- Follow the declared datatype for every field.
{line_item_rules}
- Before returning the JSON, internally re-scan the document and verify EVERY requested field against visible source evidence.
- If an extracted value is not supported, correct it or return null.
- The final JSON must contain only the fields defined by this template.
"""




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
    """Company-scoped OCR extractor with a provider-neutral AI backend.

    The class name is retained for compatibility with existing imports. The
    implementation is no longer Gemini-specific: the active company
    configuration resolves the provider and model at request time.
    """

    def __init__(self) -> None:
        self.timeout = getattr(settings, "OCR_TIMEOUT", 180)
        self.max_retries = getattr(settings, "OCR_MAX_RETRIES", 3)
        self.retry_delay = getattr(settings, "OCR_RETRY_DELAY", 1.0)

    def extract(
        self,
        file_path: str | Path,
        mime_type: str | None = None,
        requested_fields: dict[str, Any] | None = None,
        *,
        company=None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> dict:
        (
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
        ) = resolve_field_config(requested_fields)

        effective_timeout = self.timeout if timeout is None else timeout
        effective_max_retries = (
            self.max_retries if max_retries is None else max_retries
        )

        if effective_timeout <= 0:
            raise ValueError("OCR extraction timeout must be greater than 0.")
        if effective_max_retries < 0:
            raise ValueError("OCR max_retries cannot be negative.")
        if company is None:
            raise GeminiConnectionException(
                "No company context was supplied for OCR AI configuration."
            )

        header_keys = tuple(header_fields.keys())
        line_keys = tuple(line_fields.keys())
        schema = _build_schema(
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
        )
        prompt = build_prompt(
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
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

        request_id = uuid.uuid4().hex[:8]
        provider = ai_configuration_service.resolve_provider(company=company)

        logger.info(
            "Company AI OCR extraction started — request_id=%s file=%s provider=%s model=%s",
            request_id,
            path.name,
            getattr(provider, "__class__", type(provider)).__name__,
            getattr(provider, "model", "unknown"),
        )

        last_exception: Exception | None = None
        start = time.perf_counter()

        for attempt in range(effective_max_retries + 1):
            try:
                result = _normalize_result(
                    provider.generate_json(
                        file_path=path,
                        mime_type=media_type,
                        prompt=prompt,
                        schema=schema,
                        timeout=effective_timeout,
                        seed=42,
                    ),
                    header_keys,
                    line_keys,
                    include_line_items,
                )

                result = _apply_datatype_normalization(
                    result,
                    header_types,
                    line_types,
                    line_keys,
                )

                audit = self._verify_extraction(
                    provider=provider,
                    file_path=path,
                    mime_type=media_type,
                    candidate=result,
                    request_id=request_id,
                    timeout=effective_timeout,
                    header_fields=header_fields,
                    line_fields=line_fields,
                    header_types=header_types,
                    line_types=line_types,
                )
                if audit is None:
                    raise GeminiValidationException(
                        "OCR extraction could not be verified against the source document."
                    )

                result = _merge_corrected_result(
                    result,
                    audit,
                    header_keys=header_keys,
                    line_keys=line_keys,
                    include_line_items=include_line_items,
                )
                result = _apply_datatype_normalization(
                    result,
                    header_types,
                    line_types,
                    line_keys,
                )

                logger.info(
                    "Company AI OCR extraction completed — request_id=%s attempt=%d duration_ms=%.2f",
                    request_id,
                    attempt + 1,
                    (time.perf_counter() - start) * 1000,
                )
                return result

            except GeminiValidationException:
                raise
            except AIProviderError as exc:
                last_exception = exc
                error_text = str(exc)
                error_lower = error_text.lower()

                if any(token in error_lower for token in ("429", "quota", "rate limit", "resource_exhausted")):
                    classified = GeminiRateLimitException(
                        f"AI provider rate limit exceeded: {error_text}"
                    )
                    wait_seconds = 15
                elif any(token in error_lower for token in ("timeout", "deadline")):
                    classified = GeminiTimeoutException(
                        f"AI provider request timed out: {error_text}"
                    )
                    wait_seconds = 3
                elif any(token in error_lower for token in ("connection", "network", "503", "502", "500")):
                    classified = GeminiConnectionException(
                        f"AI provider request failed: {error_text}"
                    )
                    wait_seconds = 3
                else:
                    classified = GeminiValidationException(
                        f"AI provider request failed: {error_text}"
                    )
                    wait_seconds = 0

                logger.warning(
                    "Company AI OCR extraction failed — request_id=%s attempt=%d/%d error=%s",
                    request_id,
                    attempt + 1,
                    effective_max_retries + 1,
                    error_text,
                )

                if attempt >= effective_max_retries:
                    raise classified from last_exception

                if wait_seconds:
                    time.sleep(wait_seconds * (attempt + 1))

            except Exception as exc:
                last_exception = exc
                logger.warning(
                    "Company AI OCR extraction failed — request_id=%s attempt=%d/%d error=%s",
                    request_id,
                    attempt + 1,
                    effective_max_retries + 1,
                    exc,
                )
                if attempt >= effective_max_retries:
                    raise GeminiConnectionException(
                        f"AI provider request failed: {exc}"
                    ) from exc

        raise GeminiConnectionException(
            f"AI extraction failed: {last_exception}"
        ) from last_exception

    def _verify_extraction(
        self,
        *,
        provider,
        file_path: Path,
        mime_type: str,
        candidate: dict,
        request_id: str,
        timeout: float,
        header_fields: dict[str, str],
        line_fields: dict[str, str],
        header_types: dict[str, str],
        line_types: dict[str, str],
    ) -> dict | None:
        """Run a template-driven evidence check using the same provider."""

        field_contract = json.dumps(
            {
                "header_fields": [
                    {"key": key, "questionaire": description, "data_type": header_types[key], "scope": "header"}
                    for key, description in header_fields.items()
                ],
                "line_fields": [
                    {"key": key, "questionaire": description, "data_type": line_types[key], "scope": "line"}
                    for key, description in line_fields.items()
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        verification_prompt = VERIFICATION_PROMPT_TEMPLATE.format(
            field_contract=field_contract,
            primary_json=json.dumps(candidate, ensure_ascii=False),
        )

        try:
            audit = provider.generate_json(
                file_path=file_path,
                mime_type=mime_type,
                prompt=verification_prompt,
                schema=_audit_schema(
                    line_fields=line_fields,
                    line_types=line_types,
                    include_line_items=bool(line_fields),
                ),
                timeout=timeout,
                seed=43,
            )

            if not isinstance(audit, dict):
                logger.warning(
                    "OCR verification returned invalid shape — request_id=%s",
                    request_id,
                )
                return None

            logger.info(
                "Company AI OCR verification completed — request_id=%s corrections=%s",
                request_id,
                len(audit.get("corrections", []))
                if isinstance(audit.get("corrections"), list)
                else 0,
            )
            return audit

        except Exception as exc:
            logger.warning(
                "OCR verification skipped — request_id=%s error=%s",
                request_id,
                exc,
            )
            return None


notebook_gemini_extractor = NotebookGeminiExtractor()
