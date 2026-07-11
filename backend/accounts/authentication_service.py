import logging

from accounts.exceptions import (
    AccountNotVerifiedException,
    InvalidCredentialsException,
    UserAlreadyExistsException,
)
from accounts.models import OTP, User
from accounts.repositories import UserRepository
from accounts.services import OTPService

logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Business logic for registration and the two-step, OTP-gated login flow
    (AUTHENTICATION_DESIGN.md, Sections 5-6).

    Orchestrates UserRepository and OTPService only — it never queries the
    database directly. JWT issuance is intentionally out of scope: every
    method here returns a User instance, and token generation is left to a
    separate caller/service once OTP verification succeeds.
    """

    def __init__(self, user_repository: UserRepository | None = None, otp_service=None):
        self.user_repository = user_repository or UserRepository()
        self.otp_service = otp_service or OTPService()

    def register(
        self, *, email: str, password: str, first_name: str, last_name: str, mobile_number: str
    ) -> User:
        """
        Register a new user.

        Validates that the email and mobile number are not already in use,
        creates an inactive/unverified account (defaults come from the
        User model itself, not repeated here), and sends a REGISTRATION
        OTP.
        """
        if self.user_repository.email_exists(email):
            raise UserAlreadyExistsException('An account with this email already exists.')

        if self.user_repository.mobile_number_exists(mobile_number):
            raise UserAlreadyExistsException(
                'An account with this mobile number already exists.'
            )

        user = self.user_repository.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            mobile_number=mobile_number,
        )

        self.otp_service.generate_and_send_otp(user=user, purpose=OTP.Purpose.REGISTRATION)

        logger.info('Registration started for user %s.', user.id)
        return user

    def verify_registration_otp(self, *, email: str, otp_code: str) -> User:
        """Verify a REGISTRATION OTP and activate the account on success."""
        user = self.user_repository.get_by_email(email)
        if user is None:
            raise InvalidCredentialsException('Invalid email or verification code.')

        self.otp_service.verify_otp(
            user=user, purpose=OTP.Purpose.REGISTRATION, submitted_code=otp_code
        )

        user = self.user_repository.activate_and_verify(user)

        logger.info('Registration completed for user %s.', user.id)
        return user

    def login(self, *, email: str, password: str) -> User:
        """
        Step 1 of login: verify credentials and, if valid and the account
        is active/verified, send a LOGIN OTP. Issues no token.
        """
        user = self.user_repository.get_by_email(email)

        if user is None or not user.check_password(password):
            # Same exception for "no such user" and "wrong password" —
            # never reveal whether an email is registered.
            logger.warning('Login attempt failed for email=%s.', email)
            raise InvalidCredentialsException('Invalid email or password.')

        if not user.is_active or not user.is_email_verified:
            logger.warning('Login rejected for unverified/inactive user %s.', user.id)
            raise AccountNotVerifiedException(
                'This account has not completed registration verification.'
            )

        self.otp_service.generate_and_send_otp(user=user, purpose=OTP.Purpose.LOGIN)

        logger.info('Login OTP sent for user %s.', user.id)
        return user

    def verify_login_otp(self, *, email: str, otp_code: str) -> User:
        """
        Step 2 of login: verify the LOGIN OTP and return the authenticated
        User. Issues no token — that is a separate, later concern.
        """
        user = self.user_repository.get_by_email(email)
        if user is None:
            raise InvalidCredentialsException('Invalid email or verification code.')

        self.otp_service.verify_otp(
            user=user, purpose=OTP.Purpose.LOGIN, submitted_code=otp_code
        )

        logger.info('Login completed for user %s.', user.id)
        return user
