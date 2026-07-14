"""
Signed, short-lived token utility built on Django's own `signing` module
(HMAC-signed with SECRET_KEY — no new dependency, no database row).

Used wherever a flow needs to prove "this step already happened" across
separate stateless HTTP requests without persisting a row for it — e.g.
proving OTP verification completed before allowing registration profile
completion. Deliberately generic (not accounts-specific) since the same
need will come up again for other multi-step flows (e.g. a future
password-reset flow).
"""

from django.core import signing


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