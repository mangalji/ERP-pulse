"""Idempotent company processing usage accounting."""

from django.db import transaction
from django.utils import timezone

from ocr.models import BillProcessingCount, OCRBatch, OCRUpload


class ProcessingLimitExceeded(Exception):
    """A company has no remaining allocation for this processing source."""


class ProcessingUsageUnavailable(Exception):
    """Usage accounting could not be checked safely."""


def get_or_create_usage(company):
    usage, _ = BillProcessingCount.objects.get_or_create(company=company)
    return usage


def allocation_period_state(usage, source='pdf'):
    """Return active/not_started/expired for the shared quota window."""
    today = timezone.localdate()
    prefix = 'pdf' if source == 'pdf' else 'email'
    start_date = getattr(usage, f'{prefix}_allocation_start_date')
    end_date = getattr(usage, f'{prefix}_allocation_end_date')
    if start_date and today < start_date:
        return 'not_started'
    if end_date and today > end_date:
        return 'expired'
    return 'active'


def _is_active(usage):
    return allocation_period_state(usage) == 'active'


def pdf_capacity_available(company_id) -> bool:
    usage = BillProcessingCount.objects.filter(company_id=company_id).first()
    return bool(usage and allocation_period_state(usage, 'pdf') == 'active' and usage.pdf_page_limit > usage.pdf_pages_consumed)


def email_capacity_available(company_id) -> bool:
    usage = BillProcessingCount.objects.filter(company_id=company_id).first()
    return bool(usage and allocation_period_state(usage, 'email') == 'active' and usage.email_bill_limit > usage.email_bills_consumed)


def reserve_upload_pages(upload: OCRUpload, page_count: int) -> None:
    """Reserve file pages once, before AI; safe when a worker retries."""
    pages = max(1, int(page_count or 1))
    if not upload.batch_id:
        return
    with transaction.atomic():
        locked = OCRUpload.objects.select_for_update().select_related('batch').get(pk=upload.pk)
        if locked.processing_usage_counted:
            return
        company_id = locked.batch.company_id if locked.batch_id else None
        if not company_id:
            return
        usage, _ = BillProcessingCount.objects.select_for_update().get_or_create(
            company_id=company_id
        )
        period_state = allocation_period_state(usage, 'pdf')
        if period_state != 'active':
            raise ProcessingLimitExceeded(
                'PDF/file processing allocation is not active because its '
                f'validity period is {period_state.replace("_", " ")}. '
                'Please contact your SuperAdmin.'
            )
        if usage.pdf_page_limit <= 0 or usage.pdf_pages_consumed + pages > usage.pdf_page_limit:
            raise ProcessingLimitExceeded(
                f"PDF/file processing limit reached. This company has "
                f"used {usage.pdf_pages_consumed} of {usage.pdf_page_limit} "
                f"allocated pages. Please contact your SuperAdmin."
            )
        usage.pdf_pages_consumed += pages
        usage.save(update_fields=['pdf_pages_consumed', 'updated_at'])
        locked.processing_usage_counted = True
        locked.processing_usage_pages = pages
        locked.save(update_fields=['processing_usage_counted', 'processing_usage_pages', 'updated_at'])


def record_email_bill(batch: OCRBatch) -> None:
    """Count one promoted vendor-bill email exactly once."""
    if not batch.company_id:
        return
    with transaction.atomic():
        locked = OCRBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.processing_usage_counted:
            return
        usage, _ = BillProcessingCount.objects.select_for_update().get_or_create(
            company_id=locked.company_id
        )
        period_state = allocation_period_state(usage, 'email')
        if period_state != 'active':
            raise ProcessingLimitExceeded(
                'Email bill processing allocation is not active because its '
                f'validity period is {period_state.replace("_", " ")}. '
                'Please contact your SuperAdmin.'
            )
        if usage.email_bill_limit <= 0 or usage.email_bills_consumed >= usage.email_bill_limit:
            raise ProcessingLimitExceeded(
                f"Email bill processing limit reached. This company has "
                f"used {usage.email_bills_consumed} of {usage.email_bill_limit} "
                f"allocated email bills. Please contact your SuperAdmin."
            )
        usage.email_bills_consumed += 1
        usage.save(update_fields=['email_bills_consumed', 'updated_at'])
        locked.processing_usage_counted = True
        locked.save(update_fields=['processing_usage_counted'])
