"""
Receipt extraction prompts for Gemini.

Provides the system persona and the structured extraction prompt used
for Receipt documents. Returns a JSON object with receipt-specific
fields and per-field confidence.
"""

from __future__ import annotations

#: System-level persona for Receipt extraction.
SYSTEM_PROMPT: str = (
    "You are a precise receipt OCR extraction engine. "
    "Your only task is to read receipt images and extract structured data. "
    "You never invent data, never guess, never add explanations."
)

#: The main receipt extraction prompt.
EXTRACTION_PROMPT: str = (
    "Extract the following fields from this receipt image."
    " Return ONLY valid JSON. No markdown. No explanation. No code blocks.\n\n"
    "Required JSON structure:\n"
    "{\n"
    '  "merchant": "",\n'
    '  "receipt_number": "",\n'
    '  "receipt_date": "",\n'
    '  "currency": "",\n'
    '  "subtotal": 0,\n'
    '  "tax": 0,\n'
    '  "total": 0,\n'
    '  "payment_method": "",\n'
    '  "items": [],\n'
    '  "confidence": {}\n'
    "}\n\n"
    "Rules:\n"
    "1. Preserve exact values as they appear on the receipt.\n"
    "2. Use null (not empty string, not 0) for missing values.\n"
    "3. Date format: YYYY-MM-DD.\n"
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
