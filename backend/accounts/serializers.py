from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers
from common import constants
from accounts.models import User

otp_code_validator = RegexValidator(
    regex = r'^\d+$',
    message = 'OTP code must be digits only'
)

class RegisterSerializer(serializers.Serializer):
    """
    Validates registration input.
 
    Field-level validation only (types, lengths, password strength via
    Django's configured AUTH_PASSWORD_VALIDATORS). Uniqueness checks for
    email/mobile_number are business rules and remain in
    AuthenticationService.register(), which raises
    UserAlreadyExistsException — not duplicated here.
    """
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    mobile_number = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True, validators=[validate_password])

class VerifyRegistrationOTPSerializer(serializers.Serializer):
    """
    Validates registration OTP verification input.
 
    Whether the OTP actually matches, is expired, or exists at all is
    decided by OTPService.verify_otp() — this only checks shape.
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(
        max_length=constants.OTP_LENGTH,
        min_length=constants.OTP_LENGTH,
        validators = [otp_code_validator]
    )

class LoginSerializer(serializers.Serializer):
    """
    Validates Step 1 (email/password) login input.
 
    Credential correctness and account verification state are checked by
    AuthenticationService.login(), not here.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class VerifyLoginOTPSerializer(serializers.Serializer):
    """
    Validates Step 2 (OTP) login input.
 
    Mirrors VerifyRegistrationOTPSerializer's shape validation; OTP
    correctness is decided by OTPService.verify_otp().
    """
 
    email = serializers.EmailField()
    otp_code = serializers.CharField(
        max_length=constants.OTP_LENGTH,
        min_length=constants.OTP_LENGTH,
        validators=[otp_code_validator],
    )

class UserSerializer(serializers.ModelSerializer):
    """
    Public-safe representation of a User.
 
    Reused for both the "user" object embedded in the Verify Login OTP
    response and GET /api/v1/auth/me/, so the shape only needs to be
    defined once. Deliberately excludes password, is_staff, is_superuser,
    and permission/group fields — a user should never see more about
    their own account than this via the API.
    """
 
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'mobile_number',
            'is_active',
            'is_email_verified',
            'created_at',
        ]
        read_only_fields = fields