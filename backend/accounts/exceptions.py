class OTPNotFoundException(Exception):
    """Raised when no active (unused) OTP exists for the given user and purpose."""


class OTPExpiredException(Exception):
    """Raised when a matching OTP exists but has passed its expiry time."""


class OTPMismatchException(Exception):
    """Raised when the submitted OTP code does not match the stored hash."""

class UserAlreadyExistsException(Exception):
    """Raised at registration when the email or mobile number is already in use."""


class InvalidCredentialsException(Exception):
    """
    Raised when email/password authentication fails, or when an email
    cannot be matched at all. Deliberately used for both cases — never
    reveal whether a given email is registered (AUTHENTICATION_DESIGN.md,
    Section 10).
    """


class AccountNotVerifiedException(Exception):
    """Raised when login is attempted before registration OTP verification is complete."""
