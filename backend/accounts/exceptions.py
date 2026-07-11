from rest_framework import status

class OTPNotFoundException(Exception):
    """Raised when no active (unused) OTP exists for the given user and purpose."""
    status_code = status.HTTP_400_BAD_REQUEST


class OTPExpiredException(Exception):
    """Raised when a matching OTP exists but has passed its expiry time."""
    status_code = status.HTTP_400_BAD_REQUEST


class OTPMismatchException(Exception):
    """Raised when the submitted OTP code does not match the stored hash."""
    status_code = status.HTTP_400_BAD_REQUEST

class UserAlreadyExistsException(Exception):
    """Raised at registration when the email or mobile number is already in use."""
    status_code = status.HTTP_409_CONFLICT


class InvalidCredentialsException(Exception):
    """
    Raised when email/password authentication fails, or when an email
    cannot be matched at all. Deliberately used for both cases — never
    reveal whether a given email is registered (AUTHENTICATION_DESIGN.md,
    Section 10).
    """
    status_code = status.HTTP_401_UNAUTHORIZED


class AccountNotVerifiedException(Exception):
    """Raised when login is attempted before registration OTP verification is complete."""
    status_code = status.HTTP_403_FORBIDDEN