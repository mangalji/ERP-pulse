import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from accounts.managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model using email as the unique login identifier.

    Built on AbstractBaseUser + PermissionsMixin (rather than AbstractUser)
    because AbstractUser ships with a `username` field that this project
    does not use — starting from AbstractBaseUser avoids carrying an unused
    field. PermissionsMixin still provides is_superuser, groups, and
    user_permissions for Django admin compatibility.

    Field set and naming follow AUTHENTICATION_DESIGN.md, Section 3.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=20, unique=True)

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

    last_login_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'mobile_number']

    class Meta:
        db_table = 'user'

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self) -> str:
        return self.first_name


class OTP(models.Model):
    """
    A one-time password issued for either registration or login
    verification, per AUTHENTICATION_DESIGN.md, Section 4.

    Only the schema is defined here. Generation, hashing, sending, and
    verification logic are implemented by OTPService in a later task —
    this model intentionally contains no behavior beyond field definitions,
    per CODE_STYLE.md ("Models should NOT ... perform analytics").
    """

    class Purpose(models.TextChoices):
        REGISTRATION = 'REGISTRATION', 'Registration'
        LOGIN = 'LOGIN', 'Login'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='otps',
    )

    # The OTP code itself is never stored in plaintext — only its hash,
    # matching the password-hashing precedent (AUTHENTICATION_DESIGN.md,
    # Decision AUTH-007). max_length mirrors AbstractBaseUser.password,
    # since OTP hashing is expected to reuse Django's password hasher.
    otp_hash = models.CharField(max_length=128)

    purpose = models.CharField(max_length=20, choices=Purpose.choices)

    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'otp'
        indexes = [
            # Speeds up the "latest valid OTP for this user/purpose" lookup
            # used by both the registration and login verification flows
            # (AUTHENTICATION_DESIGN.md, Section 13).
            models.Index(fields=['user', 'purpose', 'is_used'], name='otp_user_purpose_used_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.get_purpose_display()} OTP for {self.user.email}'
