"""
Business-rule extraction prompts for Gemini.

Used to extract business-specific fields (e.g. GST, line-level tax,
discounts) that complement the core extraction. The prompt is
deliberately generic so it can be reused across document types.
"""

from __future__ import annotations

#: Business-rules extraction prompt with a ``{document_type}`` placeholder.
BUSINESS_RULES_PROMPT: str = (
    "From the {document_type} image, extract the following business fields.\n"
    "Return ONLY valid JSON with these keys where present (use null if "
    "a field is not on the document):\n"
    "{\n"
    '  "gstin": "",\n'
    '  "cgst": 0,\n'
    '  "sgst": 0,\n'
    '  "igst": 0,\n'
    '  "discount": 0,\n'
    '  "rounding": 0,\n'
    '  "shipping_charges": 0,\n'
    '  "payment_terms": ""\n'
    "}\n"
    "Do not invent values. Numeric fields must be numbers.\n"
    "Confidence scores are not required for these fields."
)
