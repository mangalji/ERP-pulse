"""Persistence helpers for the approved Gemini OCR extraction schema."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from copy import deepcopy

from django.db import transaction
from django.utils import timezone

from ocr.models import (
    DocumentType,
    OCRDocument,
    OCRDocumentStatus,
    OCRDocumentVersion,
    GeneratedInvoiceNumber,
)
from ocr.services.calculated_values import apply_calculated_values

def _nullable_string(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _apply_initial_defaults(result, reviewed_result=None):
    original_data = result.get('data', result)
    current = reviewed_result if reviewed_result is not None else result
    current_data = current.get('data', current)
    if not isinstance(original_data, dict) or not isinstance(current_data, dict):
        return
    for key, default in (('invoice_number', None),):
        if _nullable_string(original_data.get(key)) or _nullable_string(current_data.get(key)):
            continue
        value = default
        if key == 'invoice_number':
            value = f'vendor_bill_inv_{GeneratedInvoiceNumber.objects.create().pk}'
        original_data[key] = value
        current_data[key] = value


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

def _remove_customer_name_key(value):
    """Remove the unsupported Vendor Bill Customer Name field from JSON payloads."""
    if isinstance(value, dict):
        return {
            key: _remove_customer_name_key(item)
            for key, item in value.items()
            if str(key).strip().lower() not in {"customer_name", "customer name"}
        }
    if isinstance(value, list):
        return [_remove_customer_name_key(item) for item in value]
    return value


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
        'subsidiary': _nullable_string(data.get('subsidiary')),
        'currency': _nullable_string(data.get('currency')),
        'subtotal': _nullable_decimal(data.get('subtotal')),
        'tax_amount': _nullable_decimal(data.get('tax_amount')),
        'tax_rate': _nullable_decimal(data.get('tax_rate')),
        'total_amount': _nullable_decimal(data.get('total_amount')),
        'payment_terms': _nullable_string(data.get('payment_terms')),
    }

@transaction.atomic
def persist_extraction(*, upload=None, document=None, batch=None, user=None, result: dict = None, reviewed_result: dict | None = None, allow_company_admin=False):
    """
    Persist one extraction as an immutable OCR document version.

    The complete original AI JSON is retained in ``normalized_json``.
    When ``reviewed_result`` is provided, the user-approved/edited JSON is
    stored in ``reviewed_json`` and its normalized fields are materialized into the version columns while preserving line items in the JSON snapshot. This lets the application preserve
    the original AI extraction while making the reviewed result the current
    business data.

    The function creates an immutable version, so editing an existing saved
    document later creates a new version instead of destroying the previous
    snapshot.
    """

    if user is None or result is None:
        raise ValueError("A user and extraction result are required.")
    if upload is None and document is None:
        raise ValueError("An OCR upload or document is required.")
    if upload is not None and document is not None:
        raise ValueError("Provide either an OCR upload or document, not both.")

    if reviewed_result is not None and not isinstance(reviewed_result, dict):
        raise ValueError('Reviewed OCR result must be a JSON object.')

    # Do not retain the deprecated Customer Name field in newly saved snapshots.
    result = _remove_customer_name_key(result)
    raw_result = deepcopy(result)
    if reviewed_result is not None:
        reviewed_result = _remove_customer_name_key(reviewed_result)

    company = getattr(user, 'company', None)

    if document is None:
        document, _ = OCRDocument.objects.get_or_create(
            upload=upload,
            defaults={
                'user': user,
                'company': company,
                'document_type': DocumentType.UNKNOWN,
                'status': OCRDocumentStatus.PROCESSING,
            },
        )
    elif batch is not None and document.batch_id is None:
        document.batch = batch
        document.save(update_fields=['batch', 'updated_at'])

    # Same lock as posting reservation: editing and posting cannot race.
    document = OCRDocument.objects.select_for_update().get(pk=document.pk)

    if document.user_id != user.id:
        role = getattr(user, "role", None)

        is_company_admin = (
            getattr(user, "is_superuser", False)
            or getattr(user, "is_staff", False)
            or (
                role is not None
                and role.name.lower() == "company admin"
            )
)
        if not (allow_company_admin and is_company_admin):
            raise PermissionError('OCR document belongs to a different user.')

    if company is not None:
        if document.company_id is not None and document.company_id != company.id:
            raise PermissionError('OCR document belongs to a different company.')
        if document.company_id is None:
            document.company = company
            document.save(update_fields=['company', 'updated_at'])

    # Defaults are assigned once, when the extraction is first saved. Existing
    # reviews retain their values and an explicit user edit is never replaced.
    if not document.versions.exists():
        _apply_initial_defaults(result, reviewed_result)

    # Fill legacy/null derived values at persistence time too. Explicit user
    # values and template defaults are preserved here; new extraction output is
    # calculated before defaults are applied in the extraction service.
    result = apply_calculated_values(result, overwrite=False)
    if reviewed_result is not None:
        reviewed_result = apply_calculated_values(reviewed_result, overwrite=False)

    effective_result = reviewed_result if reviewed_result is not None else result
    normalized = normalize_extraction_payload(effective_result)

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
        raw_ocr=raw_result,
        normalized_json=result,
        reviewed_json=(
            reviewed_result if reviewed_result is not None else {}
        ),
        confidence={},
        validation_errors=[],
        created_by=user,
        **normalized,
    )
    document.current_version = version_number
    document.status = (
        OCRDocumentStatus.APPROVED if reviewed_result is not None else OCRDocumentStatus.EXTRACTED
    )
    document.processing_completed_at = (
        upload.processing_completed_at if upload is not None else timezone.now()
    )
    document.processing_duration_ms = (
        upload.processing_duration_ms if upload is not None else None
    )
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
