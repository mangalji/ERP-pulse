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

FIELD_DESCRIPTIONS = {
    "invoice_number":( # field_id = tranid
        "Invoice number or ID printed on the supplier invoice. "
        "Do not use a purchase order number or vendor ID."
        ),
    "invoice_date": ( # field_id = trandate
        "Invoice issue date, normalized format YYYY-MM-DD when unambiguous."
        ),
    "due_date": ( # field_id = duedate
        "Payment due date, normalized to YYYY-MM-DD when stated. "
        "Do not calculate or guess a missing due date, except for the "
        "single-date fallback explicitly stated in the extraction rules."
        ),
    "vendor_name": ( # field_id = entity
        "Name of the vendor or supplier issuing the invoice."
        ),
    "subsidiary": ( # field_id = subsidiary
        "Company subsidiary or business unit, only when explicitly "
        "identified. Do not guess."
        ),
    "location": (
        "NetSuite Location, branch, site, or warehouse for this Vendor Bill. "
        "Use the exact name only when explicitly stated on the invoice. "
        "Do not infer a Location from an address or guess a default; return "
        "null when the invoice does not identify one."
    ),    
    "currency": ( # field_id = currency
        "Three-letter currency code, such as USD, INR, or EUR. "
        "Return null if the currency cannot be identified reliably."
        ),
    "total_tax_amount":( # field_id = taxtotal
        "Total tax amount for the entire invoice. Use the invoice-level "
        "tax total when shown; otherwise sum line-item taxes only when "
        "all relevant line tax amounts are available. "
        "Return a number without a currency symbol."
        ),
    "amount": ( # field_id = usertotal
        "Grand total of the entire invoice after discounts and including "
        "applicable taxes and charges, as shown on the invoice. "
        "Return a number without a currency symbol. Do not substitute "
        "an individual line amount."
        ),
}

LINE_ITEM_FIELDS = {
    "item": ( # field_id = item
        "Product, service, or charge name/description for this specific "
        "invoice line. Do not combine separate line items."
        ),
    "quantity": ( # field_id = quantity
        "Quantity for this line item. Return a number; do not guess "
        "if the quantity is not shown."
        ),
    "unit_price": ( # field_id = rate
        "Price per unit for this line item as printed on the invoice. "
        "Return a number without a currency symbol; do not calculate "
        "a missing unit price."
        ),
    "subtotal": ( # field_id = amount
        "This line item's amount before tax, after any stated line-level "
        "discounts. This is not the invoice-level subtotal. "
        "Return a number without a currency symbol."
        ),
    "tax_amount": ( # field_id = tax1amt
        "Tax amount attributable to this specific line item, not the "
        "tax total for the entire invoice. Return a number without "
        "a currency symbol."
        ),
    "tax_rate": ( # field_id = taxrate1
        "Tax rate for this line item, expressed as a percentage when "
        "explicitly stated, for example 18 for 18%. Do not guess "
        "a missing rate."
        ),
    "total_amount":( # field_id = grossamt
        "Final amount for this specific line item, including its "
        "applicable taxes and line-level charges after discounts. "
        "This is not the invoice grand total. Return a number "
        "without a currency symbol."
        )
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
                key = _slugify_field_key(str(custom.get("key") or label))
                target = line_defaults if custom.get("scope") == "line" else header_defaults
                target[key] = value

    return header_defaults, line_defaults


def _apply_template_default_values(
    data: dict[str, Any],
    requested_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply configured template values after extraction.

    A configured default is intentional business configuration, not a fallback:
    it always replaces the AI-extracted value for that field.
    """
    header_defaults, line_defaults = _configured_field_defaults(requested_fields)
    if not header_defaults and not line_defaults:
        return data

    result = dict(data)
    for key, value in header_defaults.items():
        result[key] = value

    if line_defaults and isinstance(result.get("line_items"), list):
        result["line_items"] = [
            (
                {
                    **line,
                    **{
                        key: value
                        for key, value in line_defaults.items()
                    },
                }
                if isinstance(line, dict)
                else line
            )
            for line in result["line_items"]
        ]

    return result


def _apply_email_received_date_fallback(
    data: dict[str, Any],
    header_keys: tuple[str, ...],
    *,
    email_received_at: datetime | None,
) -> dict[str, Any]:
    """Apply the mailbox receipt date as the invoice date for email input.

    The email receipt time is application-owned evidence, unlike a value
    inferred by the model. The automated-email workflow defines the mailbox
    receipt date as the invoice date, so it deliberately overrides an AI
    extracted value and a template default. A source-provided due date remains
    untouched and optional.
    """
    if "invoice_date" not in header_keys:
        return data
    if email_received_at is None:
        return data

    received_date = (
        timezone.localtime(email_received_at).date()
        if timezone.is_aware(email_received_at)
        else email_received_at.date()
    )
    data["invoice_date"] = received_date.isoformat()
    return data


def _build_email_vendor_bill_prompt(*, extraction_contract: str, email_body: str) -> str:
    """Build the email-only extraction instruction without changing file OCR.

    NetSuite sender-email resolution has already established the vendor before
    this prompt is used.  A known vendor can still send ordinary messages, so
    this one email-specific request both classifies the message and extracts
    data only when the message is a vendor-bill instruction.
    """
    return f"""You are assessing an email from a known NetSuite vendor for a possible Vendor Bill.
The sender has already been matched to an active NetSuite vendor, but that alone
does NOT mean this particular message is a vendor bill.

First decide whether the message represents a concrete billable purchase,
invoice, order, supply request, charge, or payment request. Return
"is_vendor_bill": true only when all of the following are supported by the
email:
1. there is clear transaction or procurement intent;
2. at least one specific product or service is being requested, supplied, or
   billed; and
3. at least one commercial detail is present for a line: quantity, rate/price,
   amount, or an explicit statement that the line is free or zero-value.

Return "is_vendor_bill": false for ordinary follow-ups, reminders, delivery
status questions, availability or price enquiries, general discussions, or
messages that merely reference a prior invoice/order without requesting,
supplying, or billing a concrete line. When false, return data as null and do
not attempt extraction.

When true, extract the information present in the email body into the
configured schema. Email messages can be invoices, purchase instructions,
short requests, conversational prose, tables, or a mixture of formats.

Identify every distinct product or service line that is explicitly supported by
the message, even when the information is written naturally rather than in
columns.
Where the configured extraction contract refers to visible source rows, cells,
or columns, interpret that for an email as each separately described product or
service in prose or a table. Do not require a tabular layout.

For each line, return only values that the message supports:
- identify the product or service name;
- extract quantity when stated; a missing quantity is valid for services;
- extract a unit rate or price when stated; a missing price is valid for a
  no-charge item or service;
- preserve an explicit line amount; when a requested amount is not explicitly
  present, leave that field empty rather than deriving it;
- do not use zero for a missing number unless the message explicitly states
  that the line is free or has a zero value.

The mailbox received date is supplied by the application and is always the
invoice date. Extract a due date only when the email explicitly provides one.
Vendor identity is supplied by the matched NetSuite vendor, so do not infer or
replace it from email text. Subsidiary and location are optional email values
and may be populated later from the matched vendor.

{extraction_contract}

EMAIL BODY START
{email_body}
EMAIL BODY END
"""

def build_prompt(
    header_fields: dict[str, str],
    line_fields: dict[str, str],
    include_line_items: bool,
    header_types: dict[str, str],
    line_types: dict[str, str],
    *,
    fallback_invoice_date: str | None = None,
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
        line_item_rules = """- Extract EVERY clearly separated source row that is visibly present in the document.
- Preserve source-row order; each line_items entry must correspond to one visible source row.
- Never merge, collapse, skip, duplicate, or summarize separate rows.
- Read each requested line field from its own corresponding source cell/column for that row.
- Do not fill a missing line field by copying a value from another row, header, footer, or nearby column.
- Extract only values that are directly supported by the source. Do not perform arithmetic for subtotal, tax, or totals; leave a derived field null when it is not explicitly shown. The application calculates derived financial fields deterministically after extraction.
- If a requested line field has no directly supported value in that source row, return null for that field.
- Preserve complete visible row information only within the fields the template requested.
- Before finalizing, recount visible source rows and compare that count with line_items."""
    else:
        line_items_section = ""
        line_item_rules = "- Do not return line_items because no line fields were requested."
    date_fallback_rule = ""
    if {"invoice_date", "due_date"}.issubset(header_fields):
        reference_date = fallback_invoice_date or timezone.localdate().isoformat()
        date_fallback_rule = f"""- Single-date fallback: apply this only when the source explicitly contains exactly one relevant bill/invoice date and does not explicitly contain a second invoice/bill or due date. Preserve that source date as `due_date` and set `invoice_date` to `{reference_date}`. This is the current date for a file or the email's received date for an email. Do not apply this fallback when both dates are explicitly present, and never overwrite an explicitly stated date.
"""
    return f"""You are the PRIMARY extraction stage of a production business-document extraction system.
Read the attached document in full. Layouts vary widely across invoices, receipts, purchase orders, vouchers, credit notes, debit notes, and other business documents.

Top-level fields requested by the user's template:
{field_lines}
{line_items_section}
Rules:
- Respond with ONLY one valid JSON object.
- Use EXACTLY the requested field names and structure; do not add extra keys.
- The configured template is the complete field contract. Extract only the fields listed above.
- Use each field's questionaire/instruction as the definition of what information to extract.
- NEVER invent, assume, calculate, or guess a requested value.
- Extract a value only when it is directly supported by the source document for that exact field.
- Do not derive one field from another field, even when the arithmetic seems obvious.
- Do not substitute a nearby or similarly named value when the requested field's own value is absent.
- Use null when the requested value is missing, unreadable, ambiguous, or cannot be directly matched to source evidence.
- Inspect the entire document before deciding a field is null.
- Follow the declared datatype for every field.
{date_fallback_rule}{line_item_rules}
- Do not output fields merely because other information is visible in the document; unrequested fields must be omitted.
- The final JSON must contain exactly the header fields and line-item fields defined by this template.
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
                result = apply_calculated_values(result)
                result = _apply_template_default_values(result, requested_fields)

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
        extraction_prompt = build_prompt(
            header_fields,
            line_fields,
            include_line_items,
            header_types,
            line_types,
            fallback_invoice_date=(
                timezone.localtime(email_received_at).date().isoformat()
                if email_received_at and timezone.is_aware(email_received_at)
                else email_received_at.date().isoformat()
                if email_received_at
                else None
            ),
        )
        prompt = _build_email_vendor_bill_prompt(
            extraction_contract=extraction_prompt,
            email_body=email_body,
        )
        provider = ai_configuration_service.resolve_provider(company=company)
        request_id = uuid.uuid4().hex[:8]
        last_exception: Exception | None = None
        start = time.perf_counter()
        for attempt in range(effective_max_retries + 1):
            try:
                response = provider.generate_structured_json(
                    prompt=prompt, schema=schema, timeout=effective_timeout
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
                data = _apply_email_received_date_fallback(
                    data,
                    header_keys,
                    email_received_at=email_received_at,
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
