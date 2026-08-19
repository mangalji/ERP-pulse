from __future__ import annotations

from datetime import timedelta
import re
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from common.contact_validation import normalize_phone

from accounts.models import User, Gender
from invitations.models import Invitation, InvitationStatus
from invitations.services import invitation_service
from notifications.models import Notification
from rbac.models import Role, UserRole
from superadmin.models import (
    CompanyPlan,
    CompanyPlanStatus,
    Plan,
    PlanStatus,
    SupportSession,
    SupportSessionStatus,
    SubscriptionHistory,
    Transaction,
    DiscountType,
    BillingCycle,
    PaymentStatus,
    TransactionStatus,
)
from tenancy.models import Company, CompanyModule, Module, CompanyDeletionHistory, CompanySuspensionReason
from tenancy.services import company_lifecycle_service

class SuperAdminService:
    """Business logic for AGSuite Super Admin operations."""

    def get_dashboard_summary(self):
        company_summary = Company.objects.aggregate(
            total=Count("id",filter=Q(is_deleted=False)),
            active=Count("id", filter=Q(is_deleted=False, status=Company.Status.ACTIVE)),
            suspended=Count("id", filter=Q(is_deleted=False, status=Company.Status.SUSPENDED)),
            trial=Count("id", filter=Q(is_deleted=False, status=Company.Status.TRIAL)),
            soft_deleted = Count(
                "id",
                filter=Q(is_deleted=True)
            )
        )
        permanent_deleted = CompanyDeletionHistory.objects.count()

        user_summary = User.objects.aggregate(
            agsuite=Count("id", filter=Q(company__isnull=True)),
            client=Count("id", filter=Q(company__isnull=False)),
        )

        plan_summary = Plan.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status=PlanStatus.ACTIVE)),
        )

        support_summary = SupportSession.objects.aggregate(
            total=Count("id"),
            active=Count(
                "id",
                filter=Q(status=SupportSessionStatus.ACTIVE),
            ),
        )

        module_summary = Module.objects.aggregate(
            total=Count("id"),
            enabled=Count("id", filter=Q(is_active=True)),
        )

        return {
            "total_companies": company_summary["total"],
            "active_companies": company_summary["active"],
            "suspended_companies": company_summary["suspended"],
            "trial_companies": company_summary["trial"],
            "soft_deleted_companies": company_summary["soft_deleted"],
            "permanently_deleted_companies": permanent_deleted,
            "total_agsuite_employees": user_summary["agsuite"],
            "total_client_employees": user_summary["client"],
            "total_plans": plan_summary["total"],
            "active_plans": plan_summary["active"],
            "total_support_sessions": support_summary["total"],
            "active_support_sessions": support_summary["active"],
            "total_modules": module_summary["total"],
            "enabled_modules": module_summary["enabled"],
            "recent_company_registrations": list(
                Company.objects.order_by("-created_at")
                .values(
                    "id",
                    "name",
                    "code",
                    "status",
                    "created_at",
                )[:5]
            ),
        }
    @transaction.atomic
    def permanently_delete_company(self, *, company_id, deleted_by=None):
        """
        Permanently delete a company after its 15-day recovery period.

        A minimal deletion-history snapshot is preserved before the
        company is hard-deleted. All company-owned records configured
        with CASCADE are removed with the company.
        """
        company = Company.objects.select_for_update().filter(
            pk=company_id,
        ).first()

        if not company:
            raise ValueError('Company not found.')

        if not company.is_deleted:
            raise ValueError(
                'Only soft-deleted companies can be permanently deleted.'
            )

        if company.deleted_at is None:
            raise ValueError(
                'Company does not have a valid deletion timestamp.'
            )

        permanently_deleted_at = timezone.now()

        history = CompanyDeletionHistory.objects.create(
            company_id_snapshot=company.id,
            company_name=company.name,
            company_code=company.code,
            soft_deleted_at=company.deleted_at,
            permanently_deleted_at=permanently_deleted_at,
            deleted_by=deleted_by,
        )

        company_name = company.name
        company_code = company.code

        company.delete()

        return {
            'history_id': str(history.id),
            'company_id': str(history.company_id_snapshot),
            'company_name': company_name,
            'company_code': company_code,
            'permanently_deleted_at': permanently_deleted_at,
        }
        
    def get_company_plan_history(self, company_id):
        return list(
            CompanyPlan.objects.filter(company_id=company_id)
            .select_related('plan', 'company', 'assigned_by')
            .order_by('-start_date', '-created_at')
            .values(
                'id',
                'company_id',
                'plan_id',
                'plan__name',
                'status',
                'start_date',
                'end_date',
                'is_auto_renew',
                'discount_type',
                'discount_value',
                'billing_cycle',
                'original_price',
                'final_price',
                'assigned_by__email',
                'created_at',
            )
        )

    def get_company_transactions(self, company_id):
        return list(
            Transaction.objects.filter(company_id=company_id)
            .select_related('plan')
            .order_by('-created_at')
            .values(
                'id',
                'transaction_id',
                'plan__name',
                'original_amount',
                'final_amount',
                'discount_amount',
                'billing_cycle',
                'payment_status',
                'transaction_status',
                'payment_method',
                'invoice_number',
                'created_at',
            )
        )
    @transaction.atomic
    def assign_plan(
        self, 
        *, 
        company_id, 
        plan_id, 
        discount_type=None, 
        discount_value=None,
        billing_cycle=None, 
        assigned_by=None, 
        status=None, 
        start_date=None, 
        end_date=None
        ):
        company = get_object_or_404(Company, pk=company_id)
        plan = get_object_or_404(Plan, pk=plan_id)
        normalized_status = status or CompanyPlanStatus.ACTIVE
        normalized_discount_type = discount_type or DiscountType.NONE
        normalized_discount_value = discount_value or 0
        normalized_billing_cycle = billing_cycle or BillingCycle.MONTHLY

        start_date = start_date or timezone.now().date()

        if end_date is not None and end_date < start_date:
            raise ValueError(
                'Plan end date cannot be earlier than the start date.'
            )

        original_price = plan.yearly_price if normalized_billing_cycle == BillingCycle.YEARLY else plan.monthly_price
        final_price = self._calculate_final_price(original_price, normalized_discount_type, normalized_discount_value)

        active_existing = CompanyPlan.objects.filter(
            company=company,
            status__in=[CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL],
        ).exclude(plan=plan)

        if active_existing.exists() and normalized_status in [CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL]:
            active_existing.update(status=CompanyPlanStatus.CANCELLED, end_date=timezone.now().date())

        company_plan, created = CompanyPlan.objects.get_or_create(
            company=company,
            plan=plan,
            defaults={
                'start_date': start_date,
                'end_data':end_date,
                'status': normalized_status,
                'is_auto_renew': False,
                'discount_type': normalized_discount_type,
                'discount_value': normalized_discount_value,
                'billing_cycle': normalized_billing_cycle,
                'original_price': original_price,
                'final_price': final_price,
                'assigned_by': assigned_by,
            },
        )

        if not created:
            company_plan.start_date = start_date
            company_plan.status = normalized_status

            if end_date is not None:
                company_plan.end_date = end_date

            elif normalized_status in [
                CompanyPlanStatus.ACTIVE,
                CompanyPlanStatus.TRIAL,
            ]:
                company_plan.end_date = None
            
            company_plan.is_auto_renew = company_plan.is_auto_renew
            company_plan.discount_type = normalized_discount_type
            company_plan.discount_value = normalized_discount_value
            company_plan.billing_cycle = normalized_billing_cycle
            company_plan.original_price = original_price
            company_plan.final_price = final_price
            company_plan.assigned_by = assigned_by
            company_plan.save(update_fields=[
                'start_date', 'status', 'end_date', 'discount_type', 'discount_value',
                'billing_cycle', 'original_price', 'final_price', 'assigned_by'
                ])

        self._create_subscription_history(
            company=company, plan=plan, company_plan=company_plan,
            original_price=original_price, discount_type=normalized_discount_type,
            discount_value=normalized_discount_value, final_price=final_price,
            billing_cycle=normalized_billing_cycle, assigned_by=assigned_by,
            status_before=CompanyPlanStatus.CANCELLED, status_after=normalized_status,
            change_type='assign',
        )

        self._create_transaction(
            company=company, plan=plan, original_amount=original_price,
            final_amount=final_price, billing_cycle=normalized_billing_cycle,
        )
        company.status = company_lifecycle_service.get_effective_status(
            company=company
        )
        if company.status in [
            Company.Status.ACTIVE,
            Company.Status.TRIAL,
            ]:
            company.suspension_reason = CompanySuspensionReason.NONE
        elif company.suspension_reason != CompanySuspensionReason.MANUAL:
            company.suspension_reason = CompanySuspensionReason.PLAN
        company.save(
            update_fields=[
                'status',
                'suspension_reason'
            ]
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
                     billing_cycle=None, assigned_by=None):
        company = get_object_or_404(Company, pk=company_id)
        plan = get_object_or_404(Plan, pk=plan_id)
        old_plan = CompanyPlan.objects.filter(company=company).order_by('-start_date').first()
        if old_plan:
            old_status = old_plan.status
            old_plan.status = CompanyPlanStatus.CANCELLED
            old_plan.end_date = timezone.now().date()
            old_plan.save(update_fields=['status', 'end_date'])
        else:
            old_status = None

        new_plan = self.assign_plan(
            company_id=company.id, plan_id=plan.id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, assigned_by=assigned_by,
            status=CompanyPlanStatus.ACTIVE,
        )

        if old_status:
            SubscriptionHistory.objects.filter(
                company=company, company_plan=old_plan
            ).update(status_after=CompanyPlanStatus.CANCELLED)

        return new_plan

    @transaction.atomic
    def downgrade_plan(self, *, company_id, plan_id, discount_type=None, discount_value=None,
                       billing_cycle=None, assigned_by=None):
        company = get_object_or_404(Company, pk=company_id)
        plan = get_object_or_404(Plan, pk=plan_id)
        old_plan = CompanyPlan.objects.filter(company=company).order_by('-start_date').first()
        if old_plan:
            old_status = old_plan.status
            old_plan.status = CompanyPlanStatus.CANCELLED
            old_plan.end_date = timezone.now().date()
            old_plan.save(update_fields=['status', 'end_date'])
        else:
            old_status = None

        new_plan = self.assign_plan(
            company_id=company.id, plan_id=plan.id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, assigned_by=assigned_by,
            status=CompanyPlanStatus.TRIAL,
        )

        if old_status:
            SubscriptionHistory.objects.filter(
                company=company, company_plan=old_plan
            ).update(status_after=CompanyPlanStatus.CANCELLED)

        return new_plan

    @transaction.atomic
    def cancel_plan(self, *, company_id, assigned_by=None):
        company = get_object_or_404(Company, pk=company_id)
        company_plan = CompanyPlan.objects.filter(company=company).order_by('-start_date').first()
        if not company_plan:
            raise ValueError('No active plan found for this company.')
        old_status = company_plan.status
        company_plan.status = CompanyPlanStatus.CANCELLED
        company_plan.end_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'end_date'])
        company.status = Company.Status.SUSPENDED
        company.suspension_reason = CompanySuspensionReason.PLAN
        company.save(
            update_fields=[
                'status',
                'suspension_reason',
            ]
        )

        self._create_subscription_history(
            company=company, plan=company_plan.plan, company_plan=company_plan,
            original_price=company_plan.original_price, discount_type=company_plan.discount_type,
            discount_value=company_plan.discount_value, final_price=company_plan.final_price,
            billing_cycle=company_plan.billing_cycle, assigned_by=assigned_by,
            status_before=old_status, status_after=CompanyPlanStatus.CANCELLED,
            change_type='cancel',
        )
        return company_plan
    
    @transaction.atomic
    def renew_plan(
        self, 
        *, 
        company_id, 
        plan_id=None, 
        discount_type=None, 
        discount_value=None, 
        billing_cycle=None, 
        assigned_by=None
        ):
        company = get_object_or_404(Company, pk=company_id)
        company_plan = CompanyPlan.objects.filter(company=company).order_by('-start_date').first()
        if company_plan is None and plan_id is None:
            raise ValueError('Plan selection is required when renewing a cancelled plan.')
        if company_plan and company_plan.status == CompanyPlanStatus.CANCELLED and plan_id is None:
            plan_id = company_plan.plan_id
        if plan_id is not None:
            plan = get_object_or_404(Plan, pk=plan_id)
            company_plan = self.assign_plan(
                company_id=company.id, plan_id=plan.id,
                discount_type=discount_type, discount_value=discount_value,
                billing_cycle=billing_cycle, assigned_by=assigned_by,
                status=CompanyPlanStatus.ACTIVE,
            )
            return company_plan
        company_plan.status = CompanyPlanStatus.ACTIVE
        company_plan.start_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'start_date'])
        company.status = company_lifecycle_service.get_effective_status(
            company=company
        )

        company.suspension_reason = (
            CompanySuspensionReason.NONE
            if company.status in [
                Company.Status.ACTIVE,
                Company.Status.TRIAL,
            ]
            else CompanySuspensionReason.PLAN
        )

        company.save(
            update_fields=[
                'status',
                'suspension_reason',
            ]
        )
        return company_plan

    def list_notifications(self, *, user, searchable=None, is_read=None, limit=None, offset=0):
        qs = Notification.objects.filter(user=user).select_related('company')
        if searchable:
            qs = qs.filter(Q(title__icontains=searchable) | Q(message__icontains=searchable))
        if is_read is not None:
            qs = qs.filter(is_read=is_read)
        qs = qs.order_by('-created_at')
        if limit is not None:
            return list(qs[offset:offset + limit])
        return list(qs[offset:])

    def unread_notifications_count(self, *, user):
        return Notification.objects.filter(user=user, is_read=False).count()

    def mark_notification_read(self, *, notification_id, user):
        notification = get_object_or_404(Notification, pk=notification_id, user=user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        return notification

    def mark_all_notifications_read(self, *, user):
        updated_count = Notification.objects.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )
        return {'updated_count': updated_count}

    def get_employee_roles(self, *, user):
        return list(user.user_roles.select_related('role').values('role_id', 'role__name'))


    def ensure_employee_company_operational(self, *, employee):
        company = getattr(employee, 'company', None)

        # AGSuite internal user — no client company restriction.
        if company is None:
            return

        if company.is_deleted:
            raise ValueError(
                "This employee's company no longer exists."
            )

        if company_lifecycle_service.get_effective_status(
            company=company
        ) == Company.Status.SUSPENDED:
            raise ValueError(
                "This company's account is currently suspended. "
                "Employee operations are unavailable."
            )


    @transaction.atomic
    def assign_user_role( self, *, user_id, role_id):
        user = get_object_or_404(
            User,
            pk=user_id,
        )
        self.ensure_employee_company_operational(
            employee=user
        )

        role = get_object_or_404(
            Role,
            pk=role_id,
        )

        user_role, created = UserRole.objects.get_or_create(
            user=user,
            role=role,
        )

        return {
            "created": created,
            "user_role": user_role,
        }
    
    def remove_user_role(self, *, user_id, role_id):
        user = get_object_or_404(User, pk=user_id)
        self.ensure_employee_company_operational(
            employee=user
        )
        deleted, _ = UserRole.objects.filter(user=user, role_id=role_id).delete()
        return {'deleted': deleted > 0}

    def set_company_module_state(self, *, company_id, module_id, enabled):
        company = get_object_or_404(Company, pk=company_id)
        module = get_object_or_404(Module, pk=module_id)
        company_module, _ = CompanyModule.objects.get_or_create(company=company, module=module)
        company_module.enabled = enabled
        company_module.save(update_fields=['enabled'])
        return company_module

    @transaction.atomic
    def bulk_set_company_modules(
    self,
    *,
    company_id,
    module_ids,
    enabled,
):
        company = get_object_or_404(Company, pk=company_id)

        modules = Module.objects.filter(pk__in=module_ids)

        company_modules = []

        for module in modules:
            company_module, _ = CompanyModule.objects.get_or_create(
                company=company,
                module=module,
            )

            company_module.enabled = enabled

            company_modules.append(company_module)

        CompanyModule.objects.bulk_update(
            company_modules,
            ["enabled"],
        )
        return company_modules

    def list_company_modules(self, *, company_id):
        company = get_object_or_404(Company, pk=company_id)
        return list(
            CompanyModule.objects.filter(company=company)
            .select_related('module')
            .order_by('module__sort_order', 'module__name')
            .values('id', 'module_id', 'module__name', 'module__code', 'enabled', 'usage_limit')
        )

    def start_support_session(self, *, company_id, support_user_id, reason, ip_address=None):
        company = get_object_or_404(Company, pk=company_id)
        support_user = get_object_or_404(User, pk=support_user_id)
        if SupportSession.objects.filter(company=company, status=SupportSessionStatus.ACTIVE).exists():
            raise ValueError('Another support session is already active for this company.')
        session = SupportSession.objects.create(
            company=company,
            support_user=support_user,
            reason=reason,
            status=SupportSessionStatus.ACTIVE,
            ip_address=ip_address,
        )
        return session

    def end_support_session(self, *, session_id):
        session = get_object_or_404(SupportSession, pk=session_id)
        session.status = SupportSessionStatus.ENDED
        session.ended_at = timezone.now()
        session.save(update_fields=['status', 'ended_at'])
        return session

    def list_support_sessions(self, *, company_id=None, search=None):
        qs = SupportSession.objects.select_related('company', 'support_user')
        if company_id:
            qs = qs.filter(company_id=company_id)
        if search:
            qs = qs.filter(Q(reason__icontains=search) | Q(company__name__icontains=search))
        return list(qs.order_by('-started_at')[:50])

    def create_employee(self, *, email, first_name, last_name, company_id, role, acting_user, request=None,mobile_number=None, country=None, gender=None):
        """Create a pending company user and send the existing invitation flow."""


        normalized_email = email.lower().strip()

        if User.objects.filter(email__iexact=normalized_email).exists():
            raise ValueError("A user with this email already exists.")

        first_name = (first_name or '').strip()
        last_name = (last_name or '').strip()

        if len(normalized_email) > 40:
            raise ValueError("Email must not exceed 40 characters.")
        
        if len(first_name) > 20:
            raise ValueError("First name must not exceed 20 characters.")
        
        if len(last_name) > 20:
            raise ValueError("Last name must not exceed 20 characters.")
        
        name_pattern = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$")
        
        if not name_pattern.fullmatch(first_name):
            raise ValueError(
                "First name may contain letters, spaces, hyphens, and apostrophes only."
            )
        
        if not name_pattern.fullmatch(last_name):
            raise ValueError(
                "Last name may contain letters, spaces, hyphens, and apostrophes only."
            )

        if not first_name:
            raise ValueError("First name is required.")
        if not last_name:
            raise ValueError("Last name is required.")

        if not country:
            raise ValueError("Country is required.")
        if gender not in dict(Gender.choices):
            raise ValueError("Invalid gender selected.")  

        normalized_phone = None
        phone_country_code = ''
        if mobile_number:
            try:
                normalized = normalize_phone(
                    phone=mobile_number,
                    country=country,
                )
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            normalized_phone = normalized.number
            country = normalized.country_code
            phone_country_code = normalized.dial_code  

            if User.objects.filter(mobile_number=normalized_phone).exists():
                raise ValueError("A user with this mobile number already exists.")

        if not company_id:
            raise ValueError("company_id is required.")
        company = Company.objects.filter(pk=company_id).first()
        if not company:
            raise ValueError("Company not found.")
        if company.is_deleted:
            raise ValueError(
                "This company no longer exists."
            )
        if company_lifecycle_service.get_effective_status(
            company=company
        ) == Company.Status.SUSPENDED:
            raise ValueError(
                "This company's account is currently suspended. "
                "New employee invitations are unavailable."
            )

        role_name = {
            "admin": "Company Admin",
            "employee": "Employee",
        }.get(role)
        if not role_name:
            raise ValueError("Invalid role selected.")

        selected_role = Role.objects.filter(
            name__iexact=role_name,
            company__isnull=True,
        ).first()
        if not selected_role:
            raise ValueError(f"Required role '{role_name}' is not configured.")

        # User, RBAC assignment, and invitation must succeed or fail together.
        with transaction.atomic():
            user = User(
                email=normalized_email,
                first_name=first_name,
                last_name=last_name,
                mobile_number=normalized_phone,
                country=country.strip().upper(),
                phone_country_code=phone_country_code,
                gender=gender,
                company=company,
                is_active=False,
                is_email_verified=False,
            )
            user.set_unusable_password()
            user.save()
            UserRole.objects.create(user=user, role=selected_role)

            invitation = invitation_service.create_invitation(
                email=normalized_email,
                company_id=company.id,
                role_id=selected_role.id,
                created_by=acting_user,
                request=request,
                send_email=False,
            )

        # Delivery happens after the database transaction commits. A failed
        # delivery leaves the pending user and invitation available to resend.
        _, invitation_email_sent = invitation_service.send_invitation(
            invitation_id=invitation.id,
            request=request,
            return_delivery_status=True,
        )
        return {
            "user": user,
            "invitation": invitation,
            "invitation_email_sent": invitation_email_sent,
        }

    def resend_employee_invitation(self, *, employee_id, acting_user, request=None):
        employee = User.objects.filter(pk=employee_id).select_related('company').first()
    
        if not employee:
            raise ValueError("Employee not found.")

        # if employee.company is None:
        #     return ...

        if employee.company and employee.company.is_deleted:
            raise ValueError(
                "This employee's company no longer exists."
            )
        if(
            employee.company
            and company_lifecycle_service.get_effective_status(
                company=employee.company
            ) == Company.Status.SUSPENDED
        ):
            raise ValueError(
                "This company's account is currently suspended. "
                "Invitation operations are unavailable."
            )

        if company_lifecycle_service.get_effective_status(
            company=employee.company
        ) == Company.Status.SUSPENDED:
            raise ValueError(
                "This company's account is currently suspended. "
                "Invitation operations are unavailable."
            )
    
        invitation = (
            Invitation.objects
            .filter(
                email__iexact=employee.email,
                company=employee.company,
                status=InvitationStatus.PENDING,
            )
            .order_by('-created_at')
            .first()
        )
    
        if not invitation:
            raise ValueError("No pending invitation found for this user.")
    
        invitation_service.resend_invitation(
            invitation_id=invitation.id,
            request=request,
        )
    
        return invitation

    def update_employee(self, *, employee_id, **data):
        user = get_object_or_404(User, pk=employee_id)
        if user.company:
            if user.company.is_deleted:
                raise ValueError(
                    "This employee's company no longer exists."
                )

            if company_lifecycle_service.get_effective_status(
                company=user.company
            ) == Company.Status.SUSPENDED:
                raise ValueError(
                    "This company's account is currently suspended. "
                    "Employee operations are unavailable."
                )
        
        if 'first_name' in data and data['first_name'] is not None:
            first_name = data['first_name'].strip()

            if len(first_name) < 2:
                raise ValueError("First name must contain at least 2 characters.")

            if len(first_name) > 20:
                raise ValueError("First name must not exceed 20 characters.")

            if not re.fullmatch(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$", first_name):
                raise ValueError(
                    "First name may contain letters, spaces, hyphens, and apostrophes only."
                )

            user.first_name = first_name


        if 'last_name' in data and data['last_name'] is not None:
            last_name = data['last_name'].strip()

            if len(last_name) < 2:
                raise ValueError("Last name must contain at least 2 characters.")

            if len(last_name) > 20:
                raise ValueError("Last name must not exceed 20 characters.")

            if not re.fullmatch(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$", last_name):
                raise ValueError(
                    "Last name may contain letters, spaces, hyphens, and apostrophes only."
                )

            user.last_name = last_name


        if 'country' in data and data['country']:
            country = data['country'].strip().upper()

            normalized_phone = normalize_phone(
                phone=data.get('mobile_number') or user.mobile_number,
                country=country,
            )

            user.country = normalized_phone.country_code
            user.phone_country_code = normalized_phone.dial_code
            user.mobile_number = normalized_phone.number

        elif 'mobile_number' in data and data['mobile_number']:
            normalized_phone = normalize_phone(
                phone=data['mobile_number'],
                country=user.country,
            )

            user.mobile_number = normalized_phone.number
            user.phone_country_code = normalized_phone.dial_code


        if 'gender' in data and data['gender'] is not None:
            if data['gender'] not in dict(Gender.choices):
                raise ValueError("Invalid gender selected.")

            user.gender = data['gender']


        for field in ['designation', 'department', 'company']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])

        if 'is_active' in data:
            user.is_active = data['is_active']
        user.save()
        return user

    def deactivate_employee(self, *, employee_id):
        user = get_object_or_404(
            User.objects.select_related('company'),
            pk=employee_id,
        )

        if user.company:
            if user.company.is_deleted:
                raise ValueError(
                    "This employee's company no longer exists."
                )

            if company_lifecycle_service.get_effective_status(
                company=user.company
            ) == Company.Status.SUSPENDED:
                raise ValueError(
                    "This company's account is currently suspended. "
                    "Employee operations are unavailable."
                )

        user.is_active = False
        user.save(update_fields=['is_active'])

        return user

    def activate_employee(self, *, employee_id):
        user = get_object_or_404(
            User.objects.select_related('company'),
            pk=employee_id,
        )

        if user.company:
            if user.company.is_deleted:
                raise ValueError(
                    "This employee's company no longer exists."
                )

            if company_lifecycle_service.get_effective_status(
                company=user.company
            ) == Company.Status.SUSPENDED:
                raise ValueError(
                    "This company's account is currently suspended. "
                    "Employee operations are unavailable."
                )

        user.is_active = True
        user.save(update_fields=['is_active'])

        return user