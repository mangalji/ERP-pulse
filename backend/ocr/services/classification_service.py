"""
Document classification for the IDP engine.

Detects the business document type (Invoice, Purchase Order, Sales
Order, Credit Note, Debit Note, Receipt, etc.) from the raw OCR text.
The classifier is keyword/pattern based and deterministic — no AI is
involved, keeping classification fast and predictable.
"""

from __future__ import annotations

import re
from ocr.models import DocumentType
from ocr.utils import logger

#: Mapping of document type → list of strong keyword patterns.
#: Patterns are lowercased and matched against normalized OCR text.
TYPE_KEYWORDS: dict[str, list[str]] = {
    DocumentType.INVOICE: [
        'invoice', 'tax invoice', 'bill', 'receipt of sale',
    ],
    DocumentType.PURCHASE_ORDER: [
        'purchase order', 'po number', 'order no', 'purchase requisition',
    ],
    DocumentType.SALES_ORDER: [
        'sales order', 'so number', 'order confirmation', 'sales confirmation',
    ],
    DocumentType.CREDIT_NOTE: [
        'credit note', 'credit memo', 'credit note no',
    ],
    DocumentType.DEBIT_NOTE: [
        'debit note', 'debit memo', 'debit note no',
    ],
    DocumentType.RECEIPT: [
        'receipt', 'payment receipt', 'cash receipt', 'money receipt',
    ],
    DocumentType.DELIVERY_CHALLAN: [
        'delivery challan', 'delivery note', 'dc no', 'challan',
    ],
    DocumentType.PACKING_LIST: [
        'packing list', 'packing slip', 'packing note',
    ],
}

#: Strength weights: a type must accrue at least this score to win.
MIN_SCORE = 1

#: Number of keyword occurrences to count (cap to avoid pathological docs).
MAX_COUNT = 5


class ClassificationService:
    """
    Deterministic document type classification from OCR text.
    """

    def classify(self, *, raw_text: str) -> dict:
        """
        Classify the document type from raw OCR text.

        Args:
            raw_text: Concatenated raw OCR text for the document.

        Returns:
            Dict with ``document_type`` and ``confidence``.
        """
        normalized = re.sub(r'\s+', ' ', raw_text or '').lower()
        scores: dict[str, float] = {}

        for doc_type, keywords in TYPE_KEYWORDS.items():
            score = 0.0
            for keyword in keywords:
                # Count capped occurrences of the keyword.
                count = min(normalized.count(keyword), MAX_COUNT)
                if count:
                    # Longer keywords are stronger signals.
                    score += min(count, 3) * (1.0 + len(keyword.split()) * 0.2)
            if score > 0:
                scores[doc_type] = score

        if not scores:
            return {
                'document_type': DocumentType.UNKNOWN,
                'confidence': 0.0,
            }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        total = sum(scores.values()) or 1.0
        confidence = min(1.0, best_score / total)

        logger.info('Classified document — type=%s score=%.2f', best_type, confidence)
        return {
            'document_type': best_type,
            'confidence': round(confidence, 4),
        }


classification_service = ClassificationService()
