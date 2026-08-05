from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import User
from notifications.models import Notification
from rbac.models import Role, UserRole
from superadmin.models import (
    CompanyPlan,
    CompanyPlanStatus,
    Plan,
    PlanStatus,
    SupportSession,
    SupportSessionStatus,
)
from tenancy.models import Company, CompanyModule, Module


class SuperAdminService:
    """Business logic for AGSuite Super Admin operations."""

    def get_dashboard_summary(self):
        company_summary = Company.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status=Company.Status.ACTIVE)),
            suspended=Count("id", filter=Q(status=Company.Status.SUSPENDED)),
            trial=Count("id", filter=Q(status=Company.Status.TRIAL)),
        )

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

    def get_company_plan_history(self, company_id):
        return list(
            CompanyPlan.objects.filter(company_id=company_id)
            .select_related('plan', 'company')
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
                'created_at',
            )
        )
    @transaction.atomic
    def assign_plan(self, *, company_id, plan_id, status=None):
        company = get_object_or_404(Company, pk=company_id)
        plan = get_object_or_404(Plan, pk=plan_id)
        normalized_status = status or CompanyPlanStatus.ACTIVE

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
                'start_date': timezone.now().date(),
                'status': normalized_status,
                'is_auto_renew': False,
            },
        )

        if not created:
            company_plan.start_date = company_plan.start_date or timezone.now().date()
            company_plan.status = normalized_status
            company_plan.end_date = None if normalized_status in [CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL] else company_plan.end_date
            company_plan.is_auto_renew = company_plan.is_auto_renew
            company_plan.save(update_fields=['start_date', 'status', 'end_date'])

        return company_plan
    @transaction.atomic
    def upgrade_plan(self, *, company_id, plan_id):
        company = get_object_or_404(Company, pk=company_id)
        plan = get_object_or_404(Plan, pk=plan_id)
        current = CompanyPlan.objects.filter(company=company).order_by('-start_date').first()
        if current:
            current.status = CompanyPlanStatus.CANCELLED
            current.end_date = timezone.now().date()
            current.save(update_fields=['status', 'end_date'])
        return self.assign_plan(company_id=company.id, plan_id=plan.id, status=CompanyPlanStatus.ACTIVE)

    def downgrade_plan(self, *, company_id, plan_id):
        return self.assign_plan(company_id=company_id, plan_id=plan_id, status=CompanyPlanStatus.TRIAL)

    @transaction.atomic
    def cancel_plan(self, *, company_id):
        company = get_object_or_404(Company, pk=company_id)
        company_plan = CompanyPlan.objects.filter(company=company).order_by('-start_date').first()
        if not company_plan:
            raise ValueError('No active plan found for this company.')
        company_plan.status = CompanyPlanStatus.CANCELLED
        company_plan.end_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'end_date'])
        return company_plan
    @transaction.atomic
    def renew_plan(self, *, company_id, plan_id=None):
        company = get_object_or_404(Company, pk=company_id)
        company_plan = CompanyPlan.objects.filter(company=company).order_by('-start_date').first()
        if company_plan is None and plan_id is None:
            raise ValueError('Plan selection is required when renewing a cancelled plan.')
        if company_plan and company_plan.status == CompanyPlanStatus.CANCELLED and plan_id is None:
            plan_id = company_plan.plan_id
        if plan_id is not None:
            plan = get_object_or_404(Plan, pk=plan_id)
            company_plan = self.assign_plan(company_id=company.id, plan_id=plan.id, status=CompanyPlanStatus.ACTIVE)
            return company_plan
        company_plan.status = CompanyPlanStatus.ACTIVE
        company_plan.start_date = timezone.now().date()
        company_plan.save(update_fields=['status', 'start_date'])
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

    @transaction.atomic
    def assign_user_role(
    self,
    *,
    user_id,
    role_id,
        ):
        user = get_object_or_404(
            User,
            pk=user_id,
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

    @transaction.atomic
    def create_employee(
        self,
        *,
        email,
        password=None,
        first_name="",
        last_name="",
        company_id=None,
        role_ids=None,
    ):
        if User.objects.filter(email=email).exists():
            raise ValueError(
                "Employee with this email already exists."
            )

        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company_id=company_id,
            is_active=True,
            is_email_verified=True,
        )

        if password:
            user.set_password(password)
            user.save(update_fields=["password"])

        if role_ids:

            roles = Role.objects.filter(
                pk__in=role_ids
            )

            UserRole.objects.bulk_create(
                [
                    UserRole(
                        user=user,
                        role=role,
                    )
                    for role in roles
                ],
                ignore_conflicts=True,
            )

        return user

    def update_employee(self, *, employee_id, **data):
        user = get_object_or_404(User, pk=employee_id)
        for field in ['first_name', 'last_name', 'mobile_number', 'designation', 'department', 'company']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        if 'is_active' in data:
            user.is_active = data['is_active']
        user.save()
        return user

    def deactivate_employee(self, *, employee_id):
        user = get_object_or_404(User, pk=employee_id)
        user.is_active = False
        user.save(update_fields=['is_active'])
        return user

    def activate_employee(self, *, employee_id):
        user = get_object_or_404(User, pk=employee_id)
        user.is_active = True
        user.save(update_fields=['is_active'])
        return user
