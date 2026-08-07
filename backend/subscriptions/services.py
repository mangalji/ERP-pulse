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
from tenancy.models import Company, CompanyModule, Module
from superadmin.models import (
    Plan, CompanyPlan, CompanyPlanStatus,
    DiscountType, BillingCycle, SubscriptionHistory, Transaction,
    PaymentStatus, TransactionStatus,
)

from .utils import LicenseError


class SubscriptionService:
    """Business logic for subscription management."""

    @staticmethod
    def _audit_user(request=None):
        user = getattr(request, 'user', None) if request else None
        if user is not None and getattr(user, 'is_authenticated', False):
            return user
        return None

    def get_active_subscription(self, company_id):
        """Get the active/trial subscription for a company."""
        try:
            return CompanyPlan.objects.select_related('plan').get(
                company_id=company_id,
                status__in=[CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL],
            )
        except CompanyPlan.DoesNotExist:
            return None

    def assign_plan(self, *, company_id, plan_id, discount_type=None, discount_value=None,
                    billing_cycle=None, status=None, request=None):
        """Assign a plan to a company."""
        company = Company.objects.get(pk=company_id)
        plan = Plan.objects.get(pk=plan_id)
        normalized_status = status or CompanyPlanStatus.TRIAL
        normalized_discount_type = discount_type or DiscountType.NONE
        normalized_discount_value = discount_value or 0
        normalized_billing_cycle = billing_cycle or BillingCycle.MONTHLY

        original_price = plan.yearly_price if normalized_billing_cycle == BillingCycle.YEARLY else plan.monthly_price
        final_price = self._calculate_final_price(original_price, normalized_discount_type, normalized_discount_value)
        user = self._audit_user(request)

        # Deactivate existing active plans
        existing = CompanyPlan.objects.filter(
            company=company,
            status__in=[CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL],
        ).exclude(plan=plan)

        if existing.exists() and normalized_status in [CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL]:
            existing.update(status=CompanyPlanStatus.CANCELLED, end_date=timezone.now().date())

        company_plan, created = CompanyPlan.objects.get_or_create(
            company=company,
            plan=plan,
            defaults={
                'start_date': timezone.now().date(),
                'status': normalized_status,
                'is_auto_renew': False,
                'discount_type': normalized_discount_type,
                'discount_value': normalized_discount_value,
                'billing_cycle': normalized_billing_cycle,
                'original_price': original_price,
                'final_price': final_price,
                'assigned_by': user,
            },
        )

        if not created:
            company_plan.start_date = company_plan.start_date or timezone.now().date()
            company_plan.status = normalized_status
            company_plan.end_date = None if normalized_status in [CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL] else company_plan.end_date
            company_plan.is_auto_renew = company_plan.is_auto_renew
            company_plan.discount_type = normalized_discount_type
            company_plan.discount_value = normalized_discount_value
            company_plan.billing_cycle = normalized_billing_cycle
            company_plan.original_price = original_price
            company_plan.final_price = final_price
            company_plan.assigned_by = user
            company_plan.save(update_fields=['start_date', 'status', 'end_date', 'discount_type', 'discount_value',
                                              'billing_cycle', 'original_price', 'final_price', 'assigned_by'])

        self._create_subscription_history(
            company=company, plan=plan, company_plan=company_plan,
            original_price=original_price, discount_type=normalized_discount_type,
            discount_value=normalized_discount_value, final_price=final_price,
            billing_cycle=normalized_billing_cycle, assigned_by=user,
            status_before=CompanyPlanStatus.CANCELLED, status_after=normalized_status,
            change_type='assign',
        )

        self._create_transaction(
            company=company, plan=plan, original_amount=original_price,
            final_amount=final_price, billing_cycle=normalized_billing_cycle,
        )

        # Sync module access with plan
        self._sync_company_modules(company=company, plan=plan)

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.CREATE if created else AuditAction.UPDATE,
            entity='CompanyPlan',
            entity_id=str(company_plan.id),
            company=company,
            user=user,
            old_value={'plan_id': str(plan.id), 'status': company_plan.status} if not created else None,
            new_value={'plan_id': str(plan.id), 'status': company_plan.status, 'company_id': str(company.id)},
        )

        return company_plan

    @staticmethod
    def _calculate_final_price(original_price, discount_type, discount_value):
        if discount_type == DiscountType.PERCENTAGE:
            discount_amount = original_price * (discount_value / 100)
        elif discount_type == DiscountType.FIXED:
            discount_amount = discount_value
        else:
            discount_amount = 0
        return max(original_price - discount_amount, 0)

    def _create_subscription_history(self, *, company, plan, company_plan, original_price,
                                     discount_type, discount_value, final_price, billing_cycle,
                                     assigned_by, status_before, status_after, change_type):
        SubscriptionHistory.objects.create(
            company=company,
            plan=plan,
            company_plan=company_plan,
            original_price=original_price,
            discount_type=discount_type,
            discount_value=discount_value,
            final_price=final_price,
            billing_cycle=billing_cycle,
            start_date=company_plan.start_date,
            end_date=company_plan.end_date,
            assigned_by=assigned_by,
            status_before=status_before,
            status_after=status_after,
            change_type=change_type,
        )

    def _create_transaction(self, *, company, plan, original_amount, final_amount, billing_cycle):
        from django.utils.crypto import get_random_string
        transaction_id = f'TXN-{get_random_string(8).upper()}'
        Transaction.objects.create(
            company=company,
            plan=plan,
            transaction_id=transaction_id,
            original_amount=original_amount,
            final_amount=final_amount,
            billing_cycle=billing_cycle,
            payment_status=PaymentStatus.PENDING,
            transaction_status=TransactionStatus.INITIATED,
            payment_method='MANUAL',
        )

    @transaction.atomic
    def upgrade_plan(self, *, company_id, plan_id, discount_type=None, discount_value=None,
                     billing_cycle=None, request=None):
        """Upgrade a company to a higher tier plan."""
        user = self._audit_user(request)
        company_plan = self.get_active_subscription(company_id)
        if not company_plan:
            raise ValueError('No active subscription found.')
        old_plan_id = company_plan.plan_id
        company_plan.status = CompanyPlanStatus.CANCELLED
        company_plan.end_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'end_date'])

        new_company_plan = self.assign_plan(
            company_id=company_id, plan_id=plan_id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, request=request,
            status=CompanyPlanStatus.ACTIVE,
        )

        SubscriptionHistory.objects.filter(
            company_id=company_id, company_plan=company_plan
        ).update(status_after=CompanyPlanStatus.CANCELLED)

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='CompanyPlan',
            entity_id=str(new_company_plan.id),
            company_id=company_id,
            user=user,
            old_value={'plan_id': str(old_plan_id)},
            new_value={'plan_id': str(plan_id)},
        )
        return new_company_plan

    @transaction.atomic
    def downgrade_plan(self, *, company_id, plan_id, discount_type=None, discount_value=None,
                       billing_cycle=None, request=None):
        """Downgrade a company to a lower tier plan."""
        user = self._audit_user(request)
        company_plan = self.get_active_subscription(company_id)
        if not company_plan:
            raise ValueError('No active subscription found.')
        old_plan_id = company_plan.plan_id
        company_plan.status = CompanyPlanStatus.CANCELLED
        company_plan.end_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'end_date'])

        new_company_plan = self.assign_plan(
            company_id=company_id, plan_id=plan_id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, request=request,
            status=CompanyPlanStatus.TRIAL,
        )

        SubscriptionHistory.objects.filter(
            company_id=company_id, company_plan=company_plan
        ).update(status_after=CompanyPlanStatus.CANCELLED)

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='CompanyPlan',
            entity_id=str(new_company_plan.id),
            company_id=company_id,
            user=user,
            old_value={'plan_id': str(old_plan_id)},
            new_value={'plan_id': str(plan_id)},
        )
        return new_company_plan

    @transaction.atomic
    def renew_plan(self, *, company_id, plan_id=None, discount_type=None, discount_value=None,
                   billing_cycle=None, request=None):
        """Renew an expired or cancelled plan."""
        user = self._audit_user(request)
        company_plan = CompanyPlan.objects.filter(company_id=company_id).order_by('-start_date').first()
        if company_plan is None and plan_id is None:
            raise ValueError('Plan selection is required when renewing a cancelled plan.')
        if company_plan and company_plan.status == CompanyPlanStatus.CANCELLED and plan_id is None:
            plan_id = company_plan.plan_id
        if plan_id is not None:
            new_company_plan = self.assign_plan(
                company_id=company_id, plan_id=plan_id,
                discount_type=discount_type, discount_value=discount_value,
                billing_cycle=billing_cycle, request=request,
                status=CompanyPlanStatus.ACTIVE,
            )
            return new_company_plan
        old_status = company_plan.status
        company_plan.status = CompanyPlanStatus.ACTIVE
        company_plan.start_date = timezone.now().date()
        company_plan.end_date = None
        company_plan.save(update_fields=['status', 'start_date', 'end_date'])

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='CompanyPlan',
            entity_id=str(company_plan.id),
            company_id=company_id,
            user=user,
            old_value={'status': old_status},
            new_value={'status': CompanyPlanStatus.ACTIVE},
        )
        return company_plan

    def cancel_plan(self, *, company_id, request=None):
        """Cancel the active subscription."""
        user = self._audit_user(request)
        company_plan = self.get_active_subscription(company_id)
        if not company_plan:
            raise ValueError('No active subscription found.')

        old_status = company_plan.status
        company_plan.status = CompanyPlanStatus.CANCELLED
        company_plan.end_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'end_date'])

        self._create_subscription_history(
            company=company_plan.company, plan=company_plan.plan, company_plan=company_plan,
            original_price=company_plan.original_price, discount_type=company_plan.discount_type,
            discount_value=company_plan.discount_value, final_price=company_plan.final_price,
            billing_cycle=company_plan.billing_cycle, assigned_by=user,
            status_before=old_status, status_after=CompanyPlanStatus.CANCELLED,
            change_type='cancel',
        )

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='CompanyPlan',
            entity_id=str(company_plan.id),
            company_id=company_id,
            user=user,
            old_value={'status': old_status},
            new_value={'status': CompanyPlanStatus.CANCELLED},
        )
        return company_plan

    def expire_trial(self, *, company_id, request=None):
        """Mark trial as expired."""
        company_plan = self.get_active_subscription(company_id)
        if not company_plan:
            return None

        if company_plan.status != CompanyPlanStatus.TRIAL:
            return company_plan

        company_plan.status = CompanyPlanStatus.EXPIRED
        company_plan.end_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'end_date'])

        # Disable all company modules
        CompanyModule.objects.filter(company_id=company_id).update(enabled=False)

        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='CompanyPlan',
            entity_id=str(company_plan.id),
            company_id=company_id,
            user=self._audit_user(request),
            old_value={'status': CompanyPlanStatus.TRIAL},
            new_value={'status': CompanyPlanStatus.EXPIRED},
        )

        return company_plan

    def check_expiry(self):
        """Check and expire all expired subscriptions."""
        today = timezone.now().date()
        expired_plans = CompanyPlan.objects.filter(
            status__in=[CompanyPlanStatus.TRIAL, CompanyPlanStatus.ACTIVE],
            end_date__lt=today,
        )

        count = 0
        for plan in expired_plans:
            plan.status = CompanyPlanStatus.EXPIRED
            plan.save(update_fields=['status'])
            CompanyModule.objects.filter(company=plan.company).update(enabled=False)
            count += 1

        return count

    def _sync_company_modules(self, *, company=None, company_id=None, plan):
        """Sync company modules with plan enabled modules."""
        target_company = company or Company.objects.get(pk=company_id)
        plan_modules = plan.enabled_models.all()

        # Disable modules not in plan
        CompanyModule.objects.filter(company=target_company).exclude(module__in=plan_modules).update(enabled=False)

        # Enable modules in plan
        for module in plan_modules:
            CompanyModule.objects.get_or_create(
                company=target_company,
                module=module,
                defaults={'enabled': True},
            )


class LicenseService:
    """Business logic for license and usage checking."""

    @staticmethod
    def check_limit(company, module_code, feature=None):
        """
        Check if a company has exceeded limits for a module/feature.
        Raises LicenseError if blocked.
        """
        if not company or company.status == Company.Status.EXPIRED:
            raise LicenseError('Company subscription has expired. Please contact support.')

        company_module = CompanyModule.objects.select_related('module').filter(
            company=company,
            module__code=module_code,
            enabled=True,
        ).first()

        if not company_module:
            raise LicenseError(f'Module {module_code} is not enabled for this company.')

        if company_module.is_limit_exceeded():
            raise LicenseError(
                f'Usage limit exceeded for {module_code}. '
                f'Limit: {company_module.usage_limit}, Current: {company_module.usage_count}'
            )

        return company_module

    @staticmethod
    def can_use_module(company, module_code):
        """Check if company can use a module."""
        try:
            LicenseService.check_limit(company, module_code)
            return True
        except LicenseError:
            return False

    @staticmethod
    def can_use_ai(company):
        """Check if company can use AI features."""
        return LicenseService.can_use_module(company, 'ai')

    @staticmethod
    def can_use_ocr(company):
        """Check if company can use OCR features."""
        return LicenseService.can_use_module(company, 'ocr')

    @staticmethod
    def can_create_employee(company):
        """Check if company can create more employees."""
        try:
            LicenseService.check_limit(company, 'employees')
            return True
        except LicenseError:
            return False

    @staticmethod
    def can_generate_report(company):
        """Check if company can generate reports."""
        return LicenseService.can_use_module(company, 'reports')

    @staticmethod
    def can_use_bi(company):
        """Check if company can use BI features."""
        return LicenseService.can_use_module(company, 'bi')

    @staticmethod
    def can_sync_netsuite(company):
        """Check if company can sync NetSuite."""
        return LicenseService.can_use_module(company, 'netsuite')

    @staticmethod
    def increment_usage(company, module_code, amount=1):
        """
        Increment usage count for a module.
        Returns the updated CompanyModule or raises LicenseError.
        """
        company_module = CompanyModule.objects.select_related('module').filter(
            company=company,
            module__code=module_code,
            enabled=True,
        ).first()

        if not company_module:
            raise LicenseError(f'Module {module_code} is not enabled for this company.')

        if company_module.usage_limit and company_module.usage_count >= company_module.usage_limit:
            raise LicenseError(f'Usage limit exceeded for {module_code}.')

        company_module.usage_count = (company_module.usage_count or 0) + amount
        company_module.save(update_fields=['usage_count'])

        return company_module

    @staticmethod
    def get_usage_summary(company):
        """Get usage summary for all company modules."""
        modules = CompanyModule.objects.filter(company=company).select_related('module')
        summary = []
        for cm in modules:
            summary.append({
                'module_code': cm.module.code,
                'module_name': cm.module.name,
                'enabled': cm.enabled,
                'usage_limit': cm.usage_limit,
                'usage_count': cm.usage_count or 0,
                'remaining': (cm.usage_limit - cm.usage_count) if cm.usage_limit else None,
                'percentage': round((cm.usage_count / cm.usage_limit) * 100, 1) if cm.usage_limit else None,
            })
        return summary

    @staticmethod
    def reset_usage(company, module_code=None):
        """Reset usage counters."""
        qs = CompanyModule.objects.filter(company=company)
        if module_code:
            qs = qs.filter(module__code=module_code)
        updated = qs.update(usage_count=0, last_usage_reset=timezone.now())
        return updated


subscription_service = SubscriptionService()
license_service = LicenseService()
