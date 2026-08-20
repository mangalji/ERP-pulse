import logging
from django.db import transaction
from accounts.exceptions import (
    OTPExpiredException, OTPMismatchException, OTPNotFoundException,
    MaxOTPAttemptsExceededException, ResendCooldownException
    )
from django.utils import timezone
from accounts.models import OTP
from accounts.repositories import OTPRepository
from common.services.email_service import send_email
from common.utils.datetime import calculate_expiry, is_expired
from common.utils.hash import hash_value, verify_value
from common.utils.otp import generate_otp_code
from common import constants

logger = logging.getLogger(__name__)


class OTPService:
    """
    Business logic for issuing and verifying OTPs.

    Orchestrates the OTP utility, hash utility, datetime utility, email
    service, and OTP repository — it deliberately does not reimplement
    generation, hashing, or expiry math, since those already exist in
    common/utils/. This class only decides *when* and *how* to combine
    them.
    """

    def __init__(self, repository: OTPRepository | None = None):
        self.repository = repository or OTPRepository()

    def generate_and_send_otp(self, user, purpose: str) -> OTP:
        """
        Issue a new OTP for the given user/purpose.

        Enforces OTP_RESEND_COOLDOWN_SECONDS against the previous active
        OTP for this user/purpose (if any) before issuing — centralized
        here, rather than duplicated per call site, so every purpose
        (login, password reset, profile update, registration resend)
        gets the same protection against rapid repeat sends without
        each caller having to remember to check it. Registration itself
        is the one exception: it isn't backed by a DB row yet at that
        point, so its cooldown is enforced separately against the
        cached session in AuthenticationService.

        Invalidates any prior active OTP of the same purpose, generates
        and hashes a new code, persists it, and emails the plaintext code
        to the user. Returns the saved OTP row (never the plaintext code —
        callers that need to confirm delivery only need to know an OTP was
        issued, not what it was).

        Email delivery is intentionally outside the atomic transaction:
        if the SMTP server is unreachable or rejects the connection,
        the OTP record in the database is NOT rolled back — the user
        can request a resend without losing the just-issued code.
        """

        existing_otp = self.repository.get_latest_active_otp(user=user,purpose=purpose)
        if existing_otp is not None:
            seconds_since_last_send = (timezone.now() - existing_otp.created_at).total_seconds()
            if seconds_since_last_send < constants.OTP_RESEND_COOLDOWN_SECONDS:
                wait_seconds = int(constants.OTP_RESEND_COOLDOWN_SECONDS - seconds_since_last_send)
                raise ResendCooldownException(
                    f"Please wait {wait_seconds} more second(s) before requesting new code."
                )
        with transaction.atomic():
            self.repository.invalidate_previous_otps(user=user, purpose=purpose)

            raw_code = generate_otp_code(length=constants.OTP_LENGTH)
            otp_hash = hash_value(raw_code)
            expires_at = calculate_expiry(minutes=constants.OTP_EXPIRY_MINUTES)

            otp = self.repository.create_otp(
                user=user,
                otp_hash=otp_hash,
                purpose=purpose,
                expires_at=expires_at,
            )

            logger.info('OTP issued for user %s (purpose=%s).', user.id, purpose)

        # Log OTP visibly for development (console backend prints to terminal).
        logger.info(
            "%s OTP for user %s (%s): %s (expires in %d minutes)",
            purpose.replace('_', ' ').title(),
            user.id, user.email, raw_code, constants.OTP_EXPIRY_MINUTES,
        )

        # Email delivery outside the atomic transaction — failure here
        # must NOT roll back the OTP record. The OTP is already saved,
        # so the user can request a resend. This matches the same
        # pattern used in AuthenticationService._issue_registration_otp().
        try:
            send_email(
                recipient_list=[user.email],
                subject='Your AGSuite ERP verification code',
                message=(
                    f'Your verification code is {raw_code}. '
                    f'It expires in {constants.OTP_EXPIRY_MINUTES} minutes.'
                ),
                fail_silently=True,
            )
        except Exception:
            logger.exception(
                "Failed to send login OTP email to %s — OTP saved in DB, user can resend.",
                user.email,
            )

        return otp

    def verify_otp(self, user, purpose: str, submitted_code: str) -> OTP:
        """
        Verify a submitted OTP code against the latest active OTP for the
        given user/purpose. Marks the OTP as used on success.

        Raises:
            OTPNotFoundException: no active OTP exists for this user/purpose.
            MaxOTPAttemptsExceededException: too many wrong guesses against
                this OTP already (common.constants.MAX_OTP_ATTEMPTS) —
                checked before expiry so a locked-out OTP reports as
                locked, not merely expired, even if both are true.
            OTPExpiredException: the OTP exists but has expired.
            OTPMismatchException: the submitted code does not match.
        """
        otp = self.repository.get_latest_active_otp(user=user, purpose=purpose)
        if otp is None:
            logger.warning('No active OTP found for user %s (purpose=%s).', user.id, purpose)
            raise OTPNotFoundException('No active verification code found. Please request a new one.')

        if otp.attempt_count >=constants.MAX_OTP_ATTEMPTS:
            logger.warning("OTP attempt limit reached for user %s (purpose=%s).",user.id, purpose)
            raise MaxOTPAttemptsExceededException("Too many incorrect attempts. Please request a new code.")
        
        if is_expired(otp.expires_at):
            logger.warning('Expired OTP verification attempt for user %s.', user.id)
            raise OTPExpiredException('This OTP has expired. Please request a new code.')

        if not verify_value(submitted_code, otp.otp_hash):
            new_attempt_count = self.repository.increment_attempt_count(otp).attempt_count

            logger.warning('OTP mismatch for user %s (purpose=%s).', user.id, purpose, new_attempt_count, constants.MAX_OTP_ATTEMPTS)
            raise OTPMismatchException('The code you entered is incorrect. Please try again.')

        self.repository.mark_as_used(otp)
        logger.info('OTP verified successfully for user %s (purpose=%s).', user.id, purpose)
        return otp
