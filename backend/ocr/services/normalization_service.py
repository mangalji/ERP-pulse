"""
Normalization for the IDP engine.

Normalizes the raw OCR/Gemini extraction output into a canonical
``normalized_json`` shape that downstream consumers (NetSuite payload
builder, reporting) can rely on. All monetary values are floats,
dates are ISO 8601 strings, and lists are normalized item objects.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from ocr.utils import logger

#: Aliases for the invoice number field.
INVOICE_NO_KEYS = ('invoice_number', 'invoice_no', 'bill_no', 'number')

#: Aliases for the invoice date field.
INVOICE_DATE_KEYS = ('invoice_date', 'date', 'bill_date', 'issue_date')

#: Aliases for the vendor field.
VENDOR_KEYS = ('vendor', 'vendor_name', 'supplier', 'seller')

#: Aliases for monetary fields.
SUB_TOTAL_KEYS = ('subtotal', 'sub_total', 'net_amount')
TAX_KEYS = ('tax', 'total_tax', 'vat', 'gst')
TOTAL_KEYS = ('total', 'grand_total', 'amount_payable', 'net_total')

#: Aliases for currency.
CURRENCY_KEYS = ('currency', 'currency_code', 'iso_currency')

#: Aliases for purchase order.
PO_KEYS = ('purchase_order', 'po_number', 'po_no', 'order_no')


class NormalizationService:
    """
    Normalize extracted data into a canonical document shape.
    """

    def normalize(self, *, raw: dict, document_type: str) -> dict:
        """
        Normalize a raw extraction dict into canonical form.

        Args:
            raw: The raw extracted data (from Gemini/OCR).
            document_type: The detected document type.

        Returns:
            A normalized dict with guaranteed keys:
            vendor, invoice_number, invoice_date, currency, subtotal,
            tax, total, purchase_order, items, document_type.
            Any extra fields from ``raw`` (e.g. custom fields) are
            preserved unchanged so dynamic extraction configurations
            are not silently dropped.
        """
        logger.info('Normalizing extracted data — document_type=%s', document_type)

        items = self._normalize_items(raw.get('items', []))

        normalized = {
            'vendor': self._first_nonempty(raw, VENDOR_KEYS),
            'invoice_number': self._first_nonempty(raw, INVOICE_NO_KEYS),
            'invoice_date': self._normalize_date(self._first_nonempty(raw, INVOICE_DATE_KEYS)),
            'currency': self._normalize_currency(self._first_nonempty(raw, CURRENCY_KEYS)),
            'subtotal': self._to_money(self._first_nonempty(raw, SUB_TOTAL_KEYS)),
            'tax': self._to_money(self._first_nonempty(raw, TAX_KEYS)),
            'total': self._to_money(self._first_nonempty(raw, TOTAL_KEYS)),
            'purchase_order': self._first_nonempty(raw, PO_KEYS),
            'items': items,
            'document_type': document_type,
        }

        # Preserve any extra fields from the raw extraction (e.g. custom
        # fields from a dynamic Phase 2 configuration) so they are not
        # silently dropped by the normalization step.
        standard_keys = set(normalized.keys())
        for key, value in raw.items():
            if key not in standard_keys:
                normalized[key] = value

        # Compute totals from items if total is missing.
        if normalized['total'] is None and items:
            normalized['total'] = round(sum(i.get('total') or 0 for i in items), 2)

        if normalized['subtotal'] is None:
            normalized['subtotal'] = normalized['total']

        return normalized

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _first_nonempty(data: dict, keys: tuple) -> object:
        """Return the first non-empty value among ``keys``."""
        for key in keys:
            value = data.get(key)
            if value is not None and value != '' and value != []:
                return value
        return None

    @staticmethod
    def _normalize_date(value) -> str | None:
        """Normalize a date value to ISO ``YYYY-MM-DD`` or ``None``."""
        if value is None or value == '':
            return None
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')
        if isinstance(value, str):
            text = value.strip()
            # Already ISO.
            if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
                return text
            # M/D/YYYY or D/M/YYYY
            for fmt in ('%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d'):
                try:
                    return datetime.strptime(text, fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
        return None

    @staticmethod
    def _normalize_currency(value) -> str | None:
        """Normalize a currency code to uppercase ISO 4217 or ``None``."""
        if value is None:
            return None
        text = str(value).strip().upper()
        return text if len(text) == 3 else None

    @staticmethod
    def _to_money(value):
        """Convert a value to a non-negative float or ``None``."""
        if value is None or value == '':
            return None
        try:
            amount = float(Decimal(str(value).replace(',', '')))
        except (InvalidOperation, ValueError):
            return None
        return round(amount, 2)

    def _normalize_items(self, items) -> list:
        """Normalize a list of raw item dicts."""
        if not isinstance(items, list):
            return []
        normalized_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            cleaned = {
                'description': self._first_nonempty(item, ('description', 'name', 'product', 'item')),
                'quantity': self._to_number(self._first_nonempty(item, ('quantity', 'qty', 'qty_ordered'))),
                'unit_price': self._to_money(self._first_nonempty(item, ('unit_price', 'rate', 'price'))),
                'total': self._to_money(self._first_nonempty(item, ('total', 'amount', 'line_total'))),
            }
            if cleaned['total'] is None and cleaned.get('quantity') is not None and cleaned.get('unit_price') is not None:
                cleaned['total'] = round(cleaned['quantity'] * cleaned['unit_price'], 2)
            normalized_items.append(cleaned)
        return normalized_items

    @staticmethod
    def _to_number(value):
        """Convert a value to a number or ``None``."""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            try:
                return float(value)
            except (ValueError, TypeError):
                return None


normalization_service = NormalizationService()
