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
from django.utils.crypto import get_random_string
from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from tenancy.models import Company
from superadmin.models import (
    Plan, DiscountType, Transaction,
    PaymentStatus, TransactionStatus,
)
from decimal import Decimal

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
    def create_pending_plan_transaction(
        self,
        *,
        company_id,
        plan_id,
        discount_type=None,
        discount_value=None,
        request=None,
    ):
        company = Company.objects.select_for_update().get(pk=company_id)
        plan = Plan.objects.get(pk=plan_id)

        if plan.is_deleted or plan.status != 'ACTIVE':
            raise ValueError('This plan is not available for assignment.')

        # A company with an active subscription cannot start another
        # initial assignment transaction.
        active_subscription = self.get_active_subscription(company.id)
        if active_subscription is not None:
            raise ValueError(
                'This company already has an active subscription.'
            )

        # Only one pending assignment transaction at a time.
        existing_pending = Transaction.objects.filter(
            company=company,
            payment_status=PaymentStatus.PENDING,
            transaction_status__in=[
                TransactionStatus.INITIATED,
                TransactionStatus.PENDING,
            ],
        ).first()

        if existing_pending:
            raise ValueError(
                'A pending plan assignment transaction already exists.'
            )

        normalized_discount_type = discount_type or DiscountType.NONE
        normalized_discount_value = discount_value or 0

        discount_amount, total_amount = self._calculate_final_price(
            plan.price,
            normalized_discount_type,
            normalized_discount_value,
        )

        transaction_id = f'TXN-{get_random_string(8).upper()}'

        transaction_record = Transaction.objects.create(
            company=company,
            plan=plan,
            transaction_id=transaction_id,
            original_amount=Decimal(str(plan.price)).quantize(
                Decimal('0.01')
            ),
            discount_amount=discount_amount,
            total_amount=total_amount,
            payment_status=PaymentStatus.PENDING,
            transaction_status=TransactionStatus.INITIATED,
            payment_method='MANUAL',
            assigned_by=self._audit_user(request),
        )

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.CREATE,
            entity='Transaction',
            entity_id=str(transaction_record.id),
            company=company,
            user=self._audit_user(request),
            old_value=None,
            new_value={
                'transaction_id': transaction_record.transaction_id,
                'company_id': str(company.id),
                'plan_id': str(plan.id),
                'plan_name': plan.name,
                'original_amount': str(
                    transaction_record.original_amount
                ),
                'discount_amount': str(
                    transaction_record.discount_amount
                ),
                'total_amount': str(
                    transaction_record.total_amount
                ),
                'payment_status': transaction_record.payment_status,
                'transaction_status': transaction_record.transaction_status,
            },
        )

        return transaction_record

    @staticmethod
    def _calculate_final_price(
        original_price,
        discount_type,
        discount_value,
    ):
        original_price = Decimal(str(original_price or 0))
        discount_value = Decimal(str(discount_value or 0))

        if original_price < 0:
            raise ValueError(
                'Original price cannot be negative.'
            )

        if discount_type == DiscountType.NONE:
            discount_amount = Decimal('0')

        elif discount_type == DiscountType.PERCENTAGE:
            if discount_value < 0 or discount_value > 100:
                raise ValueError(
                    'Percentage discount must be between 0 and 100.'
                )

            discount_amount = (
                original_price
                * discount_value
                / Decimal('100')
            )

        elif discount_type == DiscountType.FIXED:
            if discount_value < 0:
                raise ValueError(
                    'Discount value cannot be negative.'
                )

            if discount_value > original_price:
                raise ValueError(
                    'Fixed discount cannot exceed the plan price.'
                )

            discount_amount = discount_value

        else:
            raise ValueError('Invalid discount type.')

        total_amount = original_price - discount_amount

        if total_amount < 0:
            raise ValueError(
                'Total amount cannot be negative.'
            )

        return (
            discount_amount.quantize(Decimal('0.01')),
            total_amount.quantize(Decimal('0.01')),
        )

    @transaction.atomic
    def complete_plan_transaction(
        self,
        *,
        company_id,
        transaction_id,
        request=None,
    ):
        company = (
            Company.objects
            .select_for_update()
            .get(pk=company_id)
        )

        transaction_record = (
            Transaction.objects
            .select_for_update()
            .select_related('plan')
            .filter(
                company=company,
                transaction_id=transaction_id,
            )
            .first()
        )

        if not transaction_record:
            raise ValueError('Transaction not found.')

        if (
            transaction_record.payment_status != PaymentStatus.PENDING
            or transaction_record.transaction_status
            not in [
                TransactionStatus.INITIATED,
                TransactionStatus.PENDING,
            ]
        ):
            raise ValueError(
                'Only a pending transaction can be completed.'
            )

        plan = transaction_record.plan

        if not plan:
            raise ValueError(
                'No plan is associated with this transaction.'
            )

        today = timezone.now().date()
        end_date = today + timedelta(days=plan.validity_days)

        company.plan = plan
        company.plan_start_date = today
        company.plan_end_date = end_date
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

        transaction_record.payment_status = PaymentStatus.SUCCESS
        transaction_record.transaction_status = TransactionStatus.COMPLETED
        transaction_record.assigned_by = self._audit_user(request)

        transaction_record.save(
            update_fields=[
                'payment_status',
                'transaction_status',
                'assigned_by',
            ]
        )

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='Transaction',
            entity_id=str(transaction_record.id),
            company=company,
            user=self._audit_user(request),
            old_value={
                'payment_status': PaymentStatus.PENDING,
                'transaction_status': TransactionStatus.INITIATED,
            },
            new_value={
                'transaction_id': transaction_record.transaction_id,
                'company_id': str(company.id),
                'plan_id': str(plan.id),
                'plan_name': plan.name,
                'payment_status': transaction_record.payment_status,
                'transaction_status': transaction_record.transaction_status,
                'plan_start_date': str(company.plan_start_date),
                'plan_end_date': str(company.plan_end_date),
            },
        )

        return transaction_record
    
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
