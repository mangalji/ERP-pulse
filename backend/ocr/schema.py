"""
Schema validation for Gemini OCR extraction results.

Validates the JSON response returned by Gemini against the expected
invoice schema. Ensures all required keys exist, types are correct,
and numeric fields are valid numbers.
"""

from __future__ import annotations

import re
from datetime import datetime

from ocr.exceptions import GeminiValidationException

#: Expected schema for Gemini extraction results.
#: Keys map to expected Python types.
REQUIRED_KEYS: dict[str, type] = {
    'vendor': str,
    'invoice_number': str,
    'invoice_date': str,
    'currency': str,
    'subtotal': (int, float),
    'tax': (int, float),
    'total': (int, float),
    'purchase_order': str,
    'items': list,
    'confidence': dict,
}

#: ISO 8601 date pattern for validation.
DATE_PATTERN: re.Pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

#: ISO 4217 currency code pattern.
CURRENCY_PATTERN: re.Pattern = re.compile(r'^[A-Z]{3}$')


def validate_extraction_result(data: dict) -> dict:
    """
    Validate the extracted data against the expected schema.

    Args:
        data: The parsed JSON dictionary from Gemini.

    Returns:
        The validated data dictionary (unmodified).

    Raises:
        GeminiValidationException: If validation fails.
    """
    _validate_required_keys(data)
    _validate_types(data)
    _validate_date_format(data)
    _validate_currency_format(data)
    _validate_numeric_range(data)
    _validate_items(data)
    _validate_confidence(data)
    return data


def _validate_required_keys(data: dict) -> None:
    """Check that all required keys are present."""
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise GeminiValidationException(
            f'Missing required keys: {", ".join(missing)}.'
        )


def _validate_types(data: dict) -> None:
    """Check that each field has the expected type."""
    for key, expected_type in REQUIRED_KEYS.items():
        value = data[key]
        if value is None:
            continue
        if not isinstance(value, expected_type):
            expected_name = getattr(expected_type, '__name__', str(expected_type))
            raise GeminiValidationException(
                f'Field "{key}" has invalid type: '
                f'expected {expected_name}, '
                f'got {type(value).__name__} ({value}).'
            )


def _validate_date_format(data: dict) -> None:
    """Validate invoice_date format (YYYY-MM-DD) if not null."""
    date_str = data.get('invoice_date')
    if date_str is None:
        return
    if not isinstance(date_str, str) or not DATE_PATTERN.match(date_str):
        raise GeminiValidationException(
            f'Invalid invoice_date format: "{date_str}". '
            'Expected YYYY-MM-DD.'
        )
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError as exc:
        raise GeminiValidationException(
            f'Invalid invoice_date: "{date_str}" is not a valid date. {exc}'
        ) from exc


def _validate_currency_format(data: dict) -> None:
    """Validate currency code (ISO 4217) if not null."""
    currency = data.get('currency')
    if currency is None:
        return
    if not isinstance(currency, str) or not CURRENCY_PATTERN.match(currency):
        raise GeminiValidationException(
            f'Invalid currency code: "{currency}". '
            'Expected ISO 4217 format (e.g. USD, EUR, INR).'
        )


def _validate_numeric_range(data: dict) -> None:
    """Validate numeric fields are non-negative if not null."""
    for key in ('subtotal', 'tax', 'total'):
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)) and value < 0:
            raise GeminiValidationException(
                f'Field "{key}" must be non-negative, got {value}.'
            )


def _validate_items(data: dict) -> None:
    """Validate items array structure if present."""
    items = data.get('items')
    if items is None:
        return
    if not isinstance(items, list):
        raise GeminiValidationException(
            f'Items must be a list, got {type(items).__name__}.'
        )
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise GeminiValidationException(
                f'Item at index {i} must be a dict, '
                f'got {type(item).__name__}.'
            )
        for field in ('description', 'quantity', 'unit_price', 'total'):
            if field not in item:
                raise GeminiValidationException(
                    f'Item at index {i} is missing field "{field}".'
                )


def _validate_confidence(data: dict) -> None:
    """Validate the confidence object structure."""
    confidence = data.get('confidence')
    if confidence is None:
        return
    if not isinstance(confidence, dict):
        raise GeminiValidationException(
            f'Confidence must be a dict, got {type(confidence).__name__}.'
        )
    for field, score in confidence.items():
        if not isinstance(score, (int, float)):
            raise GeminiValidationException(
                f'Confidence score for "{field}" must be a number, '
                f'got {type(score).__name__}.'
            )
        if score < 0.0 or score > 1.0:
            raise GeminiValidationException(
                f'Confidence score for "{field}" must be between '
                f'0.0 and 1.0, got {score}.'
            )