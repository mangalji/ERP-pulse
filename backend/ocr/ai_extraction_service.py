"""
document AI extraction service.

This service ports the extraction logic from the approved Colab prototype
into the AGSuite ERP application without changing the existing OCR upload
storage layer or the asynchronous IDP pipeline.

Step 1 scope:
    PDF/image -> AI -> structured JSON

NetSuite mapping/posting, Excel generation, Celery, and the existing
OpenCV preprocessing pipeline are intentionally outside this service.
"""

from __future__ import annotations

import json
import re
from common.timing import timed_stage

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone
from ocr.ai.providers import AIProviderError
from ocr.ai.service import ai_configuration_service
from ocr.services.calculated_values import apply_calculated_values

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

# FIELD_DESCRIPTIONS = {
#     "invoice_number":( # field_id = tranid
#         "Invoice number or ID printed on the supplier invoice. "
#         "Do not use a purchase order number or vendor ID."
#         ),
#     "invoice_date": ( # field_id = trandate
#         "Invoice issue date, normalized format YYYY-MM-DD when unambiguous."
#         ),
#     "due_date": ( # field_id = duedate
#         "Payment due date, normalized to YYYY-MM-DD when stated. "
#         "Do not calculate or guess a missing due date, except for the "
#         "single-date fallback explicitly stated in the extraction rules."
#         ),
#     "vendor_name": ( # field_id = entity
#         "Name of the vendor or supplier issuing the invoice."
#         ),
#     "subsidiary": ( # field_id = subsidiary
#         "Company subsidiary or business unit, only when explicitly "
#         "identified. Do not guess."
#         ),
#     "location": (
#         "NetSuite Location, branch, site, or warehouse for this Vendor Bill. "
#         "Use the exact name only when explicitly stated on the invoice. "
#         "Do not infer a Location from an address or guess a default; return "
#         "null when the invoice does not identify one."
#     ),
#     "currency": ( # field_id = currency
#         "Three-letter currency code, such as USD, INR, or EUR. "
#         "Return null if the currency cannot be identified reliably."
#         ),
#     "total_tax_amount":( # field_id = taxtotal
#         "Total tax amount for the entire invoice. Use the invoice-level "
#         "tax total when shown; otherwise sum line-item taxes only when "
#         "all relevant line tax amounts are available. "
#         "Return a number without a currency symbol."
#         ),
#     "amount": ( # field_id = usertotal
#         "Grand total of the entire invoice after discounts and including "
#         "applicable taxes and charges, as shown on the invoice. "
#         "Return a number without a currency symbol. Do not substitute "
#         "an individual line amount."
#         ),
# }

# LINE_ITEM_FIELDS = {
#     "item": ( # field_id = item
#         "Product, service, or charge name/description for this specific "
#         "invoice line. Do not combine separate line items."
#         ),
#     "quantity": ( # field_id = quantity
#         "Quantity for this line item. Return a number; do not guess "
#         "if the quantity is not shown."
#         ),
#     "unit_price": ( # field_id = rate
#         "Price per unit for this line item as printed on the invoice. "
#         "Return a number without a currency symbol; do not calculate "
#         "a missing unit price."
#         ),
#     "subtotal": ( # field_id = amount
#         "This line item's amount before tax, after any stated line-level "
#         "discounts. This is not the invoice-level subtotal. "
#         "Return a number without a currency symbol."
#         ),
#     "tax_amount": ( # field_id = tax1amt
#         "Tax amount attributable to this specific line item, not the "
#         "tax total for the entire invoice. Return a number without "
#         "a currency symbol."
#         ),
#     "tax_rate": ( # field_id = taxrate1
#         "Tax rate for this line item, expressed as a percentage when "
#         "explicitly stated, for example 18 for 18%. Do not guess "
#         "a missing rate."
#         ),
#     "total_amount":( # field_id = grossamt
#         "Final amount for this specific line item, including its "
#         "applicable taxes and line-level charges after discounts. "
#         "This is not the invoice grand total. Return a number "
#         "without a currency symbol."
#         )
# }

# File-upload extraction field contract. The original field prompts above are
# intentionally retained for email extraction and backward compatibility.
# These shorter, stricter descriptions are used only by the file-upload flow.
FIELD_DESCRIPTIONS = {
    "invoice_number": "Invoice number or ID. Exclude PO number or vendor ID.",
    "invoice_date": "Invoice issue date in YYYY-MM-DD format.",
    "due_date": "Payment due date in YYYY-MM-DD format. Do not calculate.",
    "vendor_name": "Vendor or supplier name.",
    "subsidiary": "Explicitly identified company subsidiary or business unit only.",
    "location": "Explicitly stated NetSuite Location, branch, site, or warehouse. Do not infer from address.",
    "currency": "Three-letter currency code, such as USD, EUR, or INR.",
    "total_tax_amount": "Total tax amount for the entire invoice.",
    "amount": "Grand total including taxes and charges.",
}

LINE_ITEM_FIELDS = {
    "item": "Product, service, or charge name/description.",
    "quantity": "Line quantity.",
    "unit_price": "Price per unit.",
    "subtotal": "Line amount before tax, after line discounts.",
    "tax_amount": "Tax amount for this specific line.",
    "tax_rate": "Tax rate percentage, such as 18 for 18%.",
    "total_amount": "Final line amount including taxes and charges.",
}

FIELD_LABELS = {
    "invoice_number": "Invoice Number",
    "invoice_date": "Invoice Date",
    "due_date": "Due Date",
    "vendor_name": "Vendor Name",
    "subsidiary": "Subsidiary",
    "currency": "Currency",
    "location":'Location',
    "total_tax_amount":"Total Tax",
    "amount": "Amount",
}

LINE_ITEM_LABELS = {
    "item": "Item",
    "quantity": "Quantity",
    "unit_price": "Unit Price",
    "subtotal": "Subtotal",
    "tax_amount": "Tax Amount",
    "tax_rate": "Tax Rate (%)",
    "total_amount": "Total Amount",
}

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
            .replace("â‚¹", "")
            .replace("$", "")
            .replace("â‚¬", "")
            .replace("Â£", "")
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

FIELD_DATA_TYPES = {
    "invoice_number": "text",
    "invoice_date": "date",
    "due_date": "date",
    "vendor_name": "text",
    "subsidiary": "text",
    "currency": "text",
    "location":"text",
    "total_tax_amount":"currency",
    "amount": "currency",
}

LINE_ITEM_DATA_TYPES = {
    "item": "text",
    "quantity": "number",
    "unit_price": "currency",
    "subtotal": "currency",
    "tax_amount": "currency",
    "tax_rate": "number",
    "total_amount": "currency",
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

def resolve_field_config(
    requested_fields: dict[str, Any] | None,
    *,
    field_descriptions: dict[str, str] | None = None,
    line_item_fields: dict[str, str] | None = None,
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

    header_catalog = field_descriptions or FIELD_DESCRIPTIONS
    line_catalog = line_item_fields or LINE_ITEM_FIELDS

    header_fields: dict[str, str] = {}
    line_fields: dict[str, str] = {}
    header_types: dict[str, str] = {}
    line_types: dict[str, str] = {}
    reserved_keys = frozenset(header_catalog) | frozenset(line_catalog) | {"line_items"}

    for raw_key in selected_standard:
        key = str(raw_key).strip()
        if not key or key == "line_items":
            continue
        if key in header_catalog:
            description = header_catalog[key]
            data_type = FIELD_DATA_TYPES.get(key, "text")
            default_scope = "header"
        elif key in line_catalog:
            description = line_catalog[key]
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
        _normalise_configured_default_value(
            override.get("default_value"),
            data_type,
            label=str(override.get("label") or key),
        )
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

        if custom.get("enabled") is False:
            continue

        label = str(custom.get("label") or custom.get("key") or "").strip()
        
        if not label:
            raise ValueError(f"custom_fields[{idx}] must have a non-empty label or key")
        
        # The user-facing label is the source of truth for custom JSON keys.
        # Older UI versions could persist only the first typed character in
        # ``key`` (for example key="m", label="memo").  Do not let that
        # stale hidden value change the AI contract.
        key = _slugify_field_key(label)
        
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
        _normalise_configured_default_value(
            custom.get("default_value"),
            data_type,
            label=label,
        )
        
        if scope == "line":
            line_fields[key] = description
            line_types[key] = data_type
        
        else:
            header_fields[key] = description
            header_types[key] = data_type
        
        seen_keys.add(key)
        
    if not header_fields and not line_fields:
        raise ValueError(
            "Extraction template must contain at least one enabled field."
        )
    include_line_items = bool(line_fields) or "line_items" in selected_standard
    if include_line_items and not line_fields:
        raise ValueError("Line-item extraction was requested but no line fields are configured.")
    return header_fields, line_fields, include_line_items, header_types, line_types

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


def _is_empty_extracted_value(value: Any) -> bool:
    """Return whether an AI-extracted scalar should be treated as absent."""
    return value is None or (isinstance(value, str) and not value.strip())


def _normalise_configured_default_value(
    value: Any,
    data_type: str,
    *,
    label: str,
) -> Any:
    """Validate and normalise one optional template fallback value."""
    if _is_empty_extracted_value(value):
        return None

    normalized = _normalize_datatype(value, data_type)
    if normalized is None:
        raise ValueError(
            f'Default Value for field "{label}" is not valid for datatype '
            f'"{data_type}".'
        )
    return normalized


def _configured_field_defaults(
    requested_fields: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return normalised header and line fallbacks from a saved template."""
    if not isinstance(requested_fields, dict):
        return {}, {}

    selected_standard = requested_fields.get("standard_fields") or []
    overrides = requested_fields.get("standard_field_overrides") or {}
    custom_fields = requested_fields.get("custom_fields") or []
    header_defaults: dict[str, Any] = {}
    line_defaults: dict[str, Any] = {}

    if isinstance(selected_standard, list) and isinstance(overrides, dict):
        for raw_key in selected_standard:
            key = str(raw_key or "").strip()
            if key in FIELD_DESCRIPTIONS:
                fallback_type, fallback_scope = FIELD_DATA_TYPES.get(key, "text"), "header"
            elif key in LINE_ITEM_FIELDS:
                fallback_type, fallback_scope = LINE_ITEM_DATA_TYPES.get(key, "text"), "line"
            else:
                continue

            override = overrides.get(key) or {}
            if not isinstance(override, dict):
                continue
            value = _normalise_configured_default_value(
                override.get("default_value"),
                _coerce_data_type(override.get("data_type") or fallback_type),
                label=str(override.get("label") or key),
            )
            if value is not None:
                scope = override.get("scope") or fallback_scope
                target = line_defaults if scope == "line" else header_defaults
                target[key] = value

    if isinstance(custom_fields, list):
        for custom in custom_fields:
            if not isinstance(custom, dict) or custom.get("enabled") is False:
                continue
            label = str(custom.get("label") or custom.get("key") or "").strip()
            if not label:
                continue
            value = _normalise_configured_default_value(
                custom.get("default_value"),
                _coerce_data_type(custom.get("data_type")),
                label=label,
            )
            if value is not None:
                key = _slugify_field_key(label)
                target = line_defaults if custom.get("scope") == "line" else header_defaults
                target[key] = value

    return header_defaults, line_defaults


def _apply_template_default_values(
    data: dict[str, Any],
    requested_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply configured template values after extraction.

    Template values remain intentional overrides for all ordinary fields.
    Location is different: a location directly extracted from a bill document
    or vendor email is source evidence and must take precedence. Its template
    value is therefore used only when AI did not find a location.
    """
    header_defaults, line_defaults = _configured_field_defaults(requested_fields)
    if not header_defaults and not line_defaults:
        return data

    result = dict(data)
    for key, value in header_defaults.items():
        if key == "location" and not _is_empty_extracted_value(result.get(key)):
            continue
        result[key] = value

    if line_defaults and isinstance(result.get("line_items"), list):
        result["line_items"] = [
            (
                {
                    **line,
                    **{
                        key: value
                        for key, value in line_defaults.items()
                        if key != "location"
                        or _is_empty_extracted_value(line.get(key))
                    },
                }
                if isinstance(line, dict)
                else line
            )
            for line in result["line_items"]
        ]

    return result


def apply_invoice_date_fallback(
    data: dict[str, Any],
    header_keys: tuple[str, ...],
    *,
    source: str,
    email_received_at: datetime | None = None,
) -> dict[str, Any]:
    """Apply a source-specific invoice-date fallback only when date is absent."""
    if "invoice_date" not in header_keys:
        return data
    if not _is_empty_extracted_value(data.get("invoice_date")):
        return data

    result = dict(data)
    if source == "email":
        if email_received_at is None:
            return data
        fallback_date = (
            timezone.localtime(email_received_at).date()
            if timezone.is_aware(email_received_at)
            else email_received_at.date()
        )
    elif source == "file":
        fallback_date = timezone.localdate()
    else:
        return data

    result["invoice_date"] = fallback_date.isoformat()
    return result


# LEGACY FILE PROMPT — retained as comments per request; not executed.
# def build_prompt_legacy(...):
#     field_lines = "\n".join(
#         f'- "{key}": {description}{_type_format_hint(header_types.get(key, "text"))}'
#         for key, description in header_fields.items()
#     )
#     # The old prompt rendered these verbose line-item rules:
#     # - Extract EVERY clearly separated source row that is visibly present.
#     # - Preserve source-row order; never merge, collapse, skip, duplicate, or summarize.
#     # - Read each line field from its own source cell/column.
#     # - Do not copy missing values from another row, header, footer, or nearby column.
#     # - Leave derived subtotal, tax, or total fields null when not explicitly shown.
#     # - Recount visible source rows before finalizing.
#     old_date_fallback_rule = (
#         "Single-date fallback: preserve the source date as due_date and set "
#         "invoice_date to the processing/reference date."
#     )
#     return f"""You are the PRIMARY extraction stage of a production business-document extraction system.
# Read the attached document in full. Layouts vary widely across invoices, receipts,
# purchase orders, vouchers, credit notes, debit notes, and other business documents.
#
# Top-level fields requested by the user's template:
# {field_lines}
#
# Rules:
# - Respond with ONLY one valid JSON object.
# - Use EXACTLY the requested field names and structure; do not add extra keys.
# - Extract only the fields listed in the configured template.
# - NEVER invent, assume, calculate, or guess a requested value.
# - Use null when a value is missing, unreadable, ambiguous, or unsupported.
# - Follow the declared datatype for every field.
# {old_date_fallback_rule}
# """


def build_file_prompt(
    header_fields: dict[str, str],
    line_fields: dict[str, str],
    include_line_items: bool,
    header_types: dict[str, str],
    line_types: dict[str, str],
    *,
    source: str = "file",
    document_context: dict[str, Any] | None = None,
) -> str:
    """Build the new upload-file prompt; the legacy prompt remains above."""
    continuation_part = bool(
        document_context
        and int(document_context.get("current_part", 1) or 1) > 1
    )
    prompt_header_fields = {} if continuation_part else header_fields
    field_lines = "\n".join(
        f'- "{key}": {description}{_type_format_hint(header_types.get(key, "text"))}'
        for key, description in prompt_header_fields.items()
    )

    if include_line_items:
        item_lines = "\n".join(
            f'  - "{key}": {description}{_type_format_hint(line_types.get(key, "text"))}'
            for key, description in line_fields.items()
        )
        line_section = f"\nLine-item fields:\n{item_lines}\n"
        line_rules = """- Extract every visible row in source order; do not merge, skip, duplicate, or summarize rows.
- Extract only explicitly stated values; return null if a value is missing or unclear."""
    else:
        line_section = ""
        line_rules = "- Do not return line_items because no line-item fields were requested."

    date_rule = ""
    if "invoice_date" in prompt_header_fields:
        if source == "email":
            date_rule = "- If invoice_date is not explicitly present, return null. The backend assigns the email received date after extraction."
        else:
            date_rule = "- If invoice_date is not explicitly present, return null. The backend assigns today's date after extraction."
    if "due_date" in prompt_header_fields:
        date_rule += "\n- If due_date is not explicitly present, return null."

    if source == "email":
        source_instruction = "Read the entire email body before responding."
    elif document_context:
        source_instruction = (
            "Read every page of the supplied PDF part before responding. "
            "The part metadata identifies its position in the original document."
        )
    else:
        source_instruction = "Read the entire uploaded document before responding."

    context_section = ""
    if document_context:
        context_section = f"""
DOCUMENT PART CONTEXT
{json.dumps(document_context, ensure_ascii=False, indent=2, default=str)}

This file is one part of a multi-part document. The Document ID identifies
the same original PDF across requests; it does not contain the previous
document content. Use the part number and page range to understand where
this file belongs in the original document.

For continuation parts:
- Preserve valid values from the previous header context.
- Never replace a previous valid value with null merely because it is not
  visible in this part.
- Extract only line items visible in the current part. Previous line-item
  data is intentionally not included and must not be reconstructed.
- Do not repeat line items from earlier parts.
"""

    header_section = (
        f"Requested header fields:\n{field_lines}"
        if prompt_header_fields
        else "Continuation part: header fields are intentionally omitted; return only line_items."
    )

    return f"""Extract business document data into the exact requested JSON schema.
{source_instruction}
{context_section}

{header_section}
{line_section}
Rules:
- Respond with only one valid JSON object.
- Use exactly the requested field names and structure; do not add extra keys.
- Extract only values explicitly supported by the document.
- Use null for missing, unreadable, ambiguous, or unsupported values.
- Never invent, assume, infer, calculate, or guess values.
- Numeric fields must contain numbers only, without currency symbols or separators.
- Dates must use YYYY-MM-DD format.
{date_rule}
{line_rules}
"""


def build_email_prompt(
    header_fields: dict[str, str],
    line_fields: dict[str, str],
    include_line_items: bool,
    header_types: dict[str, str],
    line_types: dict[str, str],
    *,
    email_body: str,
) -> str:
    """Build an email-only vendor-bill classification/extraction prompt."""
    header_lines = "\n".join(
        f'- "{key}": {description}{_type_format_hint(header_types.get(key, "text"))}'
        for key, description in header_fields.items()
    )
    line_lines = "\n".join(
        f'  - "{key}": {description}{_type_format_hint(line_types.get(key, "text"))}'
        for key, description in line_fields.items()
    )
    line_section = (
        f"Line-item fields:\n{line_lines}"
        if include_line_items
        else "No line-item fields were requested; return line_items as an empty array."
    )

    return f"""You are an email vendor-bill extraction assistant.
Classify the message before extracting it; this email prompt is independent
from the PDF/file-upload prompt.

First classify the email:
- Set "is_vendor_bill" to true only when the email contains clear billing, purchase, supply, charge, or payment intent and at least one specific product or service line.
- For ordinary conversations, follow-ups, delivery updates, enquiries, or vague references, set "is_vendor_bill" to false and "data" to null.

For a vendor bill, return one JSON object with "is_vendor_bill": true and place
the extracted fields inside "data". The matched NetSuite vendor supplies vendor
identity; do not replace it from email text.

For a vendor bill, extract the following fields from the email body.

Requested header fields:
{header_lines}

{line_section}

Rules:
- Return exactly one JSON object with is_vendor_bill and data.
- Set data to null when is_vendor_bill is false.
- Use null for missing, ambiguous, or unsupported values.
- Never invent, infer, calculate, or guess values.
- Numeric fields must contain numbers only.
- Dates must use YYYY-MM-DD format.
- Extract every visible row in source order; do not merge, skip, duplicate, or summarize rows.
- Do not treat ordinary conversation, follow-ups, enquiries, or delivery updates as bills.

EMAIL BODY START
{email_body}
EMAIL BODY END
"""

class AIExtractor:
    """Company-scoped OCR extractor with a provider-neutral AI backend.

    The class name is retained for compatibility with existing imports. The
    implementation is no longer Gemini-specific: the active company
    configuration resolves the provider and model at request time.
    """

    def __init__(self) -> None:
        self.timeout = getattr(settings, "OCR_TIMEOUT", 180)
        self.max_retries = getattr(settings, "OCR_MAX_RETRIES", 2)
        self.retry_delay = getattr(settings, "OCR_RETRY_DELAY", 1.0)

    @timed_stage("ai.document_extraction")
    def extract(
        self,
        file_path: str | Path,
        mime_type: str | None = None,
        requested_fields: dict[str, Any] | None = None,
        *,
        company=None,
        timeout: float | None = None,
        max_retries: int | None = None,
        document_context: dict[str, Any] | None = None,
    ) -> dict:
        (
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
        ) = resolve_field_config(
            requested_fields,
            field_descriptions=FIELD_DESCRIPTIONS,
            line_item_fields=LINE_ITEM_FIELDS,
        )

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
        continuation_part = bool(
            document_context
            and int(document_context.get("current_part", 1) or 1) > 1
        )
        prompt_header_fields = {} if continuation_part else header_fields
        prompt_header_types = {
            key: value for key, value in header_types.items()
            if key in prompt_header_fields
        }
        schema = _build_schema(
            prompt_header_fields,
            line_fields,
            include_line_items,
            prompt_header_types,
            line_types,
        )
        prompt = build_file_prompt(
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
            document_context=document_context,
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
                # Log before the provider call so the precise prompt remains
                # visible even when the provider is unavailable or times out.
                logger.info(
                    "AI EXTRACTION DEBUG | source=file | request_id=%s | "
                    "file=%s | provider=%s | model=%s\nPROMPT:\n%s",
                    request_id,
                    path.name,
                    provider.__class__.__name__,
                    getattr(provider, "model", "unknown"),
                    prompt,
                )
                # logger.info(
                #     "Current AI provider=%s | model=%s",provider.__class__.__name__,getattr(provider, "model", "unknown"),
                # )
                provider_result = provider.generate_json(
                    file_path=path,
                    mime_type=media_type,
                    prompt=prompt,
                    schema=schema,
                    timeout=effective_timeout,
                    seed=42,
                )
                # Development diagnostic: prints the exact final prompt and
                # unmodified provider text to the backend terminal.  Do not
                # move this data to frontend/API responses or persistence.
                logger.info(
                    "AI EXTRACTION DEBUG | source=file | request_id=%s | "
                    "RAW AI RESPONSE:\n%s\nPARSED AI RESPONSE:\n%s",
                    request_id,
                    getattr(provider, "last_raw_response", ""),
                    json.dumps(provider_result, ensure_ascii=False, indent=2, default=str),
                )
                result = _normalize_result(
                    provider_result,
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
                result = apply_calculated_values(result)
                if not continuation_part:
                    result = _apply_template_default_values(result, requested_fields)
                    result = apply_invoice_date_fallback(
                        result,
                        header_keys,
                        source="file",
                    )
                logger.info(
                    "AI EXTRACTION DEBUG | source=file | request_id=%s | "
                    "TEMPLATE-MAPPED RESULT:\n%s",
                    request_id,
                    json.dumps(result, ensure_ascii=False, indent=2, default=str),
                )

                if company is not None:
                    from audit.integration_alerts import mark_ai_healthy
                    mark_ai_healthy(company=company)

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
                status_code = getattr(exc, "status_code", None)
                rate_limited = getattr(exc, "rate_limited", False)
                retryable = getattr(exc, "retryable", False)
                quota_exhausted = getattr(exc, "quota_exhausted", False)

                if quota_exhausted:
                    classified = GeminiRateLimitException(
                        f"AI provider quota exhausted: {error_text}"
                    )
                    should_retry = False
                    wait_seconds = 0
                
                elif rate_limited:
                    classified = GeminiRateLimitException(
                        f"AI provider rate limit exceeded: {error_text}"
                    )
                    should_retry = True
                    wait_seconds = 15

                elif retryable:
                    if status_code in {408, 504}:
                        classified = GeminiTimeoutException(
                            f"AI provider request timed out: {error_text}"
                        )
                    else:
                        classified = GeminiConnectionException(
                            f"AI provider temporary request failure: {error_text}"
                        )
                    should_retry = True
                    wait_seconds = min(2 ** attempt, 8)

                else:
                    classified = GeminiValidationException(
                        f"AI provider request failed: {error_text}"
                    )
                    should_retry = False
                    wait_seconds = 0

                logger.warning(
                    "Company AI OCR extraction failed — request_id=%s attempt=%d/%d error=%s",
                    request_id,
                    attempt + 1,
                    effective_max_retries + 1,
                    error_text,
                )

                if not should_retry or attempt >= effective_max_retries:
                    if company is not None:
                        from audit.integration_alerts import report_ai_connection_failure
                        report_ai_connection_failure(company=company, error=exc)
                    raise classified from last_exception

                if wait_seconds:
                    time.sleep(wait_seconds)

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

    @timed_stage("ai.email_extraction")
    def extract_email_text(
        self,
        email_body: str,
        requested_fields: dict[str, Any] | None = None,
        *,
        company=None,
        email_received_at: datetime | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """Extract a sender-verified vendor email with its own prompt.

        The exact template contract, schema construction and datatype
        normalization used for file OCR are deliberately reused here, while
        the email prompt remains independent from file extraction behaviour.
        """
        (
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
        ) = resolve_field_config(requested_fields)
        if company is None:
            raise GeminiConnectionException(
                "No company context was supplied for OCR AI configuration."
            )
        if not isinstance(email_body, str) or not email_body.strip():
            raise GeminiValidationException("A sender-matched email has no readable body to extract.")

        effective_timeout = self.timeout if timeout is None else timeout
        effective_max_retries = self.max_retries if max_retries is None else max_retries
        if effective_timeout <= 0:
            raise ValueError("OCR extraction timeout must be greater than 0.")
        if effective_max_retries < 0:
            raise ValueError("OCR max_retries cannot be negative.")

        header_keys = tuple(header_fields.keys())
        line_keys = tuple(line_fields.keys())
        extraction_schema = _build_schema(
            header_fields, line_fields, include_line_items, header_types, line_types
        )
        schema = {
            "type": "object",
            "properties": {
                "is_vendor_bill": {"type": "boolean"},
                "data": {
                    **extraction_schema,
                    "nullable": True,
                },
            },
            "required": ["is_vendor_bill", "data"],
        }
        prompt = build_email_prompt(
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
            email_body=email_body,
        )
        provider = ai_configuration_service.resolve_provider(company=company)
        request_id = uuid.uuid4().hex[:8]
        last_exception: Exception | None = None
        start = time.perf_counter()
        for attempt in range(effective_max_retries + 1):
            try:
                # Same ordering as file OCR: emit the final prompt before a
                # provider call that may fail before returning any response.
                logger.info(
                    "AI EXTRACTION DEBUG | source=email | request_id=%s | "
                    "provider=%s | model=%s\nPROMPT:\n%s",
                    request_id,
                    provider.__class__.__name__,
                    getattr(provider, "model", "unknown"),
                    prompt,
                )
                response = provider.generate_structured_json(
                    prompt=prompt, schema=schema, timeout=effective_timeout
                )
                # Same local terminal diagnostic as file extraction.  Email
                # content is already part of ``prompt`` for this flow.
                logger.info(
                    "AI EXTRACTION DEBUG | source=email | request_id=%s | "
                    "RAW AI RESPONSE:\n%s\nPARSED AI RESPONSE:\n%s",
                    request_id,
                    getattr(provider, "last_raw_response", ""),
                    json.dumps(response, ensure_ascii=False, indent=2, default=str),
                )
                if not isinstance(response, dict):
                    raise GeminiValidationException("AI email extraction did not return a JSON object.")
                if response.get("is_vendor_bill") is not True:
                    logger.info(
                        "Company AI email classified message as not a vendor bill — request_id=%s attempt=%d duration_ms=%.2f",
                        request_id, attempt + 1, (time.perf_counter() - start) * 1000,
                    )
                    return {"is_vendor_bill": False, "data": None}
                extracted_data = response.get("data")
                if not isinstance(extracted_data, dict):
                    raise GeminiValidationException(
                        "AI classified the email as a vendor bill but did not return extraction data."
                    )
                data = _normalize_result(extracted_data, header_keys, line_keys, include_line_items)
                data = _apply_datatype_normalization(data, header_types, line_types, line_keys)
                data = apply_calculated_values(data)
                data = _apply_template_default_values(data, requested_fields)
                data = apply_invoice_date_fallback(
                    data,
                    header_keys,
                    source="email",
                    email_received_at=email_received_at,
                )
                logger.info(
                    "AI EXTRACTION DEBUG | source=email | request_id=%s | "
                    "TEMPLATE-MAPPED RESULT:\n%s",
                    request_id,
                    json.dumps(data, ensure_ascii=False, indent=2, default=str),
                )
                if company is not None:
                    from audit.integration_alerts import mark_ai_healthy
                    mark_ai_healthy(company=company)
                logger.info(
                    "Company AI email extraction completed — request_id=%s attempt=%d duration_ms=%.2f",
                    request_id, attempt + 1, (time.perf_counter() - start) * 1000,
                )
                return {"is_vendor_bill": True, "data": data}
            except GeminiValidationException:
                raise
            except AIProviderError as exc:
                last_exception = exc
                if getattr(exc, "quota_exhausted", False):
                    classified = GeminiRateLimitException(f"AI provider quota exhausted: {exc}")
                    should_retry, wait_seconds = False, 0
                elif getattr(exc, "rate_limited", False):
                    classified = GeminiRateLimitException(f"AI provider rate limit exceeded: {exc}")
                    should_retry, wait_seconds = True, 15
                elif getattr(exc, "retryable", False):
                    classified = GeminiTimeoutException(f"AI provider request timed out: {exc}") if getattr(exc, "status_code", None) in {408, 504} else GeminiConnectionException(f"AI provider temporary request failure: {exc}")
                    should_retry, wait_seconds = True, min(2 ** attempt, 8)
                else:
                    classified = GeminiValidationException(f"AI provider request failed: {exc}")
                    should_retry, wait_seconds = False, 0
                if not should_retry or attempt >= effective_max_retries:
                    if company is not None:
                        from audit.integration_alerts import report_ai_connection_failure
                        report_ai_connection_failure(company=company, error=exc)
                    raise classified from exc
                time.sleep(wait_seconds)
            except Exception as exc:
                last_exception = exc
                if attempt >= effective_max_retries:
                    raise GeminiConnectionException(f"AI provider request failed: {exc}") from exc
        raise GeminiConnectionException(f"AI extraction failed: {last_exception}") from last_exception

ai_extractor = AIExtractor()
