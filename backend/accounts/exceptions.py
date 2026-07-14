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

class RegistrationSessionNotFoundException(Exception):
    """
    Raised when no in-flight registration exists for a given email —
    either it was never started, or its cache entry has expired. The two
    cases are indistinguishable once the cache entry is gone, so they
    share one exception rather than two.
    """
    status_code = status.HTTP_404_NOT_FOUND
 
 
class ResendCooldownException(Exception):
    """Raised when a resend is requested before the 60-second cooldown has elapsed."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
 
 
class MaxOTPAttemptsExceededException(Exception):
    """
    Raised when the current registration OTP has already been guessed
    wrong the maximum number of times.
    """
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
 
 
class InvalidRegistrationTokenException(Exception):
    """
    Raised when the Complete Profile step's signed token is missing,
    invalid, tampered with, or expired.
    """
    status_code = status.HTTP_400_BAD_REQUEST