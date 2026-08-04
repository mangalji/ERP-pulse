"""
Prompt templates for Gemini OCR extraction.

All prompts are stored here as module-level constants so they are
never hardcoded inside service or client code. This makes them
auditable, translatable, and easy to version-control.

Each template is a plain string with ``{placeholders}`` that are
filled by the calling code.
"""

from __future__ import annotations

#: System-level instruction for the Gemini model.
#: This is the "persona" prompt — it tells the model what role to
#: adopt and how to behave.
SYSTEM_PROMPT: str = (
    "You are a precise invoice OCR extraction engine. "
    "Your only task is to read invoice images and extract structured data. "
    "You never invent data, never guess, never add explanations."
)

#: The main extraction prompt. Instructs Gemini to return a JSON
#: object with specific fields. The ``{image_context}`` placeholder
#: can be used to pass additional context (e.g. the filename or
#: upload ID) if needed.
#:
#: The prompt explicitly forbids:
#: - Markdown formatting
#: - Explanatory text
#: - Invented or default values
#: - Non-JSON output
EXTRACTION_PROMPT: str = (
    "Extract the following fields from this invoice image."
    " Return ONLY valid JSON. No markdown. No explanation. No code blocks.\n\n"
    "Required JSON structure:\n"
    "{\n"
    '  "vendor": "",\n'
    '  "invoice_number": "",\n'
    '  "invoice_date": "",\n'
    '  "currency": "",\n'
    '  "subtotal": 0,\n'
    '  "tax": 0,\n'
    '  "total": 0,\n'
    '  "purchase_order": "",\n'
    '  "items": [],\n'
    '  "confidence": {}\n'
    "}\n\n"
    "Rules:\n"
    "1. Preserve exact values as they appear on the invoice.\n"
    "2. Use null (not empty string, not 0) for missing values.\n"
    "3. Invoice date format: YYYY-MM-DD.\n"
    "4. Currency: ISO 4217 three-letter code (e.g. USD, EUR, INR).\n"
    "5. Items should be an array of objects with keys: "
    "description, quantity, unit_price, total.\n"
    "6. For each field, include a confidence score (0.0 to 1.0) "
    "in the confidence object.\n"
    "7. Never invent or default any value. If unsure, use null.\n"
    "8. Return ONLY the JSON object. No other text.\n"
    "9. Numeric fields must be numbers, not strings.\n"
    "10. Preserve original formatting for text fields."
)

#: Confidence validation prompt. Used as a second pass when the
#: initial extraction has low confidence for some fields.
#: Instructs Gemini to re-evaluate specific fields.
REVIEW_PROMPT: str = (
    "Review the following invoice extraction result.\n"
    "The following fields have low confidence: {low_confidence_fields}.\n"
    "Please re-examine the invoice image and provide corrected values "
    "for these fields only.\n"
    "Return ONLY valid JSON with the corrected fields.\n"
    "If the original value was correct, return it unchanged.\n"
    "No markdown. No explanation."
)