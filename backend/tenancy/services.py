"""
Client Portal business logic.

All methods are company-scoped: ``company`` is always the acting user's
company (``request.user.company``), never supplied by the client. This
guarantees a user from Company A can never reach Company B employees or
settings. Business rules, audit logging and RBAC live here; views stay
thin.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from invitations.models import Invitation, InvitationStatus
from invitations.services import invitation_service
from notifications.models import Notification
from rbac.models import Role, RolePermission, UserRole
from tenancy.models import CompanyModule, CompanySettings


class ClientPortalService:
    """Company-scoped business logic for the client portal."""

    # ── Employees ─────────────────────────────────────────────

    def list_employees(self, *, company, search=None):
        qs = User.objects.filter(company=company).select_related('company').prefetch_related('user_roles__role')
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs.order_by('first_name', 'last_name')

    def get_employee(self, *, company, employee_id):
        return get_object_or_404(
            User.objects.prefetch_related('user_roles__role'),
            pk=employee_id,
            company=company,
        )

    @transaction.atomic
    def create_employee(self, *, company, acting_user, **data):
        email = data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValueError('A user with this email already exists.')

        # TASK 7: Subscription Enforcement — verify employee limit.
        from superadmin.models import CompanyPlan
        current_plan = CompanyPlan.objects.filter(
            company=company,
            status__in=['ACTIVE', 'TRIAL'],
        ).first()
        if current_plan and current_plan.plan.max_employees > 0:
            current_count = User.objects.filter(company=company).count()
            if current_count >= current_plan.plan.max_employees:
                raise ValueError(
                    f'Employee limit of {current_plan.plan.max_employees} reached. '
                    f'Please upgrade your plan to add more employees.'
                )

        employee = User.objects.create(
            email=email.lower().strip(),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            designation=data.get('designation', ''),
            department=data.get('department', ''),
            company=company,
            is_active=False,
            is_email_verified=False,
        )
        employee.set_password(User.objects.make_random_password())
        employee.save(update_fields=['password'])

        role_id = data.get('role_id')
        Invitation.objects.create(
            email=email.lower().strip(),
            company=company,
            role_id=role_id,
            expires_at=timezone.now() + timedelta(days=7),
            created_by=acting_user,
        )

        audit_service.log(
            module=AuditModule.EMPLOYEE,
            action=AuditAction.CREATE,
            entity='User',
            entity_id=str(employee.id),
            company=company,
            user=acting_user,
            new_value={'email': employee.email, 'role_id': role_id},
        )
        return employee

    def resend_employee_invitation(self, *, company, employee_id, acting_user):
        employee = self.get_employee(company=company, employee_id=employee_id)
        invitation = Invitation.objects.filter(
            email=employee.email,
            company=company,
            status=InvitationStatus.PENDING,
        ).order_by('-created_at').first()
        if not invitation:
            raise ValueError('No pending invitation found for this employee.')
        invitation_service.resend_invitation(invitation_id=invitation.id)
        return employee

    def list_employees(self, *, company, search=None, status=None):
        qs = User.objects.filter(company=company).select_related('company').prefetch_related('user_roles__role')
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        if status:
            if status == 'active':
                qs = qs.filter(is_active=True)
            elif status == 'inactive':
                qs = qs.filter(is_active=False)
            elif status == 'pending':
                qs = qs.filter(is_active=False)
        return qs.order_by('first_name', 'last_name')

    @transaction.atomic
    def update_employee(self, *, company, employee_id, acting_user, **data):
        employee = self.get_employee(company=company, employee_id=employee_id)
        old = {
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'designation': employee.designation,
            'department': employee.department,
        }
        for field in ('first_name', 'last_name', 'designation', 'department'):
            if field in data and data[field] is not None:
                setattr(employee, field, data[field])
        employee.save(update_fields=['first_name', 'last_name', 'designation', 'department'])

        # Handle role update if provided
        role_id = data.get('role_id')
        if role_id is not None:
            role = self._validate_role(company=company, role_id=role_id)
            # Replace all existing role assignments
            UserRole.objects.filter(user=employee).delete()
            if role:
                UserRole.objects.create(user=employee, role=role)

        audit_service.log(
            module=AuditModule.EMPLOYEE,
            action=AuditAction.UPDATE,
            entity='User',
            entity_id=str(employee.id),
            company=company,
            user=acting_user,
            old_value=old,
            new_value={
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'designation': employee.designation,
                'department': employee.department,
            },
        )
        return employee

    @transaction.atomic
    def activate_employee(self, *, company, employee_id, acting_user):
        employee = self.get_employee(company=company, employee_id=employee_id)
        employee.is_active = True
        employee.save(update_fields=['is_active'])
        audit_service.log(
            module=AuditModule.EMPLOYEE,
            action=AuditAction.UPDATE,
            entity='User',
            entity_id=str(employee.id),
            company=company,
            user=acting_user,
            old_value={'is_active': False},
            new_value={'is_active': True},
        )
        return employee

    @transaction.atomic
    def deactivate_employee(self, *, company, employee_id, acting_user):
        employee = self.get_employee(company=company, employee_id=employee_id)
        employee.is_active = False
        employee.save(update_fields=['is_active'])
        audit_service.log(
            module=AuditModule.EMPLOYEE,
            action=AuditAction.UPDATE,
            entity='User',
            entity_id=str(employee.id),
            company=company,
            user=acting_user,
            old_value={'is_active': True},
            new_value={'is_active': False},
        )
        return employee

    # ── Roles ─────────────────────────────────────────────────

    def list_assignable_roles(self, *, company):
        """List roles assignable within a company's portal.

        Returns company-specific roles only. System-level roles (Super Admin,
        Company Admin) are excluded — only roles explicitly belonging to the
        company are assignable by its admin when creating employees.
        """
        return Role.objects.filter(company=company).order_by('name')

    def _validate_role(self, *, company, role_id):
        """Return a role only if it is global or belongs to the company."""
        role = get_object_or_404(Role, pk=role_id)
        if role.company_id is not None and role.company_id != company.id:
            raise ValueError('Role does not belong to your company.')
        return role

    @transaction.atomic
    def assign_role(self, *, company, employee_id, role_id, acting_user):
        employee = self.get_employee(company=company, employee_id=employee_id)
        role = self._validate_role(company=company, role_id=role_id)
        user_role, created = UserRole.objects.get_or_create(user=employee, role=role)
        audit_service.log(
            module=AuditModule.RBAC,
            action=AuditAction.UPDATE,
            entity='UserRole',
            entity_id=str(user_role.id),
            company=company,
            user=acting_user,
            new_value={'user_id': str(employee.id), 'role_id': str(role.id)},
        )
        return {'created': created, 'user_role': user_role}

    @transaction.atomic
    def remove_role(self, *, company, employee_id, role_id, acting_user):
        employee = self.get_employee(company=company, employee_id=employee_id)
        role = self._validate_role(company=company, role_id=role_id)
        deleted, _ = UserRole.objects.filter(user=employee, role=role).delete()
        audit_service.log(
            module=AuditModule.RBAC,
            action=AuditAction.UPDATE,
            entity='UserRole',
            entity_id=None,
            company=company,
            user=acting_user,
            new_value={'user_id': str(employee.id), 'role_id': str(role.id), 'deleted': deleted > 0},
        )
        return {'deleted': deleted > 0}

    # ── Company settings ──────────────────────────────────────

    def get_company_settings(self, *, company):
        settings, _ = CompanySettings.objects.get_or_create(company=company)
        return {'company': company, 'settings': settings}

    @transaction.atomic
    def update_company_settings(self, *, company, acting_user, data):
        settings, _ = CompanySettings.objects.get_or_create(company=company)
        old = {
            'contact_email': company.contact_email,
            'contact_phone': company.contact_phone,
            'country': company.country,
            'timezone': settings.timezone,
            'currency': settings.currency,
            'language': settings.language,
            'date_format': settings.date_format,
            'number_format': settings.number_format,
        }

        company_changed = []
        settings_changed = []

        for field in ('contact_email', 'contact_phone', 'country'):
            if field in data:
                setattr(company, field, data[field])
                company_changed.append(field)
        if company_changed:
            company.save(update_fields=company_changed)

        for field in ('timezone', 'currency', 'language', 'date_format', 'number_format'):
            if field in data:
                setattr(settings, field, data[field])
                settings_changed.append(field)
        if settings_changed:
            settings.save(update_fields=settings_changed)

        audit_service.log(
            module=AuditModule.SETTINGS,
            action=AuditAction.UPDATE,
            entity='CompanySettings',
            entity_id=str(settings.id),
            company=company,
            user=acting_user,
            old_value=old,
            new_value={
                'contact_email': company.contact_email,
                'contact_phone': company.contact_phone,
                'country': company.country,
                'timezone': settings.timezone,
                'currency': settings.currency,
                'language': settings.language,
                'date_format': settings.date_format,
                'number_format': settings.number_format,
            },
        )
        return {'company': company, 'settings': settings}

    # ── Notifications (user-scoped) ───────────────────────────

    def list_notifications(self, *, user, is_read=None, limit=20, offset=0):
        qs = Notification.objects.filter(user=user).select_related('company')
        if is_read is not None:
            qs = qs.filter(is_read=is_read)
        qs = qs.order_by('-created_at')
        count = qs.count()
        return qs[offset:offset + limit], count

    def unread_notifications_count(self, *, user):
        return Notification.objects.filter(user=user, is_read=False).count()

    def mark_notification_read(self, *, notification_id, user):
        notification = get_object_or_404(Notification, pk=notification_id, user=user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        return notification

    def mark_all_notifications_read(self, *, user):
        updated = Notification.objects.filter(user=user, is_read=False).update(
            is_read=True, read_at=timezone.now(),
        )
        return {'updated_count': updated}

    # ── Client me context ─────────────────────────────────────

    def get_client_context(self, *, user):
        company = getattr(user, 'company', None)
        modules = []
        permissions = []
        if company:
            modules = list(
                CompanyModule.objects.filter(company=company, enabled=True)
                .select_related('module')
                .values('module_id', 'module__code', 'module__name')
            )
        role_names = list(user.user_roles.values_list('role__name', flat=True))
        # Collect permission codes granted to the user via their roles.
        permissions = list(
            RolePermission.objects.filter(
                role__user_roles__user=user,
            ).values_list('permission__code', flat=True).distinct()
        )
        # TASK 7: Employee limit info
        employee_count = 0
        plan_info = None
        if company:
            from superadmin.models import CompanyPlan
            employee_count = User.objects.filter(company=company).count()
            current_plan = CompanyPlan.objects.filter(
                company=company,
                status__in=['ACTIVE', 'TRIAL'],
            ).first()
            if current_plan:
                plan_info = {
                    'plan_name': current_plan.plan.name,
                    'max_employees': current_plan.plan.max_employees,
                    'employee_count': employee_count,
                }
        return {
            'user': user,
            'company': company,
            'modules': modules,
            'roles': role_names,
            'permissions': permissions,
            'plan': plan_info,
        }
