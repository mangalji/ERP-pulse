import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from tenancy.models import Company, CompanyDeletionHistory
from superadmin.services import SuperAdminService


logger = logging.getLogger(__name__)


@shared_task
def purge_expired_deleted_companies():
    """
    Permanently delete companies that have remained soft-deleted
    for at least 15 days.

    The company deletion history is preserved before the actual
    company row is removed.
    """
    cutoff = timezone.now() - timedelta(days=15)

    companies = (
        Company.objects
        .filter(
            is_deleted=True,
            deleted_at__isnull=False,
            deleted_at__lte=cutoff,
        )
        .only(
            'id',
            'name',
            'code',
            'deleted_at',
        )
    )

    deleted_count = 0

    for company in companies:
        try:
            # with transaction.atomic():
            #     permanently_deleted_at = timezone.now()

            #     CompanyDeletionHistory.objects.create(
            #         company_id_snapshot=company.id,
            #         company_name=company.name,
            #         company_code=company.code,
            #         soft_deleted_at=company.deleted_at,
            #         permanently_deleted_at=permanently_deleted_at,
            #         deleted_by=None,
            #     )

            #     company.delete()

            result = SuperAdminService().permanently_delete_company(
                company_id=company.id,
                deleted_by=None,
            )

            deleted_count += 1

            logger.info(
                'Company %s (%s) permanently deleted after 15-day recovery period.',
                result['company_name'],
                result['company_id'],
            )

        except Exception:
            logger.exception(
                'Failed to permanently delete company %s (%s).',
                company.name,
                company.id,
            )

    return {
        'deleted_count': deleted_count,
    }