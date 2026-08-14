"""
Notebook-compatible Gemini document extraction service.

This service ports the extraction logic from the approved Colab prototype
into the ERP Pulse application without changing the existing OCR upload
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


# Canonical output contract used by the ERP Pulse OCR feature.
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


def _json_object_schema() -> dict[str, Any]:
    return EXTRACTION_SCHEMA


def _audit_schema() -> dict[str, Any]:
    return AUDIT_SCHEMA


def _normalize_result(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize the model response to the approved output contract.

    Missing top-level keys are explicitly represented as None and line_items
    is always a list. This keeps the API/DB contract stable without inventing
    any values.
    """
    normalized = {
        key: data.get(key)
        for key in TOP_LEVEL_FIELDS
    }

    raw_items = data.get("line_items")
    normalized_items = []

    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue

            normalized_items.append(
                {
                    key: raw_item.get(key)
                    for key in LINE_ITEM_OUTPUT_FIELDS
                }
            )

    normalized["line_items"] = normalized_items
    return normalized


def _verification_is_needed(data: dict[str, Any]) -> bool:
    """
    Decide whether the first extraction deserves a second verification pass.

    High-value missing fields always trigger verification. A non-empty
    line-item set also triggers verification because missing/merged rows were
    an observed failure mode in the supplied test documents.
    """
    if any(data.get(field) is None for field in VERIFICATION_FIELDS):
        return True

    if data.get("line_items"):
        return True

    return False


def _merge_corrected_result(
    candidate: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply only evidence-backed corrections.

    A verifier is never allowed to erase a non-null primary value merely by
    returning null. Scalar corrections are applied when the primary value is
    null. Line items are replaced only when the verifier found a larger or
    clearly corrected row set; individual missing fields in line items are
    filled from the verifier when the primary field is null.
    """
    merged = _normalize_result(candidate)

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

        if field in TOP_LEVEL_FIELDS:
            # Primary non-null values are retained unless the verifier can
            # provide a concrete replacement. A null verifier value is never
            # allowed to destroy a concrete primary value.
            if merged.get(field) is None and corrected_value is not None:
                merged[field] = corrected_value
            elif (
                merged.get(field) is not None
                and corrected_value is not None
                and field in {"invoice_number", "invoice_date", "due_date",
                              "vendor_name", "customer_name", "subsidiary",
                              "currency", "payment_terms"}
            ):
                # For textual/date fields, a concrete verifier correction can
                # replace the primary only when it is explicitly reported as
                # a correction. Numeric fields remain conservative.
                merged[field] = corrected_value

        elif field == "line_items" and isinstance(corrected_value, list):
            candidate_items = merged.get("line_items") or []

            # Prefer the verifier when it found more source rows.
            if len(corrected_value) > len(candidate_items):
                merged["line_items"] = _normalize_result(
                    {"line_items": corrected_value}
                )["line_items"]
                continue

            # Otherwise fill missing fields and prefer longer descriptions.
            if len(corrected_value) == len(candidate_items):
                merged_items = []
                for index, candidate_item in enumerate(candidate_items):
                    verifier_item = corrected_value[index]
                    merged_item = dict(candidate_item)

                    for key in LINE_ITEM_OUTPUT_FIELDS:
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

    return _normalize_result(merged)



# def build_prompt() -> str:
#     """Build the extraction prompt using the notebook's field definitions."""
#     field_lines = "\n".join(
#         f'- "{key}": {description}'
#         for key, description in FIELD_DESCRIPTIONS.items()
#     )
#     item_lines = "\n".join(
#         f'  - "{key}": {description}'
#         for key, description in LINE_ITEM_FIELDS.items()
#     )

#     return f"""You are an accounting data-extraction assistant. Read the attached document
# (it may be an invoice, receipt, purchase order, or similar business document; layout and
# format may vary widely) and extract the following fields.

# Top-level fields:
# {field_lines}

# Also extract a "line_items" list, where each item has:
# {item_lines}

# Rules:
# - Respond with ONLY a single valid JSON object, no markdown fences, no commentary.
# - If a field is not present in the document, use null (do not guess).
# - Numbers must be plain numbers (no currency symbols or thousands separators).
# - For line_items, extract EVERY clearly separated line, row, item, expense, account row, or service row that belongs to the document's itemized/table section.
# - Preserve each source row as a separate line_item. Never omit, merge, combine, collapse, or summarize multiple source rows into one line_item.
# - Preserve the original order of the source rows.
# - Preserve the COMPLETE information belonging to each source row. Do NOT shorten, paraphrase, summarize, truncate, normalize, or rewrite the row description. The line_item "description" must contain all relevant text visible in that row, including account names, references, memos, identifiers, tax references, names, and other descriptive text that belongs to the row.
# - If the row contains information that does not have a dedicated output field, keep that information inside "description" rather than dropping it.
# - Use null only when a requested field is genuinely absent or cannot be determined from the document. Do not use null when the value is visibly present elsewhere on the page or can be directly associated with the field.
# - For top-level fields, inspect the ENTIRE document, including the header, company block, metadata area, totals, and tables. If a value is explicitly present, extract it even if the document is not technically an invoice.
# - For vendor_name, use the explicitly identified vendor/supplier/payee/issuer when the document identifies one. Do not leave it null merely because the document is a voucher or other business document.
# - For subsidiary, use the explicitly stated subsidiary/business entity when present. If the document contains the company name and identifies it as the subsidiary/entity, preserve that value.
# - For tabular documents, use the visible row boundaries and column structure when determining line_items; do not infer a reduced number of rows from totals, semantic similarity, or arithmetic relationships.
# - Before returning the JSON, perform a final completeness check:
#   1. Count the clearly separated source rows in the itemized/table section.
#   2. Ensure the number of line_items matches that row count whenever a clear table exists.
#   3. Ensure every line_item description contains the complete relevant text from its corresponding source row.
#   4. Ensure no visible top-level value has been unnecessarily returned as null.
# - These rules improve extraction completeness only. Keep the existing JSON fields, field names, data types, and overall response structure unchanged.
# - If there are no clearly separated line items, return line_items as an empty list.
# - JSON shape exactly:
# {{
#   "invoice_number": ..., "invoice_date": ..., "due_date": ..., "vendor_name": ...,
#   "customer_name": ..., "subsidiary": ..., "currency": ..., "subtotal": ...,
#   "tax_amount": ..., "tax_rate": ..., "total_amount": ..., "payment_terms": ...,
#   "line_items": [{{"description": ..., "quantity": ..., "unit_price": ..., "amount": ...}}]
# }}
# """

# EXTRACTION_PROMPT = build_prompt()

def build_prompt() -> str:
    """Build the extraction prompt using the notebook's field definitions."""
    field_lines = "\n".join(
        f'- "{key}": {description}'
        for key, description in FIELD_DESCRIPTIONS.items()
    )
    item_lines = "\n".join(
        f'  - "{key}": {description}'
        for key, description in LINE_ITEM_FIELDS.items()
    )

    return f"""You are the PRIMARY extraction stage of a production accounting document extraction system.
Read the attached document in full. The document may be an invoice, receipt, purchase order,
payment voucher, journal voucher, bank transfer voucher, credit note, debit note, or another
business document. Layouts vary widely.

Top-level fields:
{field_lines}

Line-item fields:
{item_lines}

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
- For line_items, extract EVERY clearly separated source row.
- Preserve source-row order.
- Never merge, collapse, skip, or summarize separate rows.
- Preserve the COMPLETE visible row information in description.
- Do not shorten or paraphrase descriptions.
- Before finalizing, re-scan the document once more for top-level fields that are still null.
- Before finalizing, recount source rows and compare that count with line_items.
- Keep line_items=[] only when no clearly separated source rows exist.
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

    def extract(self, file_path: str | Path, mime_type: str | None = None) -> dict:
        """Read the original file bytes and extract structured JSON with Gemini."""
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
                    contents=[file_part, EXTRACTION_PROMPT],
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_json_object_schema(),
                        temperature=0,
                        seed=42,
                    ),
                )

                response_text = getattr(response, "text", None)
                result = _normalize_result(
                    parse_json_response(response_text or "")
                )
                if _verification_is_needed(result):
                    audit = self._verify_extraction(
                        genai=genai,
                        client=client,
                        file_part=file_part,
                        candidate=result,
                        request_id=request_id,
                        )
                    if audit is None:
                        result = _merge_corrected_result(
                            result,audit,
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
