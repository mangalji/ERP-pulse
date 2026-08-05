"""
Layout analysis for the IDP engine.

Detects document regions (header, footer, vendor/customer block,
address, GST block, invoice metadata, totals, item table, notes,
signatures) from raw OCR text using line/anchor heuristics. Preserves
region names and text; bounding boxes are populated when available.
"""

from __future__ import annotations

import re
from ocr.utils import logger

#: Anchor patterns → region label.
REGION_ANCHORS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(invoice\s*no|invoice\s*number|bill\s*no)\b', re.I), 'invoice_metadata'),
    (re.compile(r'\b(invoice\s*date|bill\s*date|date\s*of\s*issue)\b', re.I), 'invoice_metadata'),
    (re.compile(r'\b(gstin|gst\s*no|gst\s*number|cgst|sgst|igst)\b', re.I), 'gst_block'),
    (re.compile(r'\b(total|grand\s*total|amount\s*payable|net\s*amount)\b', re.I), 'totals'),
    (re.compile(r'\b(subtotal|sub\s*total)\b', re.I), 'totals'),
    (re.compile(r'\bshipped?\s*to\b', re.I), 'customer_block'),
    (re.compile(r'\bbill\s*to\b', re.I), 'customer_block'),
    (re.compile(r'\bsold\s*by\b', re.I), 'vendor_block'),
    (re.compile(r'\bvendor\b', re.I), 'vendor_block'),
    (re.compile(r'\b(supplied?\s*by|from)\b', re.I), 'vendor_block'),
    (re.compile(r'\baddress\b', re.I), 'address'),
    (re.compile(r'\bdelivery\s*address\b', re.I), 'address'),
    (re.compile(r'\bqty|quantity|unit\s*price|rate\b', re.I), 'item_table'),
    (re.compile(r'\b(terms|notes|remarks|comment)\b', re.I), 'notes'),
    (re.compile(r'\bsignature|authorized\s*signatory\b', re.I), 'signature'),
]


class LayoutService:
    """
    Detect document layout regions from raw OCR text.
    """

    def analyze(self, *, raw_text: str) -> dict:
        """
        Analyze raw OCR text and return detected layout blocks.

        Args:
            raw_text: Raw OCR text (may be multi-line).

        Returns:
            Dict mapping region label → list of blocks, plus a
            ``bbox`` map when coordinates are available.
        """
        normalized = re.sub(r'\s+', ' ', raw_text or '').lower()
        blocks: dict[str, list[str]] = {}
        bbox: dict[str, list] = {}

        for pattern, label in REGION_ANCHORS:
            matches = pattern.findall(normalized)
            if matches:
                blocks.setdefault(label, []).append(matches[0])
                bbox.setdefault(label, []).append({'text': matches[0]})

        # Header: first non-empty line.
        lines = [ln.strip() for ln in (raw_text or '').splitlines() if ln.strip()]
        if lines:
            blocks.setdefault('header', []).append(lines[0])

        # Footer: last non-empty line.
        if len(lines) > 1:
            blocks.setdefault('footer', []).append(lines[-1])

        logger.info('Layout analysis — regions=%s', list(blocks.keys()))
        return {'blocks': blocks, 'bbox': bbox}


layout_service = LayoutService()
