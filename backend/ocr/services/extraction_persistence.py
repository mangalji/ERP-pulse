"""Persistence helpers for the approved Gemini OCR extraction schema."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from ocr.models import (
    DocumentType,
    OCRDocument,
    OCRDocumentStatus,
    OCRDocumentVersion,
    OCRLineItem,
)

# These are the fields explicitly requested by the current approved extraction
# schema. They are persisted as first-class DB columns on OCRDocumentVersion.
EXTRACTION_FIELDS = (
    'invoice_number',
    'invoice_date',
    'due_date',
    'vendor_name',
    'customer_name',
    'subsidiary',
    'currency',
    'subtotal',
    'tax_amount',
    'tax_rate',
    'total_amount',
    'payment_terms',
)

LINE_ITEM_FIELDS = (
    'description',
    'quantity',
    'unit_price',
    'amount',
)


def _nullable_string(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _nullable_decimal(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'Invalid numeric extraction value: {value!r}') from exc


def _nullable_date(value):
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid date extraction value: {value!r}') from exc


def normalize_extraction_payload(result: dict) -> dict:
    """Build the stable DB payload without dropping the complete JSON response."""
    if not isinstance(result, dict):
        raise ValueError('Gemini extraction result must be a JSON object.')

    data = result.get('data', result)
    if not isinstance(data, dict):
        raise ValueError('Gemini extraction data must be a JSON object.')

    return {
        'invoice_number': _nullable_string(data.get('invoice_number')),
        'invoice_date': _nullable_date(data.get('invoice_date')),
        'due_date': _nullable_date(data.get('due_date')),
        'vendor_name': _nullable_string(data.get('vendor_name')),
        'customer_name': _nullable_string(data.get('customer_name')),
        'subsidiary': _nullable_string(data.get('subsidiary')),
        'currency': _nullable_string(data.get('currency')),
        'subtotal': _nullable_decimal(data.get('subtotal')),
        'tax_amount': _nullable_decimal(data.get('tax_amount')),
        'tax_rate': _nullable_decimal(data.get('tax_rate')),
        'total_amount': _nullable_decimal(data.get('total_amount')),
        'payment_terms': _nullable_string(data.get('payment_terms')),
    }


def normalize_line_items(result: dict) -> list[dict]:
    data = result.get('data', result)
    line_items = data.get('line_items') if isinstance(data, dict) else []

    if line_items is None:
        return []
    if not isinstance(line_items, list):
        raise ValueError('Gemini line_items must be an array when present.')

    normalized = []
    for item in line_items:
        if not isinstance(item, dict):
            raise ValueError('Each Gemini line item must be a JSON object.')
        normalized.append({
            'description': _nullable_string(item.get('description')),
            'quantity': _nullable_decimal(item.get('quantity')),
            'unit_price': _nullable_decimal(item.get('unit_price')),
            'amount': _nullable_decimal(item.get('amount')),
        })
    return normalized


@transaction.atomic
def persist_extraction(*, upload, user, result: dict):
    """Persist one extraction as an immutable OCR document version.

    The complete Gemini JSON is retained in ``normalized_json``. The fields
    explicitly defined by the approved extraction schema are additionally
    materialized into DB columns so every known field has a stable column even
    when its value is NULL. Line items are stored in a separate table because
    their count is variable.
    """
    normalized = normalize_extraction_payload(result)
    line_items = normalize_line_items(result)

    company = getattr(user, 'company', None)

    document, _ = OCRDocument.objects.get_or_create(
        upload=upload,
        defaults={
            'user': user,
            'company': company,
            'document_type': DocumentType.UNKNOWN,
            'status': OCRDocumentStatus.PROCESSING,
        },
    )

    if document.user_id != user.id:
        raise PermissionError('OCR document belongs to a different user.')

    version_number = (
        OCRDocumentVersion.objects
        .filter(document=document)
        .order_by('-version_number')
        .values_list('version_number', flat=True)
        .first()
        or 0
    ) + 1

    version = OCRDocumentVersion.objects.create(
        document=document,
        version_number=version_number,
        raw_ocr=result,
        normalized_json=result,
        reviewed_json={},
        confidence={},
        validation_errors=[],
        created_by=user,
        **normalized,
    )

    OCRLineItem.objects.bulk_create([
        OCRLineItem(
            version=version,
            line_number=index,
            **item,
        )
        for index, item in enumerate(line_items, start=1)
    ])

    document.current_version = version_number
    document.status = OCRDocumentStatus.EXTRACTED
    document.processing_completed_at = upload.processing_completed_at
    document.processing_duration_ms = upload.processing_duration_ms
    document.failure_reason = None
    document.save(update_fields=[
        'current_version',
        'status',
        'processing_completed_at',
        'processing_duration_ms',
        'failure_reason',
        'updated_at',
    ])

    return document, version
