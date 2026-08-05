"""
Low-confidence field review prompts for Gemini.

Used as a second pass when the initial extraction has low confidence
for specific fields. Instructs Gemini to re-evaluate only those fields.
"""

from __future__ import annotations

#: Review prompt with a ``{low_confidence_fields}`` placeholder.
REVIEW_PROMPT: str = (
    "Review the following document extraction result.\n"
    "The following fields have low confidence: {low_confidence_fields}.\n"
    "Please re-examine the document image and provide corrected values "
    "for these fields only.\n"
    "Return ONLY valid JSON with the corrected fields.\n"
    "If the original value was correct, return it unchanged.\n"
    "No markdown. No explanation."
)
