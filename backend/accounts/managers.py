from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Manager for the custom User model.

    Django's default UserManager assumes a `username` field. Since email is
    USERNAME_FIELD (AUTHENTICATION_DESIGN.md, Section 3), user creation must
    be keyed on email instead.
    """

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError('The email field is required.')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        """
        Create and save a superuser with the given email and password.

        A superuser is created already active and email-verified, since the
        registration OTP flow (not yet implemented) does not apply to
        accounts created via the management command.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_email_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)
