import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from audit.models import AuditModule, AuditAction
from audit.services import audit_service
from common.services.email_service import send_email
from accounts.models import OTP
from accounts.services import OTPService

from tenancy.models import Company
from rbac.models import Role

from .models import Invitation, InvitationStatus

User = get_user_model()
logger = logging.getLogger(__name__)


class InvitationService:
    """Business logic for invitation handling."""

    def __init__(self):
        self.otp_service=OTPService()

    @staticmethod
    def _audit_user(request=None):
        user = getattr(request, 'user', None) if request else None
        if user is not None and getattr(user, 'is_authenticated', False):
            return user
        return None

    def create_invitation(self, *, email, company_id, role_id=None, created_by=None, expires_in_days=7, request=None, send_email=True):
        """
        Create a new invitation
        When send_email=False, only the invitation record is created.
        The caller can send the email separately after its database
        transaction has successfully completed.
        """
        company = Company.objects.get(pk=company_id)
        role = Role.objects.filter(pk=role_id).first() if role_id else None

        # Check for existing pending invitation
        existing = Invitation.objects.filter(
            email__iexact=email,
            company=company,
            status=InvitationStatus.PENDING,
        ).filter(expires_at__gt=timezone.now()).first()
        if existing:
            raise ValueError('An active invitation already exists for this email and company.')

        expires_at = timezone.now() + timedelta(days=expires_in_days)

        with transaction.atomic():
            invitation = Invitation.objects.create(
                email=email.lower().strip(),
                company=company,
                role=role,
                expires_at=expires_at,
                created_by=created_by,
            )
            if send_email:
                self._send_invitation_email(invitation)

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
        # Email is intentionally sent outside the database transaction.
        if send_email:
            self._send_invitation_email(invitation)
        return invitation

    def send_invitation(self, *, invitation_id, request=None, return_delivery_status=False):
        """
        Resend an existing invitation email.
        """
        invitation = Invitation.objects.select_related('company', 'role').get(pk=invitation_id)

        if invitation.status != InvitationStatus.PENDING:
            raise ValueError('Only pending invitations can be sent.')

        if invitation.is_expired():
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=['status'])
            raise ValueError('Invitation has expired.')

        sent = self._send_invitation_email(invitation)
        # self._send_invitation_email(invitation)

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
        Resend an invitation and extend its expiry.
        """
        invitation = Invitation.objects.select_related('company', 'role').get(pk=invitation_id)

        if invitation.status != InvitationStatus.PENDING:
            raise ValueError('Only pending invitations can be resent.')

        invitation.expires_at = timezone.now() + timedelta(days=7)
        invitation.save(update_fields=['expires_at'])

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

        return invitation

    # def accept_invitation(self, token, password, first_name, last_name):
    #     """
    #     Accept an invitation by creating a user account.
    #     """
    #     invitation = self.validate_token(token)

    #     with transaction.atomic():
    #         # Create or update user
    #         user, created = User.objects.get_or_create(
    #             email=invitation.email.lower().strip(),
    #             defaults={
    #                 'first_name': first_name,
    #                 'last_name': last_name,
    #                 'company': invitation.company,
    #                 'is_active': True,
    #                 'is_email_verified': True,
    #             },
    #         )

    #         if not created:
    #             user.first_name = first_name
    #             user.last_name = last_name
    #             user.company = invitation.company
    #             user.is_active = True
    #             user.is_email_verified = True

    #         user.set_password(password)
    #         user.save()

    #         # Assign role if provided
    #         if invitation.role:
    #             from rbac.models import UserRole
    #             UserRole.objects.get_or_create(user=user, role=invitation.role)

    #         invitation.status = InvitationStatus.ACCEPTED
    #         invitation.accepted_at = timezone.now()
    #         invitation.save(update_fields=['status', 'accepted_at'])

    #         audit_service.log(
    #             module=AuditModule.INVITATION,
    #             action=AuditAction.ACCEPT,
    #             entity='Invitation',
    #             entity_id=str(invitation.id),
    #             company=invitation.company,
    #             user=user,
    #             old_value={'status': InvitationStatus.PENDING},
    #             new_value={'status': InvitationStatus.ACCEPTED, 'user_id': str(user.id)},
    #         )

    #     return user

    def request_invitation_otp(self,token,password):
        """
        Validate an invitation and send an OTP before activating
        the pre-created user account.
        """
        invitation = self.validate_token(token)
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
        
        # Send a separate OTP for invitation/account activation.
        self.otp_service.generate_and_send_otp(user=user,purpose=OTP.Purpose.INVITATION)
        return user

    def accept_invitation(self,token,password,otp):
        """
        Verify the invitation OTP and complete account activation.
        """
        invitation = self.validate_token(token)

        try:
            user = User.objects.get(
                email__iexact=invitation.email
            )
        except User.DoesNotExist:
            raise ValueError(
            "The user account associated with this invitation was not found."
        )
        if user.company_id != invitation.company_id:
            raise ValueError("The invited user does not belong to the invited company.")

        if user.is_active:
            raise ValueError(
                "This user account is already active."
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
            user.save(
                update_fields=[
                    "password",
                    "is_active",
                    "is_email_verified",
                ]
            )

            # The role was already assigned when the Super Admin
            # created the user. We do not create a duplicate role here.
            
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
        return Invitation.objects.select_related('company', 'role', 'created_by').get(pk=request_id)

    def _send_invitation_email(self, invitation):
        """
        Send invitation email using the existing email service.
        """
        frontend_url = settings.FRONTEND_URL.rstrip('/')
        invitation_link = f"{frontend_url}/invitation/{invitation.token}"
        print("\n" + "=" * 70)
        print("              AGSUITE INVITATION")
        print("=" * 70)
        print(f"Email:            {invitation.email}")
        print(f"Company:          {invitation.company.name}")
        print(f"Invitation Link:  {invitation_link}")
        print(f"Expires At:       {invitation.expires_at}")
        print("=" * 70 + "\n")

        subject = f"You've been invited to join {invitation.company.name}"
        message = (
            f"Hello,\n\n"
            f"You have been invited to join {invitation.company.name} on AGSuite.\n\n"
            f"Click the link below to accept your invitation and set up your account:\n"
            f"{invitation_link}\n\n"
            f"This invitation will expire on {invitation.expires_at.strftime('%B %d, %Y at %I:%M %p')}.\n\n"
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
