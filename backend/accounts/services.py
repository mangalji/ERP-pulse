import logging
from django.db import transaction
from accounts.exceptions import (
    OTPExpiredException, 
    OTPMismatchException, 
    OTPNotFoundException,
    MaxOTPAttemptsExceededException, 
    ResendCooldownException,
    OTPEmailDeliveryException,
    )
from django.utils import timezone
from accounts.models import OTP
from accounts.repositories import OTPRepository
from common.email_service import send_email
from common.common_utils import calculate_expiry, is_expired
from common.common_utils import hash_value, verify_value
from common.common_utils import generate_otp_code
from common.common_utils import (
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_LENGTH,
    OTP_EXPIRY_MINUTES,
    MAX_OTP_ATTEMPTS,
)

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

        with transaction.atomic():
            # Lock the user row so concurrent OTP generation requests
            # for the same user are serialized.
            user.__class__.objects.select_for_update().get(pk=user.pk)

            existing_otp = self.repository.get_latest_active_otp(
                user=user,
                purpose=purpose,
            )

            if existing_otp is not None:
                seconds_since_last_send = (
                    timezone.now() - existing_otp.created_at
                ).total_seconds()

                if seconds_since_last_send < OTP_RESEND_COOLDOWN_SECONDS:
                    wait_seconds = int(
                        OTP_RESEND_COOLDOWN_SECONDS - seconds_since_last_send
                    )
                    raise ResendCooldownException(
                        f"Please wait {wait_seconds} more second(s) before requesting new code."
                    )

            self.repository.invalidate_previous_otps(
                user=user,
                purpose=purpose,
            )

            raw_code = generate_otp_code(length=OTP_LENGTH)
            otp_hash = hash_value(raw_code)
            expires_at = calculate_expiry(minutes=OTP_EXPIRY_MINUTES)

            otp = self.repository.create_otp(
                user=user,
                otp_hash=otp_hash,
                purpose=purpose,
                expires_at=expires_at,
            )

            logger.info(
                'OTP issued for user %s (purpose=%s).',
                user.id,
                purpose,
            )

        # Email delivery outside the atomic transaction — failure here
        # must NOT roll back the OTP record. The OTP is already saved,
        # so the user can request a resend. This matches the same
        # pattern used in AuthenticationService._issue_registration_otp().
        try:
            sent_count = send_email(
                recipient_list=[user.email],
                subject='Your AGSuite ERP verification code',
                message=(
                    f'Your verification code is {raw_code}. '
                    f'It expires in {OTP_EXPIRY_MINUTES} minutes.'
                ),
                fail_silently=True,
            )
            if sent_count != 1:
                raise OTPEmailDeliveryException(
                    'We could not send the verification code right now. Please try again later.'
                )
        except OTPEmailDeliveryException:
            raise

        except Exception as exc:
            logger.exception(
                "Failed to send login OTP email to %s — OTP saved in DB",
                user.email,
            )
            raise OTPEmailDeliveryException(
                'We could not send the verification code right now. Please try again later.'
            ) from exc

        return otp

    def verify_otp(self, user, purpose: str, submitted_code: str, *, expected_otp_id=None) -> OTP:
        # Callers must not surround OTP verification with a rollback-on-error
        # transaction: failure counters must survive an invalid-code response.
        mismatch = False
        with transaction.atomic():
            otp = self.repository.get_latest_active_otp(
                user=user, purpose=purpose, for_update=True,
            )
            if otp is None or (expected_otp_id is not None and str(otp.pk) != str(expected_otp_id)):
                raise OTPNotFoundException('No matching verification code. Restart login.')
            if otp.attempt_count >= MAX_OTP_ATTEMPTS:
                raise MaxOTPAttemptsExceededException('Too many incorrect attempts. Request a new code.')
            if is_expired(otp.expires_at):
                raise OTPExpiredException('This OTP has expired. Request a new code.')
            if not verify_value(submitted_code, otp.otp_hash):
                self.repository.increment_attempt_count(otp)
                mismatch = True
            else:
                self.repository.mark_as_used(otp)
        if mismatch:
            raise OTPMismatchException('The code you entered is incorrect. Please try again.')
        return otp
