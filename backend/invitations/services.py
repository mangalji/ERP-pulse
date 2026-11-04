import logging
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from audit.models import AuditModule, AuditAction
from audit.services import audit_service
from common.email_service import send_email
from accounts.models import OTP
from accounts.services import OTPService
from common.contact_validation import normalize_phone
from common.email_verification import ensure_email_deliverable
from tenancy.services import company_lifecycle_service
from tenancy.models import Company, CompanyDepartment
from rbac.models import Role
from urllib.parse import urlsplit
from .models import Invitation, InvitationStatus

User = get_user_model()
logger = logging.getLogger(__name__)


class InvitationService:
    """Business logic for invitation handling."""

    def __init__(self):
        self.otp_service=OTPService()

    @staticmethod
    def _get_invitation_or_error(invitation_id):
        try:
            return Invitation.objects.select_related('company', 'role').get(
                pk=invitation_id
            )
        except Invitation.DoesNotExist as exc:
            raise ValueError('Invitation not found.') from exc

    @staticmethod
    def _audit_user(request=None):
        user = getattr(request, 'user', None) if request else None
        if user is not None and getattr(user, 'is_authenticated', False):
            return user
        return None

    @staticmethod
    def _is_configured_department(*, company, department: str) -> bool:
        """Validate against the company's editable department catalogue.

        Older companies have no catalogue rows until they first manage
        departments. Seed the documented defaults once for those companies,
        but do not resurrect defaults after an admin has deliberately removed
        every department.
        """
        departments = CompanyDepartment.objects.filter(company=company)
        if not departments.exists():
            CompanyDepartment.objects.bulk_create(
                [
                    CompanyDepartment(company=company, name=name)
                    for name in ('HR', 'NetSuite', 'IT Support', 'Development')
                ],
                ignore_conflicts=True,
            )
            departments = CompanyDepartment.objects.filter(company=company)
        return departments.filter(
            name__iexact=department,
            is_active=True,
            is_deleted=False,
        ).exists()

    def create_company_user_and_invite(
        self,
        *,
        company,
        acting_user,
        email,
        first_name,
        last_name,
        country,
        role_id,
        gender=None,
        mobile_number=None,
        designation='',
        department='',
        request=None,
    ):
        """
        Create one pending company user and its invitation.

        Both platform administrators and company administrators use this
        method.  The caller decides *which* company is in scope; this method
        owns the identical user, role, invitation, email and audit flow.
        """
        company_lifecycle_service.ensure_operational(company=company)

        normalized_email = (email or '').lower().strip()
        if not normalized_email:
            raise ValueError('Email is required.')
        if len(normalized_email) > 40:
            raise ValueError('Email must not exceed 40 characters.')
        ensure_email_deliverable(normalized_email)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise ValueError('A user with this email already exists.')

        first_name = (first_name or '').strip()
        last_name = (last_name or '').strip()
        if not first_name:
            raise ValueError('First name is required.')
        if len(first_name) < 2:
            raise ValueError('First name must contain at least 2 characters.')
        if len(first_name) > 40:
            raise ValueError('First name must not exceed 40 characters.')
        if last_name and len(last_name) < 2:
            raise ValueError('Last name must contain at least 2 characters.')
        if len(last_name) > 40:
            raise ValueError('Last name must not exceed 40 characters.')

        name_pattern = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ']+$")
        if not name_pattern.fullmatch(first_name):
            raise ValueError(
                'First name may contain letters and apostrophes only.'
            )
        if last_name and not name_pattern.fullmatch(last_name):
            raise ValueError(
                'Last name may contain letters and apostrophes only.'
            )
        if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", first_name):
            raise ValueError('First name must contain at least one letter.')
        if last_name and not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", last_name):
            raise ValueError('Last name must contain at least one letter.')

        country = (country or '').strip().upper()
        if not country:
            raise ValueError('Country is required.')
        designation = (designation or '').strip()
        department = (department or '').strip()
        if not designation:
            raise ValueError('Designation is required.')
        if not department:
            raise ValueError('Department is required.')
        if not self._is_configured_department(
            company=company,
            department=department,
        ):
            raise ValueError('Select a department configured for this company.')

        if not role_id:
            raise ValueError('Role is required.')
        role = Role.objects.filter(pk=role_id).first()
        if role is None:
            raise ValueError('Role not found.')
        if role.company_id is not None and role.company_id != company.id:
            raise ValueError('Role does not belong to this company.')
        if role.company_id is None and role.name.strip().lower() == 'super admin':
            raise ValueError('The Super Admin role cannot be assigned to a company user.')

        normalized_phone = None
        phone_country_code = ''
        if not mobile_number:
            raise ValueError('Mobile number is required.')
        try:
            normalized = normalize_phone(phone=mobile_number, country=country)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        normalized_phone = normalized.number
        country = normalized.country_code
        phone_country_code = normalized.dial_code
        if User.objects.filter(mobile_number=normalized_phone).exists():
            raise ValueError('A user with this mobile number already exists.')

        with transaction.atomic():
            user = User(
                email=normalized_email,
                first_name=first_name,
                last_name=last_name,
                mobile_number=normalized_phone,
                country=country,
                phone_country_code=phone_country_code,
                designation=designation,
                department=department,
                company=company,
                role=role,
                is_active=False,
                is_email_verified=False,
            )
            user.set_unusable_password()
            user.save()

            invitation = self.create_invitation(
                email=user.email,
                company_id=company.id,
                role_id=role.id,
                created_by=acting_user,
                request=request,
                send_email=False,
            )

            audit_service.log(
                module=AuditModule.EMPLOYEE,
                action=AuditAction.CREATE,
                entity='User',
                entity_id=str(user.id),
                company=company,
                user=acting_user,
                new_value={
                    'event': 'created',
                    'employee_name': user.get_full_name(),
                    'email': user.email,
                    'role_id': str(role.id),
                },
            )

        _, invitation_email_sent = self.send_invitation(
            invitation_id=invitation.id,
            request=request,
            return_delivery_status=True,
        )
        return {
            'user': user,
            'invitation': invitation,
            'invitation_email_sent': invitation_email_sent,
        }

    def create_invitation(self, *, email, company_id, role_id=None, created_by=None, request=None, send_email=True):
        """
        Create a new invitation
        When send_email=False, only the invitation record is created.
        The caller can send the email separately after its database
        transaction has successfully completed.
        """
        company = Company.objects.get(pk=company_id)
        company_lifecycle_service.ensure_operational(
            company=company
        )
        role = Role.objects.filter(pk=role_id).first() if role_id else None

        # Check for existing pending invitation
        existing = Invitation.objects.filter(
            email__iexact=email,
            company=company,
            status=InvitationStatus.PENDING,
        ).filter(expires_at__gt=timezone.now()).first()
        if existing:
            raise ValueError('An active invitation already exists for this email and company.')

        expires_at = timezone.now() + timedelta(hours=24)

        with transaction.atomic():
            invitation = Invitation.objects.create(
                email=email.lower().strip(),
                company=company,
                role=role,
                expires_at=expires_at,
                created_by=created_by,
            )

            audit_service.log(
                module=AuditModule.INVITATION,
                action=AuditAction.CREATE,
                entity='Invitation',
                entity_id=str(invitation.id),
                company=company,
                user=self._audit_user(request),
                old_value=None,
                new_value={
                    'email': invitation.email,
                    'company': company.name,
                    'role': role.name if role else None,
                    'expires_at': invitation.expires_at.isoformat(),
                },
            )
        # Email is intentionally sent outside the database transaction, so a
        # slow/failed SMTP call never holds the DB transaction open, and a
        # transaction rollback never leaves an email sent for a row that no
        # longer exists. This is the ONLY send in this method — do not also
        # send inside the transaction.atomic() block above; that previously
        # caused every invitation created with send_email=True to be
        # emailed twice.
        if send_email:
            self._send_invitation_email(invitation)
        return invitation

    def resend_user_invitation(self, *, user, acting_user, request=None):
        """Resend or repair onboarding for one company user.

        Company-admin and superadmin employee flows use this single path so
        pending, expired, and legacy invitation records behave identically.
        """
        company = getattr(user, 'company', None)
        if company is None:
            raise ValueError('Only company users can receive invitations.')

        company_lifecycle_service.ensure_operational(company=company)

        # A pending account cannot be active before it has a password. Repair
        # records created by older flows before deciding whether to resend.
        if user.is_active and not user.has_usable_password():
            user.is_active = False
            user.save(update_fields=['is_active'])

        invitation = (
            Invitation.objects.filter(
                email__iexact=user.email,
                company=company,
                status__in=[InvitationStatus.PENDING, InvitationStatus.EXPIRED],
            )
            .order_by('-created_at')
            .first()
        )
        if invitation is not None:
            invitation = self.resend_invitation(
                invitation_id=invitation.id,
                request=request,
            )
            return {'user': user, 'invitation': invitation}

        # Do not invite a user who has already finished setup, including one
        # who was later deactivated by an administrator.
        if user.is_active or user.has_usable_password():
            raise ValueError('This employee already completed account setup.')
        if not user.role_id:
            raise ValueError('This employee has no role configured for an invitation.')

        invitation = self.create_invitation(
            email=user.email,
            company_id=company.id,
            role_id=user.role_id,
            created_by=acting_user,
            request=request,
        )
        return {'user': user, 'invitation': invitation}

    def send_invitation(self, *, invitation_id, request=None, return_delivery_status=False):
        """
        Resend an existing invitation email.
        """
        invitation = self._get_invitation_or_error(invitation_id)
        company_lifecycle_service.ensure_operational(company=invitation.company)

        if invitation.status != InvitationStatus.PENDING:
            raise ValueError('Only pending invitations can be sent.')

        if invitation.is_expired():
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=['status'])
            raise ValueError('Invitation has expired.')

        sent = self._send_invitation_email(invitation)

        audit_service.log(
            module=AuditModule.INVITATION,
            action=AuditAction.SEND,
            entity='Invitation',
            entity_id=str(invitation.id),
            company=invitation.company,
            user=self._audit_user(request),
            old_value={'sent': False},
            new_value={'sent': sent},
        )
        if return_delivery_status:
            return invitation, sent
        
        return invitation

    def resend_invitation(self, *, invitation_id, request=None):
        """
        Resend an invitation. 
    
        A still-valid pending invitation keeps its existing token and gets a
        fresh 24-hour expiry. An expired invitation receives a new Invitation
        row and token, so the old expired link can never become valid again.
        """

        invitation = self._get_invitation_or_error(invitation_id)
        company_lifecycle_service.ensure_operational(company=invitation.company)

        if invitation.status not in {
            InvitationStatus.PENDING, InvitationStatus.EXPIRED
        }:
            raise ValueError('Only pending invitations can be resent.')

        if invitation.status == InvitationStatus.PENDING and not invitation.is_expired():
            invitation.expires_at = timezone.now() + timedelta(hours=24)
            invitation.save(update_fields=["expires_at"])

            self._send_invitation_email(invitation)

            audit_service.log(
                module=AuditModule.INVITATION,
                action=AuditAction.SEND,
                entity='Invitation',
                entity_id=str(invitation.id),
                company=invitation.company,
                user=self._audit_user(request),
                old_value={'action': 'resent'},
                new_value={'expires_at': invitation.expires_at.isoformat()},
            )

            return invitation

        if invitation.status == InvitationStatus.PENDING:
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=['status'])

        return self.create_invitation(
            email=invitation.email,
            company_id=invitation.company_id,
            role_id=invitation.role_id,
            created_by=self._audit_user(request) or invitation.created_by,
            request=request,
            send_email=True,
        )

    def validate_token(self, token):
        """
        Validate an invitation token and return the invitation if valid.
        Raises ValueError if invalid or expired.
        """
        try:
            invitation = Invitation.objects.select_related('company', 'role').get(token=token)
        except Invitation.DoesNotExist:
            raise ValueError('Invalid invitation token.')

        if invitation.status != InvitationStatus.PENDING:
            raise ValueError('This invitation has already been used or cancelled.')

        if invitation.is_expired():
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=['status'])
            raise ValueError('This invitation has expired.')

        company_lifecycle_service.ensure_operational(company=invitation.company)

        return invitation

    @staticmethod
    def _validate_original_mobile_number(*, user, mobile_number):
        """Match an invitee's national number to the pre-created user record.

        The country and dialling code are never accepted from the invitation
        page. Keeping this comparison against the persisted normalized number
        prevents an invitee from substituting a different phone number.
        """
        entered = ''.join(character for character in str(mobile_number or '') if character.isdigit())
        if not entered:
            raise ValueError('Mobile number is required.')
        if not user.country or not user.mobile_number:
            raise ValueError(
                'A mobile number or country is not configured for this user. '
                'Please contact your administrator.'
            )

        try:
            normalized = normalize_phone(phone=entered, country=user.country)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        if normalized.number != user.mobile_number:
            raise ValueError(
                'The mobile number does not match the number registered by your administrator. '
                'Enter your original mobile number without the country code.'
            )

    def request_invitation_otp(self, token, password, mobile_number):
        """
        Validate an invitation and send an OTP before activating
        the pre-created user account.
        """
        invitation = self.validate_token(token)
        company_lifecycle_service.ensure_operational(
            company=invitation.company
        )
        try:
            user = User.objects.get(
                email__iexact=invitation.email,
            )
        except User.DoesNotExist:
            raise ValueError("The user account associated with this invitation was not found.")
        # The user must have been pre-created by Super Admin.
        if user.company_id != invitation.company_id:
            raise ValueError(
                "The invited user does not belong to the invited company."
            )
        if user.is_active:
            raise ValueError("This user account is already active.")

        if user.has_usable_password():
            raise ValueError("This user already has a password. Please use the normal login or password reset flow.")

        self._validate_original_mobile_number(
            user=user,
            mobile_number=mobile_number,
        )
        
        # Send a separate OTP for invitation/account activation.
        self.otp_service.generate_and_send_otp(user=user,purpose=OTP.Purpose.INVITATION)
        return user

    @staticmethod
    def get_masked_invitation_mobile_number(*, invitation) -> str:
        """Return only the final four national digits for the public invite UI."""
        user = User.objects.filter(
            email__iexact=invitation.email,
            company_id=invitation.company_id,
        ).only('mobile_number', 'phone_country_code').first()
        if user is None or not user.mobile_number:
            return ''

        stored_digits = ''.join(
            character for character in str(user.mobile_number) if character.isdigit()
        )
        dial_code_digits = ''.join(
            character for character in str(user.phone_country_code or '')
            if character.isdigit()
        )
        national_digits = (
            stored_digits[len(dial_code_digits):]
            if dial_code_digits and stored_digits.startswith(dial_code_digits)
            else stored_digits
        )
        if len(national_digits) <= 4:
            return '*' * len(national_digits)
        return f"{'*' * (len(national_digits) - 4)}{national_digits[-4:]}"

    def resend_invitation_otp(self, token):
        """
        Validate the invitation and send a new invitation-specific OTP.
        The shared OTPService enforces the resend cooldown.
        """
        invitation = self.validate_token(token)
        company_lifecycle_service.ensure_operational(
            company=invitation.company
        )
    
        try:
            user = User.objects.get(
                email__iexact=invitation.email,
            )
        except User.DoesNotExist:
            raise ValueError(
                "The user account associated with this invitation was not found."
            )
    
        if user.company_id != invitation.company_id:
            raise ValueError(
                "The invited user does not belong to the invited company."
            )
    
        if user.is_active:
            raise ValueError(
                "This user account is already active."
            )
    
        if user.has_usable_password():
            raise ValueError(
                "This user already has a password. "
                "Please use the normal login or password reset flow."
            )
    
        self.otp_service.generate_and_send_otp(
            user=user,
            purpose=OTP.Purpose.INVITATION,
        )
    
        return user

    def accept_invitation(self, token, password, otp, mobile_number=None):
        """
        Verify the invitation OTP and complete account activation.

        Administrator-controlled fields (first name, last name, country,
        mobile number, company and role) are already stored on the
        pre-created User. The invitee must confirm, not update, their mobile
        number before activation.
        """
        invitation = self.validate_token(token)
        company_lifecycle_service.ensure_operational(
            company=invitation.company
        )
        try:
            user = User.objects.get(
                email__iexact=invitation.email
            )
        except User.DoesNotExist:
            raise ValueError(
                "The user account associated with this invitation was not found."
            )

        if user.company_id != invitation.company_id:
            raise ValueError(
                "The invited user does not belong to the invited company."
            )

        if user.is_active:
            raise ValueError(
                "This user account is already active."
            )

        self._validate_original_mobile_number(
            user=user,
            mobile_number=mobile_number,
        )

        # Verify the invitation-specific OTP.
        self.otp_service.verify_otp(
            user=user,
            purpose=OTP.Purpose.INVITATION,
            submitted_code=otp,
        )

        with transaction.atomic():
            # Password is saved ONLY after successful OTP verification.
            user.set_password(password)
            user.is_active = True
            user.is_email_verified = True

            update_fields = [
                "password",
                "is_active",
                "is_email_verified",
            ]

            user.save(update_fields=update_fields)

            # The role, company, first name, last name, country and gender
            # were already set by the administrator when the user was created.
            # The invitee cannot change those values during acceptance.

            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = timezone.now()
            invitation.save(
                update_fields=[
                    "status",
                    "accepted_at",
                ]
            )

        audit_service.log(
            module=AuditModule.INVITATION,
            action=AuditAction.ACCEPT,
            entity="Invitation",
            entity_id=str(invitation.id),
            company=invitation.company,
            user=user,
            old_value={
                "status": InvitationStatus.PENDING,
                "is_active": False,
                "is_email_verified": False,
            },
            new_value={
                "status": InvitationStatus.ACCEPTED,
                "user_id": str(user.id),
                "is_active": True,
                "is_email_verified": True,
                "mobile_number_confirmed": True,
            },
        )

        return user


    def expire_old_tokens(self):
        """
        Mark expired pending invitations as EXPIRED.
        """
        now = timezone.now()
        expired = Invitation.objects.filter(
            status=InvitationStatus.PENDING,
            expires_at__lt=now,
        )
        count = expired.update(status=InvitationStatus.EXPIRED)
        return count

    def get_invitation(self, *, request_id):
        try:
            return Invitation.objects.select_related(
                'company', 'role', 'created_by'
            ).get(pk=request_id)
        except Invitation.DoesNotExist as exc:
            raise ValueError('Invitation not found.') from exc

    def _send_invitation_email(self, invitation):
        """
        Send invitation email using the existing email service.
        """
        frontend_url = settings.FRONTEND_URL.rstrip('/')
        invitation_link = f"{frontend_url}/#/invitation/{invitation.token}"
        frontend_host = (urlsplit(frontend_url).hostname or '').lower()
        is_local_frontend = frontend_host in {
            'localhost',
            '127.0.0.1',
            '::1',
        }
        if settings.DEBUG and is_local_frontend:
            logger.info(
                "Invitation Link: %s, email: %s, company:%s, expires at: %s",
                invitation_link,invitation.email,invitation.company.name,invitation.expires_at,
            )

        subject = f"You've been invited to join {invitation.company.name}"
        message = (
            f"Hello,\n\n"
            f"You have been invited to join {invitation.company.name} on AGSuite.\n\n"
            f"Click the link below to accept your invitation and set up your account:\n"
            f"{invitation_link}\n\n"
            f"This invitation will expire on {invitation.expires_at.strftime('%d %B %Y at %I:%M %p')}.\n\n"
            f"If you did not expect this invitation, please ignore this email.\n\n"
            f"Best regards,\n"
            f"AGSuite Team"
        )

        try:
            send_email(
                subject=subject,
                message=message,
                recipient_list=[invitation.email],
                fail_silently=False,
            )
            return True
        except Exception:
            logger.exception(
                "Failed to send invitation email to %s", invitation.email
            )
            return False


invitation_service = InvitationService()
