import secrets
import string
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password
from rest_framework.response import Response
from django.core import signing

OTP_LENGTH = 6

OTP_EXPIRY_MINUTES = 5

MAX_OTP_ATTEMPTS = 3

OTP_RESEND_COOLDOWN_SECONDS = 60
EMAIL_SUBJECT_LOGIN = "Your AGSuite ERP login OTP"
EMAIL_SUBJECT_PASSWORD_RESET = "Reset your AGSuite ERP password"
EMAIL_SUBJECT_PROFILE_UPDATE = "Confirm your AGSuite ERP profile update"

def calculate_expiry(minutes: int) -> datetime:
    """Return a timezone-aware timestamp `minutes` from now."""
    return timezone.now() + timedelta(minutes=minutes)


def is_expired(expires_at: datetime) -> bool:
    """Return True if the given timestamp is at or before the current time."""
    return timezone.now() >= expires_at

def hash_value(raw_value: str) -> str:
    """
    Hash a raw string using Django's configured password hasher.

    Reused for OTP codes (not just passwords) per AUTHENTICATION_DESIGN.md
    Decision AUTH-007: OTP codes are hashed at rest using the same
    precedent as passwords, rather than a separate hashing scheme.
    """
    return make_password(raw_value)


def verify_value(raw_value: str, hashed_value: str) -> bool:
    """Check whether a raw string matches a previously hashed value."""
    return check_password(raw_value, hashed_value)


def generate_otp_code(length: int = 6) -> str:
    """
    Generate a random numeric OTP code of the given length.

    Uses `secrets` (not `random`) because OTP codes are a security control —
    they must not be predictable from a seeded or time-based PRNG.
    """
    if length < 4:
        raise ValueError('OTP length must be at least 4 digits.')

    return ''.join(secrets.choice(string.digits) for _ in range(length))

def success_response(*,message:str,data:dict|None=None, status_code:int=200)->Response:
    """Build a success envelope response"""
    return Response(
        {"success":True,
         'message':message,
         'data':data if data is not None else {}},
         status=status_code,
    )

def generate_signed_token(*, payload: dict, salt: str) -> str:
    """Create a signed, tamper-proof token carrying `payload`."""
    return signing.dumps(payload, salt=salt)


def verify_signed_token(*, token: str, salt: str, max_age_seconds: int) -> dict:
    """
    Decode and verify a token created by generate_signed_token().

    Raises django.core.signing.BadSignature (invalid/tampered/wrong salt)
    or django.core.signing.SignatureExpired (past max_age_seconds).
    Callers should catch these and translate to a domain-specific
    exception rather than let them leak past the service layer.
    """
    return signing.loads(token, salt=salt, max_age=max_age_seconds)