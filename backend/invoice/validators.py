"""
Validation engine for invoice data.

Validates extracted invoice data before review/approval.
"""

import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


class InvoiceValidationError:
    """Single validation error."""
    def __init__(self, field, message):
        self.field = field
        self.message = message

    def to_dict(self):
        return {'field': self.field, 'message': self.message}


class InvoiceValidator:
    """Validate invoice extracted data."""

    REQUIRED_FIELDS = ['vendor', 'invoice_number', 'invoice_date', 'currency', 'total_amount']
    DATE_FORMAT = r'^\d{4}-\d{2}-\d{2}$'
    CURRENCY_LENGTH = 3

    def validate(self, data: dict) -> list[InvoiceValidationError]:
        """
        Validate invoice data.
        
        Args:
            data: Extracted invoice JSON
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Required fields
        for field in self.REQUIRED_FIELDS:
            if not data.get(field):
                errors.append(InvoiceValidationError(field, f'{field} is required'))
        
        # Date format
        invoice_date = data.get('invoice_date', '')
        if invoice_date and not re.match(self.DATE_FORMAT, str(invoice_date)):
            errors.append(InvoiceValidationError('invoice_date', 'Invalid date format (YYYY-MM-DD)'))
        
        # Currency
        currency = data.get('currency', '')
        if currency and len(str(currency)) != self.CURRENCY_LENGTH:
            errors.append(InvoiceValidationError('currency', 'Currency must be 3 characters (e.g., USD)'))
        
        # Numeric fields
        numeric_fields = ['total_amount', 'tax_amount', 'subtotal', 'gst']
        for field in numeric_fields:
            value = data.get(field)
            if value is not None and value != '':
                try:
                    Decimal(str(value))
                except (InvalidOperation, ValueError):
                    errors.append(InvoiceValidationError(field, f'{field} must be a valid number'))
        
        # Totals validation: subtotal + tax = total
        subtotal = data.get('subtotal')
        tax = data.get('tax_amount') or data.get('tax')
        total = data.get('total_amount')
        
        if subtotal is not None and tax is not None and total is not None:
            try:
                subtotal_dec = Decimal(str(subtotal))
                tax_dec = Decimal(str(tax))
                total_dec = Decimal(str(total))
                expected_total = subtotal_dec + tax_dec
                if abs(expected_total - total_dec) > Decimal('0.01'):
                    errors.append(InvoiceValidationError(
                        'total_amount',
                        f'Total ({total}) does not match subtotal ({subtotal}) + tax ({tax})'
                    ))
            except (InvalidOperation, ValueError):
                pass  # Already caught by numeric validation
        
        # GST validation (if present, must be numeric)
        gst = data.get('gst')
        if gst is not None and gst != '':
            try:
                Decimal(str(gst))
            except (InvalidOperation, ValueError):
                errors.append(InvoiceValidationError('gst', 'GST must be a valid number'))
        
        return errors

    def is_valid(self, data: dict) -> bool:
        """Check if data is valid."""
        return len(self.validate(data)) == 0