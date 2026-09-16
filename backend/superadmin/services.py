from __future__ import annotations

from datetime import timedelta
import re
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from common.contact_validation import normalize_phone
from django.utils.crypto import get_random_string
from accounts.models import User, Gender
from invitations.models import Invitation, InvitationStatus
from invitations.services import invitation_service
from rbac.models import Role
from superadmin.models import (
    Plan,
    PlanStatus,
    Transaction,
)
from tenancy.models import Company, CompanyDeletionHistory, CompanySuspensionReason
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
                'total_amount',
                'discount_amount',
                'payment_status',
                'transaction_status',
                'payment_method',
                'invoice_number',
                'created_at',
            )
        )
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
    def assign_user_role(self, *, user_id, role_id):
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

        changed = user.role_id != role.id

        if changed:
            user.role = role
            user.save(update_fields=["role", "updated_at"])

        return {
            "created": changed,
            "user": user,
        }
    
    def remove_user_role(self, *, user_id, role_id):
        user = get_object_or_404(User, pk=user_id)
    
        self.ensure_employee_company_operational(
            employee=user
        )
    
        deleted = user.role_id == role_id
    
        if deleted:
            user.role = None
            user.save(update_fields=["role", "updated_at"])
    
        return {
            "deleted": deleted,
        }

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
                role=selected_role,
                is_active=False,
                is_email_verified=False,
            )
            user.set_unusable_password()
            user.save()
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