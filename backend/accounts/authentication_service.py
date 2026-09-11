import logging
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.db import transaction

from accounts.exceptions import (
    AccountNotVerifiedException,
    InvalidCredentialsException,
    MaxOTPAttemptsExceededException,
    OTPExpiredException,
    OTPMismatchException,
    ResendCooldownException,
    UserAlreadyExistsException,
)
from accounts.models import OTP, User
from accounts.repositories import UserRepository
from accounts.services import OTPService
from common.common_utils import (
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_LENGTH,
    OTP_EXPIRY_MINUTES,
    MAX_OTP_ATTEMPTS,
)
from common.email_service import send_email
from common.common_utils import calculate_expiry, is_expired
from common.common_utils import hash_value, verify_value
from common.common_utils import generate_otp_code
from common.common_utils import generate_signed_token, verify_signed_token
from tenancy.services import company_lifecycle_service

logger = logging.getLogger(__name__)

# Namespaces the signed token so it can never be confused with a token
# generated for a different purpose if common.utils.signed_token is ever
# reused elsewhere (e.g. a future password-reset flow).


class AuthenticationService:
    """
    Business logic for registration and the two-step, OTP-gated login flow
    (AUTHENTICATION_DESIGN.md, Sections 5-6).

    Registration is a three-step flow: Register (email+password) -> Verify
    Registration OTP -> Complete Profile (first/last name, mobile). No
    User row is created until Complete Profile succeeds — the email,
    hashed password, and OTP state in between live in a cache-backed
    store (accounts/registration_cache.py), never a database model,
    per product decision. verify_registration_otp() returns a short-lived
    signed token (common/utils/signed_token.py) that Complete Profile must
    present, proving the email really did pass OTP verification.

    Login is unchanged from prior sessions: still OTP-gated in two steps,
    still issues no JWT itself (that remains the View layer's job).
    """

    def __init__(self, user_repository: UserRepository | None = None, otp_service=None):
        self.user_repository = user_repository or UserRepository()
        self.otp_service = otp_service or OTPService()

    def _ensure_user_company_operational(self, *, user) -> None:
        """
        Client-company users can authenticate only when their company
        is operational.

        Platform-level users (company=None), such as AGSuite/Super Admin
        users, are not restricted by client-company lifecycle state.
        """
        company = getattr(user, 'company', None)

        if company is None:
            return

        try:
            company_lifecycle_service.ensure_operational(company=company)
        except ValueError as exc:
            # Keep the authentication response generic so company status
            # is not disclosed to an unauthenticated caller.
            raise InvalidCredentialsException(
                'Invalid email or password.'
            ) from exc

    # -----------------------------------------------------------------
    # Password Reset
    # -----------------------------------------------------------------

    def reset_password(self, *, email: str, otp_code: str, password: str) -> dict:
        """
        Verify PASSWORD_RESET OTP and update the user's password.
        Returns email on success.
        """
        user = self.user_repository.get_by_email(email)
        if user is None:
            # Don't reveal whether email exists
            logger.info('Password reset attempted for unknown email=%s.', email)
            return {'email': email}

        self._ensure_user_company_operational(user=user)
        self.otp_service.verify_otp(
            user=user, purpose=OTP.Purpose.PASSWORD_RESET, submitted_code=otp_code
        )

        user.set_password(password)
        user.save(update_fields=['password'])

        logger.info('Password reset completed for user %s.', user.id)
        return {'email': email}

    # -----------------------------------------------------------------
    # Profile Update
    # -----------------------------------------------------------------

    def verify_profile_update_otp(self, *, user, otp_code: str, first_name: str | None = None, last_name: str | None = None, mobile_number: str | None = None, profile_pic=None) -> User:
        """
        Verify PROFILE_UPDATE OTP and update user profile fields.
        Only updates fields that were provided (not None).
        """
        self.otp_service.verify_otp(
            user=user, purpose=OTP.Purpose.PROFILE_UPDATE, submitted_code=otp_code
        )

        update_fields = []
        if first_name is not None:
            user.first_name = first_name
            update_fields.append('first_name')
        if last_name is not None:
            user.last_name = last_name
            update_fields.append('last_name')
        if mobile_number is not None:
            # Check uniqueness if a new mobile number is provided

            if mobile_number != user.mobile_number and mobile_number:
                if self.user_repository.mobile_number_exists(mobile_number):
                    raise UserAlreadyExistsException('This mobile number is already linked to another account.')
            user.mobile_number = mobile_number
            update_fields.append('mobile_number')
        if profile_pic is not None:
            user.profile_pic = profile_pic
            update_fields.append('profile_pic')

        if update_fields:
            user.save(update_fields=update_fields)

        logger.info('Profile updated for user %s (fields: %s).', user.id, update_fields)
        return user


    def login(self, *, email: str, password: str) -> User:
        """
        Step 1 of login: verify credentials and, if valid and the account
        is active/verified, send a LOGIN OTP. Issues no token.
        """
        import traceback
        user = self.user_repository.get_by_email(email)
        if user is None:
            raise InvalidCredentialsException('Invalid email or password.')
        pw_ok = user.check_password(password)
        if not pw_ok:
            raise InvalidCredentialsException('Invalid email or password.')

        if not user.is_active or not user.is_email_verified:
            raise AccountNotVerifiedException(
                'Please activate your account first. Check your email for the '
                'invitation link, or contact your administrator if your access '
                'has been disabled.'
            )
        self._ensure_user_company_operational(user=user)

        try:
            self.otp_service.generate_and_send_otp(user=user, purpose=OTP.Purpose.LOGIN)
        except Exception as e:
            raise
        logger.info('Login OTP sent for user %s.', user.id)
        return user

    def verify_login_otp(self, *, email: str, otp_code: str) -> User:
        """
        Step 2 of login: verify the LOGIN OTP and return the authenticated
        User. Issues no token — that is a separate, later concern.
        """
        email = email.lower().strip()
        user = self.user_repository.get_by_email(email)
        if user is None:
            raise InvalidCredentialsException('Invalid email or verification code.')

        self._ensure_user_company_operational(user=user)

        self.otp_service.verify_otp(
            user=user, purpose=OTP.Purpose.LOGIN, submitted_code=otp_code
        )

        logger.info('Login completed for user %s.', user.id)
        return user

    def resend_login_otp(self, *, email: str) -> dict:
        """
        Resend LOGIN OTP for an active login flow.
        Enforces the same 60-second cooldown as registration.

        Deliberately returns the same response whether the email exists
        or not — never reveal whether an email is registered
        (AUTHENTICATION_DESIGN.md, Section 10).
        """
        email = email.lower().strip()
        user = self.user_repository.get_by_email(email)

        if user is None:
            logger.info('Login OTP resend requested for unknown email=%s.', email)
            return {"email": email}

        self.otp_service.generate_and_send_otp(user=user,purpose=OTP.Purpose.LOGIN)

        logger.info("Login OTP resent for user %s.", user.id)
        return {
            "email": email,
        }
