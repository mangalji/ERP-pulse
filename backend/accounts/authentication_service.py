import logging

from django.core.signing import BadSignature, SignatureExpired
from django.utils import timezone

from accounts import registration_cache
from accounts.exceptions import (
    AccountNotVerifiedException,
    InvalidCredentialsException,
    InvalidRegistrationTokenException,
    MaxOTPAttemptsExceededException,
    OTPExpiredException,
    OTPMismatchException,
    RegistrationSessionNotFoundException,
    ResendCooldownException,
    UserAlreadyExistsException,
)
from accounts.models import OTP, User
from accounts.repositories import UserRepository
from accounts.services import OTPService
from common import constants
from common.services.email_service import send_email
from common.utils.datetime import calculate_expiry, is_expired
from common.utils.hash import hash_value, verify_value
from common.utils.otp import generate_otp_code
from common.utils.signed_token import generate_signed_token, verify_signed_token

logger = logging.getLogger(__name__)

# Namespaces the signed token so it can never be confused with a token
# generated for a different purpose if common.utils.signed_token is ever
# reused elsewhere (e.g. a future password-reset flow).
REGISTRATION_TOKEN_SALT = 'accounts.registration.complete-profile'


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

    # -----------------------------------------------------------------
    # Registration
    # -----------------------------------------------------------------

    def register(self, *, email: str, password: str) -> dict:
        """
        Step 1: validate the email isn't already a real account, then
        generate and send a REGISTRATION OTP. Stores the pending
        registration (email + hashed password + OTP state) in cache —
        no User row is created here.
        """
        if self.user_repository.email_exists(email):
            raise UserAlreadyExistsException('An account with this email already exists.')

        self._issue_registration_otp(email=email, password_hash=hash_value(password))

        logger.info('Registration started for email=%s.', email)
        return {'email': email}

    def resend_registration_otp(self, *, email: str) -> dict:
        """Resend a REGISTRATION OTP for an in-flight registration, enforcing the cooldown."""
        pending = registration_cache.get(email)
        if pending is None:
            raise RegistrationSessionNotFoundException(
                'No registration in progress for this email. Please start again.'
            )

        seconds_since_last_send = (timezone.now() - pending['last_sent_at']).total_seconds()
        if seconds_since_last_send < constants.OTP_RESEND_COOLDOWN_SECONDS:
            wait_seconds = int(constants.OTP_RESEND_COOLDOWN_SECONDS - seconds_since_last_send)
            raise ResendCooldownException(
                f'Please wait {wait_seconds} more second(s) before requesting a new code.'
            )

        self._issue_registration_otp(email=email, password_hash=pending['password_hash'])

        logger.info('Registration OTP resent for email=%s.', email)
        return {'email': email}

    def verify_registration_otp(self, *, email: str, otp_code: str) -> dict:
        """
        Verify a REGISTRATION OTP against the cached pending registration.

        On success, returns a short-lived signed token proving this email
        completed OTP verification — required by complete_registration().
        Still does not create a User.
        """
        pending = registration_cache.get(email)
        if pending is None:
            raise RegistrationSessionNotFoundException(
                'No registration in progress for this email. Please start again.'
            )

        if pending['attempt_count'] >= constants.MAX_OTP_ATTEMPTS:
            raise MaxOTPAttemptsExceededException(
                'Too many incorrect attempts. Please request a new code.'
            )

        if is_expired(pending['otp_expires_at']):
            raise OTPExpiredException('This OTP has expired. Please request a new code.')

        if not verify_value(otp_code, pending['otp_hash']):
            pending['attempt_count'] += 1
            registration_cache.save(
                email=email,
                data=pending,
                timeout_seconds=constants.REGISTRATION_SESSION_TTL_MINUTES * 60,
            )
            logger.warning('Registration OTP mismatch for email=%s.', email)
            raise OTPMismatchException('The submitted OTP code is incorrect.')

        token = generate_signed_token(payload={'email': email}, salt=REGISTRATION_TOKEN_SALT)

        logger.info('Registration OTP verified for email=%s.', email)
        return {'email': email, 'registration_token': token}

    def complete_registration(
        self, *, registration_token: str, first_name: str, last_name: str, mobile_number: str
    ) -> User:
        """
        Final step: validate the signed token from OTP verification,
        validate mobile uniqueness, and create the User — active and
        email-verified immediately, since OTP verification already
        proved the email. This is the only point in the whole flow where
        a User row is created.
        """
        try:
            payload = verify_signed_token(
                token=registration_token,
                salt=REGISTRATION_TOKEN_SALT,
                max_age_seconds=constants.REGISTRATION_TOKEN_MAX_AGE_SECONDS,
            )
        except (BadSignature, SignatureExpired) as exc:
            raise InvalidRegistrationTokenException(
                'Your registration session is invalid or has expired. Please start again.'
            ) from exc

        email = payload['email']

        pending = registration_cache.get(email)
        if pending is None:
            raise RegistrationSessionNotFoundException(
                'Your registration session has expired. Please start again.'
            )

        if self.user_repository.mobile_number_exists(mobile_number):
            raise UserAlreadyExistsException('An account with this mobile number already exists.')

        user = self.user_repository.create_verified_user(
            email=email,
            password_hash=pending['password_hash'],
            first_name=first_name,
            last_name=last_name,
            mobile_number=mobile_number,
        )

        registration_cache.delete(email)

        logger.info('Registration completed for user %s.', user.id)
        return user

    def _issue_registration_otp(self, *, email: str, password_hash: str) -> None:
        """Shared by register()/resend_registration_otp(): generate, store, email a fresh code."""
        raw_code = generate_otp_code(length=constants.OTP_LENGTH)

        registration_cache.save(
            email=email,
            data={
                'email': email,
                'password_hash': password_hash,
                'otp_hash': hash_value(raw_code),
                'otp_expires_at': calculate_expiry(minutes=constants.OTP_EXPIRY_MINUTES),
                'attempt_count': 0,
                'last_sent_at': timezone.now(),
            },
            timeout_seconds=constants.REGISTRATION_SESSION_TTL_MINUTES * 60,
        )

        send_email(
            recipient_list=[email],
            subject=constants.EMAIL_SUBJECT_REGISTER,
            message=(
                f'Your verification code is {raw_code}. '
                f'It expires in {constants.OTP_EXPIRY_MINUTES} minutes.'
            ),
        )

    # -----------------------------------------------------------------
    # Login (unchanged)
    # -----------------------------------------------------------------

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