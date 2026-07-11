import logging

from django.conf import settings

from accounts.exceptions import OTPExpiredException, OTPMismatchException, OTPNotFoundException
from accounts.models import OTP
from accounts.repositories import OTPRepository
from common.services.email_service import send_email
from common.utils.datetime import calculate_expiry, is_expired
from common.utils.hash import hash_value, verify_value
from common.utils.otp import generate_otp_code

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

        Invalidates any prior active OTP of the same purpose, generates
        and hashes a new code, persists it, and emails the plaintext code
        to the user. Returns the saved OTP row (never the plaintext code —
        callers that need to confirm delivery only need to know an OTP was
        issued, not what it was).
        """
        self.repository.invalidate_previous_otps(user=user, purpose=purpose)

        raw_code = generate_otp_code(length=settings.OTP_LENGTH)
        otp_hash = hash_value(raw_code)
        expires_at = calculate_expiry(minutes=settings.OTP_EXPIRY_MINUTES)

        otp = self.repository.create_otp(
            user=user,
            otp_hash=otp_hash,
            purpose=purpose,
            expires_at=expires_at,
        )

        send_email(
            to_email=user.email,
            subject='Your ERP Pulse verification code',
            message=(
                f'Your verification code is {raw_code}. '
                f'It expires in {settings.OTP_EXPIRY_MINUTES} minutes.'
            ),
        )

        logger.info('OTP issued for user %s (purpose=%s).', user.id, purpose)
        return otp

    def verify_otp(self, user, purpose: str, submitted_code: str) -> OTP:
        """
        Verify a submitted OTP code against the latest active OTP for the
        given user/purpose. Marks the OTP as used on success.

        Raises:
            OTPNotFoundException: no active OTP exists for this user/purpose.
            OTPExpiredException: the OTP exists but has expired.
            OTPMismatchException: the submitted code does not match.
        """
        otp = self.repository.get_latest_active_otp(user=user, purpose=purpose)
        if otp is None:
            logger.warning('No active OTP found for user %s (purpose=%s).', user.id, purpose)
            raise OTPNotFoundException('No active OTP found for this user and purpose.')

        if is_expired(otp.expires_at):
            logger.warning('Expired OTP verification attempt for user %s.', user.id)
            raise OTPExpiredException('This OTP has expired.')

        if not verify_value(submitted_code, otp.otp_hash):
            logger.warning('OTP mismatch for user %s (purpose=%s).', user.id, purpose)
            raise OTPMismatchException('The submitted OTP code is incorrect.')

        self.repository.mark_as_used(otp)
        logger.info('OTP verified successfully for user %s (purpose=%s).', user.id, purpose)
        return otp
