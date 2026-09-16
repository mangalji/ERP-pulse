"""
Subscriptions & Licensing app.

Business logic for:
- Subscription lifecycle (assign, upgrade, downgrade, renew, cancel, expire)
- License enforcement (module access, usage limits, feature gates)
- Usage tracking and quota management
"""

from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from tenancy.models import Company
from superadmin.models import (
    Plan, DiscountType, BillingCycle, Transaction,
    PaymentStatus, TransactionStatus,
)

from .utils import LicenseError
from decimal import Decimal, InvalidOperation

class SubscriptionService:
    """Business logic for subscription management."""

    @staticmethod
    def _audit_user(request=None):
        user = getattr(request, 'user', None) if request else None
        if user is not None and getattr(user, 'is_authenticated', False):
            return user
        return None

    def get_active_subscription(self, company_id):
        """Get the currently active plan assigned to a company."""
        company = (
            Company.objects
                .select_related('plan')
                .filter(pk=company_id)
                .first()
        )
        if not company:
            return None

        today = timezone.now().date()

        if not company.plan_id:
            return None

        if company.plan_start_date and company.plan_start_date > today:
            return None

        if company.plan_end_date and company.plan_end_date < today:
            return None

        return company

    @transaction.atomic
    def assign_plan(
        self,
        *,
        company_id,
        plan_id,
        discount_type=None,
        discount_value=None,
        billing_cycle=None,
        request=None,
    ):
        """Assign a plan directly to a company."""

        company = Company.objects.select_for_update().get(pk=company_id)
        plan = Plan.objects.get(pk=plan_id)

        if plan.is_deleted or plan.status != 'ACTIVE':
            raise ValueError('This plan is not available for assignment.')

        normalized_discount_type = discount_type or DiscountType.NONE
        normalized_discount_value = discount_value or 0
        normalized_billing_cycle = billing_cycle or BillingCycle.MONTHLY

        original_price = (
            plan.yearly_price
            if normalized_billing_cycle == BillingCycle.YEARLY
            else plan.monthly_price
        )

        discount_amount,final_price = self._calculate_final_price(
            original_price,
            normalized_discount_type,
            normalized_discount_value,
        )

        today = timezone.now().date()
        end_date = today + timedelta(days=plan.validity_days)

        old_plan_id = company.plan_id

        company.plan = plan
        company.plan_start_date = today
        company.plan_end_date = end_date

        if company.suspension_reason != 'MANUAL':
            company.status = Company.Status.ACTIVE
            company.suspension_reason = 'NONE'

        company.save(
            update_fields=[
                'plan',
                'plan_start_date',
                'plan_end_date',
                'status',
                'suspension_reason',
            ]
        )

        self._create_transaction(
            company=company,
            plan=plan,
            original_amount=original_price,
            discount_amount=discount_amount,
            discount_type=normalized_discount_type,
            discount_value=normalized_discount_value,
            final_amount=final_price,
            billing_cycle=normalized_billing_cycle,
            request=request,
        )

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE if old_plan_id else AuditAction.CREATE,
            entity='Company',
            entity_id=str(company.id),
            company=company,
            user=self._audit_user(request),
            old_value={
                'plan_id': str(old_plan_id) if old_plan_id else None,
            },
            new_value={
                'plan_id': str(plan.id),
                'plan_name': plan.name,
                'plan_start_date': str(today),
                'plan_end_date': str(end_date),
            },
        )

        return company

    @staticmethod
    def _calculate_final_price(
        original_price,
        discount_type,
        discount_value,
    ):
        original_price = Decimal(str(original_price or 0))
        discount_value = Decimal(str(discount_value or 0))

        if original_price < 0:
            raise ValueError("Original price cannot be negative.")

        if discount_type == DiscountType.NONE:
            discount_value = Decimal("0")
            discount_amount = Decimal("0")

        elif discount_type == DiscountType.PERCENTAGE:
            if discount_value < 0 or discount_value > 100:
                raise ValueError(
                    "Percentage discount must be between 0 and 100."
                )

            discount_amount = (
                original_price * discount_value / Decimal("100")
            )

        elif discount_type == DiscountType.FIXED:
            if discount_value < 0:
                raise ValueError(
                    "Discount value cannot be negative."
                )

            if discount_value > original_price:
                raise ValueError(
                    "Fixed discount cannot exceed the plan price."
                )

            discount_amount = discount_value

        else:
            raise ValueError("Invalid discount type.")

        final_price = original_price - discount_amount

        if final_price < 0:
            raise ValueError("Final price cannot be negative.")

        return (
            discount_amount.quantize(Decimal("0.01")),
            final_price.quantize(Decimal("0.01")),
        )

    def _create_transaction(
        self,
        *,
        company,
        plan,
        original_amount,
        discount_amount,
        discount_type,
        discount_value,
        final_amount,
        billing_cycle,
        request=None,
    ):
        from django.utils.crypto import get_random_string
    
        transaction_id = f"TXN-{get_random_string(8).upper()}"
    
        Transaction.objects.create(
            company=company,
            plan=plan,
            transaction_id=transaction_id,
            original_amount=original_amount,
            discount_amount=discount_amount,
            discount_type=discount_type,
            discount_value=discount_value,
            final_amount=final_amount,
            billing_cycle=billing_cycle,
            payment_status=PaymentStatus.PENDING,
            transaction_status=TransactionStatus.INITIATED,
            payment_method="MANUAL",
            assigned_by=self._audit_user(request),
        )
    
    @transaction.atomic
    def upgrade_plan(
        self,
        *,
        company_id,
        plan_id,
        discount_type=None,
        discount_value=None,
        billing_cycle=None,
        request=None,
    ):
        """Upgrade company to another active plan."""

        company = Company.objects.select_for_update().get(pk=company_id)
        old_plan_id = company.plan_id

        new_company = self.assign_plan(
            company_id=company.id,
            plan_id=plan_id,
            discount_type=discount_type,
            discount_value=discount_value,
            billing_cycle=billing_cycle,
            request=request,
        )

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company_id=company.id,
            user=self._audit_user(request),
            old_value={'plan_id': str(old_plan_id) if old_plan_id else None},
            new_value={'plan_id': str(plan_id)},
        )

        return new_company

    @transaction.atomic
    def downgrade_plan(
        self,
        *,
        company_id,
        plan_id,
        discount_type=None,
        discount_value=None,
        billing_cycle=None,
        request=None,
    ):
        """Downgrade company to another active plan."""

        company = Company.objects.select_for_update().get(pk=company_id)
        old_plan_id = company.plan_id

        new_company = self.assign_plan(
            company_id=company.id,
            plan_id=plan_id,
            discount_type=discount_type,
            discount_value=discount_value,
            billing_cycle=billing_cycle,
            request=request,
        )

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company_id=company.id,
            user=self._audit_user(request),
            old_value={'plan_id': str(old_plan_id) if old_plan_id else None},
            new_value={'plan_id': str(plan_id)},
        )

        return new_company

    @transaction.atomic
    def renew_plan(
        self,
        *,
        company_id,
        plan_id=None,
        discount_type=None,
        discount_value=None,
        billing_cycle=None,
        request=None,
    ):
        """Renew the company's current plan or assign a selected plan."""

        company = Company.objects.select_for_update().select_related('plan').get(
            pk=company_id
        )

        if plan_id is None:
            if not company.plan_id:
                raise ValueError(
                    'Plan selection is required when there is no current plan.'
                )
            plan_id = company.plan_id

        return self.assign_plan(
            company_id=company.id,
            plan_id=plan_id,
            discount_type=discount_type,
            discount_value=discount_value,
            billing_cycle=billing_cycle,
            request=request,
        )

    @transaction.atomic
    def cancel_plan(self, *, company_id, request=None):
        """Cancel the company's current plan."""

        company = Company.objects.select_for_update().get(pk=company_id)

        if not company.plan_id:
            raise ValueError('No active plan found for this company.')

        old_plan_id = company.plan_id

        company.plan = None
        company.plan_start_date = None
        company.plan_end_date = None
        company.status = Company.Status.SUSPENDED
        company.suspension_reason = 'PLAN'

        company.save(
            update_fields=[
                'plan',
                'plan_start_date',
                'plan_end_date',
                'status',
                'suspension_reason',
            ]
        )

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company_id=company.id,
            user=self._audit_user(request),
            old_value={'plan_id': str(old_plan_id)},
            new_value={'plan_id': None},
        )

        return company

    def check_expiry(self):
        """
        Mark companies with expired plans as suspended.

        The plan assignment remains stored on Company for reference,
        but an expired company is no longer operational.
        """

        today = timezone.now().date()

        companies = Company.objects.filter(
            plan_id__isnull=False,
            plan_end_date__lt=today,
            is_deleted=False,
        ).exclude(
            suspension_reason='MANUAL'
        )

        count = 0

        for company in companies:
            company.status = Company.Status.SUSPENDED
            company.suspension_reason = 'PLAN'
            company.save(
                update_fields=[
                    'status',
                    'suspension_reason',
                ]
            )
            count += 1

        return count

subscription_service = SubscriptionService()
