"""Idempotent company processing usage accounting."""

import logging

from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from ocr.models import BillProcessingCount, OCRBatch, OCRUpload
from mail_integration.models import EmailIntegration, EmailMessage

logger = logging.getLogger(__name__)


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


def _configuration_error(source: str, missing: list[str]) -> ProcessingConfigurationIncomplete:
    contact = get_superadmin_contact_email()
    reason = ", ".join(missing)
    return ProcessingConfigurationIncomplete(
        f"AI extraction is not configured for this company. Missing configuration: {reason}. "
        f"Please contact your Super Administrator: {contact}."
    )


def validate_extraction_prompt(company, source: str):
    """Require a source prompt before accepting any OCR work."""
    prefix = "pdf" if source == "pdf" else "email"
    usage = BillProcessingCount.objects.filter(company=company).first()
    if not usage or not getattr(usage, f"{prefix}_extraction_prompt", "").strip():
        raise _configuration_error(source, [f"{prefix.upper()} extraction prompt"])
    return usage


def validate_processing_limits(company, source: str, *, usage=None):
    """Require an active, configured allocation after prompt validation."""
    prefix, limit_field, _ = _source_fields(source)
    usage = usage or BillProcessingCount.objects.filter(company=company).first()
    missing = []
    if not usage or int(getattr(usage, limit_field, 0) or 0) <= 0:
        missing.append("PDF/file page limit" if prefix == "pdf" else "email bill limit")
    if not usage or not getattr(usage, f"{prefix}_allocation_start_date", None) or not getattr(usage, f"{prefix}_allocation_end_date", None):
        missing.append("PDF/file allocation date range" if prefix == "pdf" else "email allocation date range")
    if missing:
        raise _configuration_error(source, missing)
    period_state = allocation_period_state(usage, prefix)
    if period_state != "active":
        raise ProcessingLimitExceeded(
            f"{prefix.upper()} processing allocation is not active because its validity period is "
            f"{period_state.replace('_', ' ')}. Please contact your SuperAdmin."
        )
    return usage


def validate_processing_configuration(company, source: str):
    """Validate prompt first, then the source allocation configuration."""
    usage = validate_extraction_prompt(company, source)
    return validate_processing_limits(company, source, usage=usage)


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


def pause_email_integrations_for_limit(company, usage=None) -> bool:
    """Pause active company mailboxes and notify their owners at quota exhaustion."""
    if usage is None:
        usage = BillProcessingCount.objects.filter(company=company).first()
    limit = int(getattr(usage, "email_bill_limit", 0) or 0)
    consumed = int(getattr(usage, "email_bills_consumed", 0) or 0)
    if consumed < limit:
        return False
    remaining = max(0, limit - consumed)
    contact = get_superadmin_contact_email()
    company_name = getattr(company, "name", None) or "Unknown company"
    message = (
        f"Email fetching stopped for {company_name}: the email bill limit is exhausted "
        f"({consumed} of {limit} used). Contact your Super Administrator at {contact} "
        "to increase the allocation."
    )

    integrations = list(
        EmailIntegration.objects.filter(
            company=company,
            is_active=True,
            is_paused=False,
            status="CONNECTED",
        ).values("id", "created_by_id")
    )
    if not integrations:
        return False

    integration_ids = [item["id"] for item in integrations]
    updated = EmailIntegration.objects.filter(
        id__in=integration_ids,
        is_paused=False,
    ).update(is_paused=True, updated_at=timezone.now())
    if not updated:
        return False

    logger.error(
        "Company email processing limit hit — company=%s company_id=%s "
        "consumed=%s limit=%s remaining=%s; email/file processing will not "
        "complete until the allocation is increased.",
        company_name,
        company.pk,
        consumed,
        limit,
        remaining,
    )
    from audit.notifications import notify

    for user_id in {item["created_by_id"] for item in integrations if item["created_by_id"]}:
        notify(user_id, company.pk, message, "/app/integrations/email")
    return True


def email_capacity_block_message(company) -> str:
    """Return a user-facing reason and SuperAdmin contact when email cannot start."""
    usage = BillProcessingCount.objects.filter(company=company).first()
    limit = int(getattr(usage, "email_bill_limit", 0) or 0)
    consumed = int(getattr(usage, "email_bills_consumed", 0) or 0)
    contact = get_superadmin_contact_email()
    if consumed >= limit:
        reason = f"the email bill limit is exhausted ({consumed} of {limit} used)"
    else:
        reason = "the email bill allocation is currently inactive"
    return (
        f"Email fetching cannot start because {reason}. Contact your Super Administrator "
        f"at {contact} to restore or increase the allocation."
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
    """Count vendor-bill file pages once after AI; safe when a worker retries."""
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
        # Keep the same preflight order at the reservation boundary. This is
        # a defensive re-check for configuration changes while a job waits in
        # the queue; it must never spend quota or report a quota error before
        # reporting a missing prompt.
        validate_processing_configuration(locked.batch.company, "pdf")
        if usage.pdf_page_limit <= 0 or usage.pdf_pages_consumed + pages > usage.pdf_page_limit:
            company_name = getattr(locked.batch.company, "name", None) or "Unknown company"
            logger.error(
                "Company file processing limit hit — company=%s company_id=%s "
                "consumed=%s limit=%s requested_pages=%s; email/file processing "
                "will not complete until the allocation is increased.",
                company_name,
                company_id,
                usage.pdf_pages_consumed,
                usage.pdf_page_limit,
                pages,
            )
            raise ProcessingLimitExceeded(
                f"PDF/file processing limit reached. This company has "
                f"used {usage.pdf_pages_consumed} of {usage.pdf_page_limit} "
                f"allocated pages. Please contact your SuperAdmin."
            )
        period_state = allocation_period_state(usage, 'pdf')
        if period_state != 'active':
            raise ProcessingLimitExceeded(
                'PDF/file processing allocation is not active because its '
                f'validity period is {period_state.replace("_", " ")}. '
                'Please contact your SuperAdmin.'
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


def record_email_message(
    message: EmailMessage,
    extracted_data: dict,
    *,
    is_vendor_bill: bool | None = None,
) -> None:
    """Count an AI-confirmed vendor-bill email once, at extraction time."""
    if is_vendor_bill is not True and message.is_vendor_bill is not True:
        return
    with transaction.atomic():
        locked = EmailMessage.objects.select_for_update().select_related(
            "integration__company"
        ).get(pk=message.pk)
        if locked.vendor_bill_notification_sent:
            return
        if (
            locked.is_vendor_bill is not True
            and is_vendor_bill is not True
        ) or not isinstance(extracted_data, dict):
            return
        company = locked.integration.company
        if not company:
            return
        usage, _ = BillProcessingCount.objects.select_for_update().get_or_create(
            company=company
        )
        if usage.email_bill_limit <= 0 or usage.email_bills_consumed >= usage.email_bill_limit:
            logger.error(
                "Company email processing limit hit — company=%s company_id=%s "
                "consumed=%s limit=%s; email/file processing will not complete "
                "until the allocation is increased.",
                getattr(company, "name", None) or "Unknown company",
                company.pk,
                usage.email_bills_consumed,
                usage.email_bill_limit,
            )
            raise ProcessingLimitExceeded(
                f"Email bill processing limit reached. This company has "
                f"used {usage.email_bills_consumed} of {usage.email_bill_limit} "
                f"allocated email bills. Please contact your SuperAdmin."
            )
        validate_processing_configuration(company, "email")
        period_state = allocation_period_state(usage, 'email')
        if period_state != 'active':
            raise ProcessingLimitExceeded(
                'Email bill processing allocation is not active because its '
                f'validity period is {period_state.replace("_", " ")}. '
                'Please contact your SuperAdmin.'
            )
        usage.email_bills_consumed += 1
        usage.save(update_fields=['email_bills_consumed', 'updated_at'])
        locked.is_vendor_bill = True
        locked.ai_extracted_data_json = extracted_data
        locked.vendor_bill_notification_sent = True
        locked.save(update_fields=[
            'is_vendor_bill', 'ai_extracted_data_json',
            'vendor_bill_notification_sent', 'updated_at',
        ])
        if usage.email_bills_consumed >= usage.email_bill_limit:
            logger.error(
                "Company email processing limit hit — company=%s company_id=%s "
                "consumed=%s limit=%s; email/file processing will not complete "
                "until the allocation is increased.",
                getattr(company, "name", None) or "Unknown company",
                company.pk,
                usage.email_bills_consumed,
                usage.email_bill_limit,
            )
        return True
