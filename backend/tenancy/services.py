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

from common.contact_validation import normalize_phone

from accounts.models import User, Gender
from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from invitations.models import Invitation, InvitationStatus
from invitations.services import invitation_service
from notifications.models import Notification
from rbac.models import Role, RolePermission, UserRole
from tenancy.models import CompanyModule, CompanySettings, Company, CompanySuspensionReason

from superadmin.models import CompanyPlan, CompanyPlanStatus

class ClientPortalService:
    """Company-scoped business logic for the client portal."""

    def _ensure_company_operational(self, *, company):
        company_lifecycle_service.ensure_operational(
            company=company
        )

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
        self._ensure_company_operational(company=company)
        return get_object_or_404(
            User.objects.prefetch_related('user_roles__role'),
            pk=employee_id,
            company=company,
        )

    @transaction.atomic
    def create_employee(self, *, company, acting_user, **data):
        self._ensure_company_operational(company=company)
        email = (data.get('email') or '').lower().strip()
        if not email:
            raise ValueError('Email is required.')
        if User.objects.filter(email__iexact=email).exists():
            raise ValueError('A user with this email already exists.')

        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        if not first_name:
            raise ValueError('First name is required.')
        if not last_name:
            raise ValueError('Last name is required.')

        country = (data.get('country') or '').strip().upper()
        if not country:
            raise ValueError('Country is required.')

        gender = data.get('gender')
        if gender not in dict(Gender.choices):
            raise ValueError('Invalid gender selected.')

        mobile_number = data.get('mobile_number')
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
                raise ValueError('A user with this mobile number already exists.')

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
            email=email,
            first_name=first_name,
            last_name=last_name,
            mobile_number=normalized_phone,
            country=country,
            phone_country_code=phone_country_code,
            gender=gender,
            designation=data.get('designation', ''),
            department=data.get('department', ''),
            company=company,
            is_active=False,
            is_email_verified=False,
        )
        employee.set_unusable_password()
        employee.save(update_fields=['password'])

        role_id = data.get('role_id')
        role = self._validate_role(company=company,role_id=role_id)
        UserRole.objects.create(
            user=employee,
            role=role,
        )
        invitation = invitation_service.create_invitation(
            email=email.lower().strip(),
            company_id=company.id,
            role_id=role.id,
            created_by=acting_user,
        )

        audit_service.log(
            module=AuditModule.EMPLOYEE,
            action=AuditAction.CREATE,
            entity='User',
            entity_id=str(employee.id),
            company=company,
            user=acting_user,
            new_value={
                        'email': employee.email, 
                       'role_id': str(role_id) if role_id else None,
                       },
        )
        return employee

    def resend_employee_invitation(self, *, company, employee_id, acting_user):
        self._ensure_company_operational(company=company)
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
        self._ensure_company_operational(company=company)
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
        self._ensure_company_operational(company=company)
        employee = self.get_employee(company=company, employee_id=employee_id)
        old = {
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'designation': employee.designation,
            'department': employee.department,
        }
        update_fields = []

        for field in ('first_name', 'last_name', 'designation', 'department'):
            if field in data and data[field] is not None:
                value = data[field].strip() if isinstance(data[field], str) else data[field]
                if field in ('first_name', 'last_name') and not value:
                    raise ValueError(f'{field.replace("_", " ").title()} is required.')
                setattr(employee, field, value)
                update_fields.append(field)

        if 'gender' in data:
            gender = data.get('gender')
            if gender not in dict(User.Gender.choices):
                raise ValueError('Invalid gender selected.')
            employee.gender = gender
            update_fields.append('gender')

        if 'country' in data or 'mobile_number' in data:
            new_country = (data.get('country') or employee.country or '').strip().upper()
            new_phone = data.get('mobile_number', employee.mobile_number)
            if new_phone:
                if not new_country:
                    raise ValueError('Country is required when updating a phone number.')
                try:
                    normalized = normalize_phone(
                        phone=new_phone,
                        country=new_country,
                    )
                except ValueError as exc:
                    raise ValueError(str(exc)) from exc
                if User.objects.filter(mobile_number=normalized.number).exclude(pk=employee.pk).exists():
                    raise ValueError('A user with this mobile number already exists.')
                employee.mobile_number = normalized.number
                employee.country = normalized.country_code
                employee.phone_country_code = normalized.dial_code
                update_fields.extend(['mobile_number', 'country', 'phone_country_code'])
            elif 'country' in data:
                employee.country = new_country
                employee.phone_country_code = ''
                update_fields.extend(['country', 'phone_country_code'])

        if update_fields:
            employee.save(update_fields=list(dict.fromkeys(update_fields)))

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
        self._ensure_company_operational(company=company)
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
        self._ensure_company_operational(company=company)
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
        """
        List roles assignable within the current company.

        Includes:
        - Global roles (company IS NULL)
        - Roles belonging to the current company

        Never returns another company's roles.
        """
        self._ensure_company_operational(company=company)
        return (
        Role.objects
        .filter(
            Q(company=company)
            | (
                Q(company__isnull=True)
                & ~Q(name__iexact='Super Admin')
            )
        )
        .order_by('name')
        )

    def _validate_role(self, *, company, role_id):
        """Return a role only if it is global or belongs to the company."""
        role = get_object_or_404(Role, pk=role_id)
        if role.company_id is not None and role.company_id != company.id:
            raise ValueError('Role does not belong to your company.')
        return role

    @transaction.atomic
    def assign_role(self, *, company, employee_id, role_id, acting_user):
        self._ensure_company_operational(company=company)
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
        self._ensure_company_operational(company=company)
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
        self._ensure_company_operational(company=company)
        settings, _ = CompanySettings.objects.get_or_create(company=company)
        return {'company': company, 'settings': settings}

    @transaction.atomic
    def update_company_settings(self, *, company, acting_user, data):
        self._ensure_company_operational(company=company)
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
        contact_email = data.get('contact_email')
        contact_phone = data.get('contact_phone')
        country = data.get('country')
        
        if contact_email is not None:
            company.contact_email = contact_email
            company_changed.append('contact_email')
        
        if contact_phone is not None or country is not None:
            final_country = (
                country.strip().upper()
                if country
                else (company.country or '').strip().upper()
            )
        
            final_phone = (
                contact_phone
                if contact_phone is not None
                else company.contact_phone
            )
        
            if final_phone:
                try:
                    normalized = normalize_phone(
                        phone=final_phone,
                        country=final_country,
                    )
                except ValueError as exc:
                    raise ValueError(str(exc)) from exc
        
                company.contact_phone = normalized.number
                company.country = normalized.country_code
                company.contact_phone_country_code = normalized.dial_code
        
                company_changed.extend([
                    'contact_phone',
                    'country',
                    'contact_phone_country_code',
                ])
        
            elif country is not None:
                company.country = final_country
                company.contact_phone_country_code = ''
        
                company_changed.extend([
                    'country',
                    'contact_phone_country_code',
                ])
        
        
        
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
        company = getattr(user,'company', None)
        if company:
            self._ensure_company_operational(company=company)
        qs = Notification.objects.filter(user=user).select_related('company')
        if is_read is not None:
            qs = qs.filter(is_read=is_read)
        qs = qs.order_by('-created_at')
        count = qs.count()
        return qs[offset:offset + limit], count

    def unread_notifications_count(self, *, user):
        company = getattr(user, 'company', None)

        if company:
            self._ensure_company_operational(company=company)

        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).count()

    def mark_notification_read(self, *, notification_id, user):
        company = getattr(user, 'company', None)

        if company:
            self._ensure_company_operational(company=company)
        notification = get_object_or_404(Notification, pk=notification_id, user=user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        return notification

    def mark_all_notifications_read(self, *, user):
        company = getattr(user, 'company', None)

        if company:
            self._ensure_company_operational(company=company)
            
        updated = Notification.objects.filter(user=user, is_read=False).update(
            is_read=True, read_at=timezone.now(),
        )
        return {'updated_count': updated}

    # ── Client me context ─────────────────────────────────────

    def get_client_context(self, *, user):
        company = getattr(user, 'company', None)
        if company:
            self._ensure_company_operational(company=company)
        modules = []
        permissions = []
        if company:
            modules = list(
                CompanyModule.objects.filter(company=company, enabled=True)
                .select_related('module')
                .values('module_id', 'module__code', 'module__name')
            )
        # role_names = list(user.user_roles.values_list('role__name', flat=True))
        role_names= [
            role_name.lower().replace(' ','_')
            for role_name in user.user_roles.values_list('role__name',flat=True)
        ]
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

from django.utils import timezone

from superadmin.models import CompanyPlan, CompanyPlanStatus
from tenancy.models import Company


class CompanyLifecycleService:
    """
    Central source of truth for determining whether a company
    is allowed to perform client-side operations.
    """

    def get_current_plan(self, *, company):
        return (
            CompanyPlan.objects
            .filter(company=company)
            .select_related('plan')
            .order_by('-start_date', '-created_at')
            .first()
        )

    def get_effective_status(self, *, company):
        """
        Return the company's effective operational status.

        A company is operational only when:
        - it is not soft deleted,
        - it is not manually suspended,
        - and its current subscription is within its valid period.
        """
        if company.is_deleted:
            return Company.Status.SUSPENDED

        if company.suspension_reason == CompanySuspensionReason.MANUAL:
            return Company.Status.SUSPENDED

        # if company.status == Company.Status.SUSPENDED:
        #     return Company.Status.SUSPENDED
        # A suspended status can be either:
        # 1. a temporary state caused by deleted/invalid subscription, or
        # 2. a manually suspended company.
        #
        # Effective state is therefore determined from deletion + subscription
        # below instead of treating the stored SUSPENDED value as permanent.

        today = timezone.now().date()

        plan = self.get_current_plan(company=company)

        if not plan:
            return Company.Status.SUSPENDED

        if plan.status in {
            CompanyPlanStatus.CANCELLED,
            CompanyPlanStatus.EXPIRED,
            CompanyPlanStatus.REPLACED,
        }:
            return Company.Status.SUSPENDED

        if plan.start_date and plan.start_date > today:
            return Company.Status.SUSPENDED

        if plan.end_date and plan.end_date < today:
            return Company.Status.SUSPENDED

        if plan.status == CompanyPlanStatus.TRIAL:
            return Company.Status.TRIAL

        if plan.status == CompanyPlanStatus.ACTIVE:
            return Company.Status.ACTIVE

        return Company.Status.SUSPENDED

    def is_operational(self, *, company):
        return self.get_effective_status(company=company) in {
            Company.Status.ACTIVE,
            Company.Status.TRIAL,
        }

    def ensure_operational(self, *, company):
        """
        Raise a ValueError when the company is not allowed
        to perform client operations.
        """
        effective_status = self.get_effective_status(company=company)

        if effective_status == Company.Status.SUSPENDED:
            raise ValueError(
                'Your company account is currently suspended.'
            )

        return company


company_lifecycle_service = CompanyLifecycleService()