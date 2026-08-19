from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from superadmin.models import CompanyPlan, CompanyPlanStatus
from tenancy.models import Company, CompanySuspensionReason
from tenancy.services import company_lifecycle_service


logger = logging.getLogger(__name__)


@shared_task
def sync_company_subscription_statuses():
    """
    Synchronize stored Company.status with the current subscription state.

    Manual suspension is preserved.
    Soft-deleted companies remain suspended with DELETED reason.
    Subscription-driven suspension uses PLAN reason.
    """
    today = timezone.now().date()

    companies = (
        Company.objects
        .filter(is_deleted=False)
        # .prefetch_related('company_plans')
    )

    updated_count = 0
    expired_plan_count = 0

    for company in companies:
        try:
            with transaction.atomic():
                company.refresh_from_db()

                # Manual suspension is controlled by Super Admin and must
                # never be automatically overridden by subscription sync.
                if (
                    company.suspension_reason
                    == CompanySuspensionReason.MANUAL
                ):
                    continue

                plan = (
                    CompanyPlan.objects
                    .filter(company=company)
                    .order_by('-start_date', '-created_at')
                    .first()
                )

                if plan and plan.end_date and plan.end_date < today:
                    if plan.status not in {
                        CompanyPlanStatus.EXPIRED,
                        CompanyPlanStatus.CANCELLED,
                        CompanyPlanStatus.REPLACED,
                    }:
                        plan.status = CompanyPlanStatus.EXPIRED
                        plan.save(
                            update_fields=[
                                'status',
                                'updated_at',
                            ]
                        )
                        expired_plan_count += 1

                effective_status = (
                    company_lifecycle_service.get_effective_status(
                        company=company
                    )
                )

                new_reason = (
                    CompanySuspensionReason.NONE
                    if effective_status in {
                        Company.Status.ACTIVE,
                        Company.Status.TRIAL,
                    }
                    else CompanySuspensionReason.PLAN
                )

                if (
                    company.status != effective_status
                    or company.suspension_reason != new_reason
                ):
                    company.status = effective_status
                    company.suspension_reason = new_reason

                    company.save(
                        update_fields=[
                            'status',
                            'suspension_reason',
                            'updated_at',
                        ]
                    )

                    updated_count += 1

        except Exception:
            logger.exception(
                'Failed to synchronize subscription status for company %s.',
                company.id,
            )

    result = {
        'updated_companies': updated_count,
        'expired_plans': expired_plan_count,
        'checked_at': timezone.now().isoformat(),
    }

    logger.info(
        'Company subscription synchronization completed: %s',
        result,
    )

    return result