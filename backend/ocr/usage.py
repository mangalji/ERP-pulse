"""Idempotent company processing usage accounting."""

from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from ocr.models import BillProcessingCount, OCRBatch, OCRUpload


class ProcessingLimitExceeded(Exception):
    """A company has no remaining allocation for this processing source."""


class ProcessingConfigurationIncomplete(ProcessingLimitExceeded):
    """The company has not been fully configured for a processing source."""


class ProcessingUsageUnavailable(Exception):
    """Usage accounting could not be checked safely."""


def _source_fields(source: str) -> tuple[str, str, str]:
    """Return the usage fields for a supported processing source."""
    if source == "pdf":
        return "pdf", "pdf_page_limit", "pdf_pages_consumed"
    if source == "email":
        return "email", "email_bill_limit", "email_bills_consumed"
    raise ValueError(f"Unsupported processing source: {source}")


def validate_allocation_dates(data, source: str) -> None:
    """Validate one source's allocation date range when both dates are present."""
    prefix, _, _ = _source_fields(source)
    start_date = data.get(f"{prefix}_allocation_start_date")
    end_date = data.get(f"{prefix}_allocation_end_date")
    if start_date and end_date and end_date < start_date:
        raise ValueError(
            f"{prefix.title()} allocation end date must be on or after the start date."
        )


def get_or_create_usage(company):
    usage, _ = BillProcessingCount.objects.get_or_create(company=company)
    return usage


def get_superadmin_contact_email() -> str:
    """Return the first active platform SuperAdmin contact address."""
    user_model = get_user_model()
    return (
        user_model.objects.filter(is_active=True, email__isnull=False)
        .exclude(email="")
        .filter(Q(is_superuser=True) | Q(is_staff=True))
        .order_by("created_at", "email")
        .values_list("email", flat=True)
        .first()
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
        or "your Super Administrator"
    )


def validate_processing_configuration(company, source: str):
    """Validate prompt, limit, and date range as one source configuration."""
    prefix = "pdf" if source == "pdf" else "email"
    usage = BillProcessingCount.objects.filter(company=company).first()
    missing = []
    if not usage:
        missing = [
            f"{prefix.upper()} extraction prompt",
            f"{prefix.upper()}/file page limit" if prefix == "pdf" else "email bill limit",
            f"{prefix.upper()}/file allocation date range" if prefix == "pdf" else "email allocation date range",
        ]
    else:
        if not getattr(usage, f"{prefix}_extraction_prompt", "").strip():
            missing.append(f"{prefix.upper()} extraction prompt")
        limit_field = "pdf_page_limit" if prefix == "pdf" else "email_bill_limit"
        if int(getattr(usage, limit_field, 0) or 0) <= 0:
            missing.append("PDF/file page limit" if prefix == "pdf" else "email bill limit")
        if not getattr(usage, f"{prefix}_allocation_start_date", None) or not getattr(usage, f"{prefix}_allocation_end_date", None):
            missing.append("PDF/file allocation date range" if prefix == "pdf" else "email allocation date range")

    if missing:
        contact = get_superadmin_contact_email()
        reason = ", ".join(missing)
        raise ProcessingConfigurationIncomplete(
            f"AI extraction is not configured for this company. Missing configuration: {reason}. "
            f"Please contact your Super Administrator: {contact}."
        )
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


def capacity_available(company_id, source: str) -> bool:
    """Return whether a company has active, unused capacity for ``source``."""
    prefix, limit_field, consumed_field = _source_fields(source)
    usage = BillProcessingCount.objects.filter(company_id=company_id).first()
    return bool(
        usage
        and allocation_period_state(usage, prefix) == "active"
        and int(getattr(usage, limit_field, 0) or 0)
        > int(getattr(usage, consumed_field, 0) or 0)
    )


def remaining_units(company_id, source: str) -> int:
    """Return active remaining allocation units for ``source``."""
    prefix, limit_field, consumed_field = _source_fields(source)
    usage = BillProcessingCount.objects.filter(company_id=company_id).first()
    if not usage or allocation_period_state(usage, prefix) != "active":
        return 0
    return max(
        0,
        int(getattr(usage, limit_field, 0) or 0)
        - int(getattr(usage, consumed_field, 0) or 0),
    )


def reserve_upload_pages(upload: OCRUpload, page_count: int) -> None:
    """Reserve file pages once, before AI; safe when a worker retries."""
    pages = max(1, int(page_count or 1))
    if not upload.batch_id:
        return
    with transaction.atomic():
        # ``batch`` is nullable. Without ``of=("self",)`` PostgreSQL tries
        # to lock the nullable side of the LEFT OUTER JOIN created by
        # ``select_related('batch')`` and raises NotSupportedError.
        locked = (
            OCRUpload.objects
            .select_for_update(of=("self",))
            .select_related('batch')
            .get(pk=upload.pk)
        )
        if locked.processing_usage_counted:
            return
        company_id = locked.batch.company_id if locked.batch_id else None
        if not company_id:
            return
        usage, _ = BillProcessingCount.objects.select_for_update().get_or_create(
            company_id=company_id
        )
        validate_processing_configuration(locked.batch.company, "pdf")
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


def release_upload_pages(upload: OCRUpload) -> None:
    """Release a file-page reservation when extraction does not succeed."""
    if not upload.batch_id:
        return
    with transaction.atomic():
        locked = OCRUpload.objects.select_for_update(of=("self",)).get(pk=upload.pk)
        if not locked.processing_usage_counted or not locked.processing_usage_pages:
            return
        batch_id = locked.batch_id
        company_id = OCRBatch.objects.filter(pk=batch_id).values_list("company_id", flat=True).first()
        if not company_id:
            return
        usage = BillProcessingCount.objects.select_for_update().filter(company_id=company_id).first()
        if usage:
            usage.pdf_pages_consumed = max(
                0, usage.pdf_pages_consumed - locked.processing_usage_pages
            )
            usage.save(update_fields=["pdf_pages_consumed", "updated_at"])
        locked.processing_usage_pages = 0
        locked.processing_usage_counted = False
        locked.save(update_fields=["processing_usage_counted", "processing_usage_pages", "updated_at"])


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
        validate_processing_configuration(locked.company, "email")
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
