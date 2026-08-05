"""
Prompt templates for Gemini OCR extraction.

Prompts are split by document type into separate modules for auditability
and version control. This package re-exports the legacy single-module
names (``SYSTEM_PROMPT``, ``REVIEW_PROMPT``) plus the document-type
specific extraction prompts so existing imports keep working.

Modules:
    - invoice:         Invoice extraction prompts.
    - purchase_order:  Purchase Order extraction prompts.
    - receipt:         Receipt extraction prompts.
    - review:          Low-confidence review prompts.
    - business_rules:  Business-rule extraction prompts.
"""

from __future__ import annotations

from ocr.prompts.invoice import (
    EXTRACTION_PROMPT as INVOICE_EXTRACTION_PROMPT,
    SYSTEM_PROMPT as INVOICE_SYSTEM_PROMPT,
)
from ocr.prompts.purchase_order import (
    EXTRACTION_PROMPT as PO_EXTRACTION_PROMPT,
    SYSTEM_PROMPT as PO_SYSTEM_PROMPT,
)
from ocr.prompts.receipt import (
    EXTRACTION_PROMPT as RECEIPT_EXTRACTION_PROMPT,
    SYSTEM_PROMPT as RECEIPT_SYSTEM_PROMPT,
)
from ocr.prompts.review import REVIEW_PROMPT
from ocr.prompts.business_rules import BUSINESS_RULES_PROMPT

#: Backward-compatible aliases (legacy single-module names).
SYSTEM_PROMPT: str = INVOICE_SYSTEM_PROMPT
EXTRACTION_PROMPT: str = INVOICE_EXTRACTION_PROMPT

#: Document-type → extraction prompt mapping for the pipeline.
PROMPT_BY_DOCUMENT_TYPE: dict[str, str] = {
    'INVOICE': INVOICE_EXTRACTION_PROMPT,
    'PURCHASE_ORDER': PO_EXTRACTION_PROMPT,
    'RECEIPT': RECEIPT_EXTRACTION_PROMPT,
}

__all__ = [
    'SYSTEM_PROMPT',
    'EXTRACTION_PROMPT',
    'REVIEW_PROMPT',
    'BUSINESS_RULES_PROMPT',
    'INVOICE_SYSTEM_PROMPT',
    'INVOICE_EXTRACTION_PROMPT',
    'PO_SYSTEM_PROMPT',
    'PO_EXTRACTION_PROMPT',
    'RECEIPT_SYSTEM_PROMPT',
    'RECEIPT_EXTRACTION_PROMPT',
    'PROMPT_BY_DOCUMENT_TYPE',
]
