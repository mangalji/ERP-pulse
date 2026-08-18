from django.contrib.auth.hashers import check_password, make_password


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
