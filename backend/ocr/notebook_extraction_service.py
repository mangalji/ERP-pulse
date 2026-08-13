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

    return f"""You are an accounting data-extraction assistant. Read the attached document
(it may be an invoice, receipt, purchase order, or similar business document; layout and
format may vary widely) and extract the following fields.

Top-level fields:
{field_lines}

Also extract a "line_items" list, where each item has:
{item_lines}

Rules:
- Respond with ONLY a single valid JSON object, no markdown fences, no commentary.
- If a field is not present in the document, use null (do not guess).
- Numbers must be plain numbers (no currency symbols or thousands separators).
- For line_items, extract EVERY clearly separated line, row, item, expense, account row, or service row that belongs to the document's itemized/table section.
- Preserve each source row as a separate line_item. Never omit, merge, combine, collapse, or summarize multiple source rows into one line_item.
- Preserve the original order of the source rows.
- Preserve the COMPLETE information belonging to each source row. Do NOT shorten, paraphrase, summarize, truncate, normalize, or rewrite the row description. The line_item "description" must contain all relevant text visible in that row, including account names, references, memos, identifiers, tax references, names, and other descriptive text that belongs to the row.
- If the row contains information that does not have a dedicated output field, keep that information inside "description" rather than dropping it.
- Use null only when a requested field is genuinely absent or cannot be determined from the document. Do not use null when the value is visibly present elsewhere on the page or can be directly associated with the field.
- For top-level fields, inspect the ENTIRE document, including the header, company block, metadata area, totals, and tables. If a value is explicitly present, extract it even if the document is not technically an invoice.
- For vendor_name, use the explicitly identified vendor/supplier/payee/issuer when the document identifies one. Do not leave it null merely because the document is a voucher or other business document.
- For subsidiary, use the explicitly stated subsidiary/business entity when present. If the document contains the company name and identifies it as the subsidiary/entity, preserve that value.
- For tabular documents, use the visible row boundaries and column structure when determining line_items; do not infer a reduced number of rows from totals, semantic similarity, or arithmetic relationships.
- Before returning the JSON, perform a final completeness check:
  1. Count the clearly separated source rows in the itemized/table section.
  2. Ensure the number of line_items matches that row count whenever a clear table exists.
  3. Ensure every line_item description contains the complete relevant text from its corresponding source row.
  4. Ensure no visible top-level value has been unnecessarily returned as null.
- These rules improve extraction completeness only. Keep the existing JSON fields, field names, data types, and overall response structure unchanged.
- If there are no clearly separated line items, return line_items as an empty list.
- JSON shape exactly:
{{
  "invoice_number": ..., "invoice_date": ..., "due_date": ..., "vendor_name": ...,
  "customer_name": ..., "subsidiary": ..., "currency": ..., "subtotal": ...,
  "tax_amount": ..., "tax_rate": ..., "total_amount": ..., "payment_terms": ...,
  "line_items": [{{"description": ..., "quantity": ..., "unit_price": ..., "amount": ...}}]
}}
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
        self.timeout = getattr(settings, "OCR_TIMEOUT", 60)
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
                    ),
                )

                response_text = getattr(response, "text", None)
                result = parse_json_response(response_text or "")

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

                if "429" in error_lower or "resource_exhausted" in error_lower or "quota" in error_lower:
                    classified = GeminiRateLimitException(
                        f"Gemini API rate limit exceeded: {error_text}"
                    )
                    wait_seconds = 15
                elif "timeout" in error_lower or "deadline" in error_lower:
                    classified = GeminiTimeoutException(
                        f"Gemini API request timed out: {error_text}"
                    )
                    wait_seconds = 3
                else:
                    classified = GeminiConnectionException(
                        f"Gemini API request failed: {error_text}"
                    )
                    wait_seconds = 3

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
