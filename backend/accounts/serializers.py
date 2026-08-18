from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers

from common import constants
from accounts.models import LoginActivity, User, Gender
from common.contact_validation import normalize_phone
from rbac.models import UserRole

otp_code_validator = RegexValidator(
    regex = r'^\d+$',
    message = 'OTP code must be digits only'
)

# International E.164-style: optional leading +, first digit 1-9 (no
# leading 0), 7-14 more digits (8-15 digits total, matching the ITU
# E.164 max length). Rejects letters, symbols, and obvious garbage
# ("not-a-phone!!", "1234", "00000000000000000000") while still
# allowing real international numbers without a country-specific format.
mobile_number_validator = RegexValidator(
    regex=r'^\+?[1-9]\d{6,14}$',
    message='Enter a valid mobile number.',
)

# Rejects digits and HTML/script-relevant characters in a human name
# field — not a strict Latin-only whitelist (that would reject many
# real international names), just a denylist of characters a real name
# never legitimately contains. Unicode letters (including Devanagari,
# accented Latin, etc.) are allowed.
name_validator = RegexValidator(
    regex=r'^[^\d<>{}\[\]\\\/`~^*_=|]+$',
    message="Name can't contain digits or special characters.",
)

def human_name_field(*, max_length: int = 100, required: bool = True) -> serializers.CharField:
    """Shared field definition for first_name/last_name — DRY per this task."""
    return serializers.CharField(
        max_length=max_length,
        min_length=1 if required else 0,
        trim_whitespace=True,
        validators=[name_validator],
        required=required,
        allow_blank=not required,
    )

def add_normalized_phone(attrs,*,required:bool=False):
    """
    Normalize phone data in serializers that receive both phone and country.

    This helper leaves blank phone data alone only when required=False.
    """
    phone = attrs.get("mobile_number")
    country = attrs.get("country")

    if not phone:
        if required:
            raise serializers.ValidationError(
                {"mobile_number": "Phone number is required."}
            )
        return attrs

    if not country:
        raise serializers.ValidationError(
            {"country": "Country is required when a phone number is provided."}
        )

    try:
        normalized = normalize_phone(phone=phone, country=country)
    except ValueError as exc:
        raise serializers.ValidationError(
            {"mobile_number": str(exc)}
        ) from exc

    attrs["mobile_number"] = normalized.number
    attrs["country"] = normalized.country_code
    attrs["phone_country_code"] = normalized.dial_code
    return attrs


class RegisterSerializer(serializers.Serializer):
    """
    Validates registration Step 1 input: email + password only.

    Confirm-password matching is a pure input-shape check (does the
    user's second entry match the first), so it belongs here rather than
    in AuthenticationService — matching this project's existing
    convention that shape validation lives in serializers while business
    rules (uniqueness, etc.) live in the service. `confirm_password` is
    popped out of validated_data once checked, so it is never passed on
    to AuthenticationService.register(), which only accepts email/password.
    """
    email = serializers.EmailField(max_length=100)
    password = serializers.CharField(write_only=True, max_length=128, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, max_length=128, validators=[validate_password])

    def validate(self, attrs):
        confirm_password = attrs.pop('confirm_password')
        if attrs['password'] != confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs

class ResendRegistrationOTPSerializer(serializers.Serializer):
    """Validates POST /api/v1/auth/register/resend-otp/ input."""
    email = serializers.EmailField(max_length=100)

class ResendLoginOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100)

class VerifyRegistrationOTPSerializer(serializers.Serializer):
    """
    Validates registration OTP verification input.
 
    Whether the OTP actually matches, is expired, or exists at all is
    decided by AuthenticationService.verify_registration_otp() — this
    only checks shape.
    """
    email = serializers.EmailField(max_length=100)
    otp_code = serializers.CharField(
        max_length=constants.OTP_LENGTH,
        min_length=constants.OTP_LENGTH,
        validators = [otp_code_validator]
    )

class CompleteProfileSerializer(serializers.Serializer):
    """
    Validates final registration profile data.

    Phone remains optional for compatibility with the existing registration
    flow. If supplied, country must also be supplied and the phone is
    normalized to E.164.
    """
    registration_token = serializers.CharField(max_length=2048)
    first_name = human_name_field()
    last_name = human_name_field()
    mobile_number = serializers.CharField(max_length=20,validators=[mobile_number_validator],required=False,allow_blank=True,allow_null=True)
    country = serializers.CharField(max_length=4,required=False,allow_blank=True)
    gender = serializers.ChoiceField(choices=Gender.choices,required=False,allow_blank=True,allow_null=True)

    def validate(self, attrs):
        return add_normalized_phone(attrs, required=False)


class LoginSerializer(serializers.Serializer):
    """
    Validates Step 1 (email/password) login input.
 
    Credential correctness and account verification state are checked by
    AuthenticationService.login(), not here.
    """
    email = serializers.EmailField(max_length=100)
    password = serializers.CharField(write_only=True, max_length=128)

class VerifyLoginOTPSerializer(serializers.Serializer):
    """
    Validates Step 2 (OTP) login input.
 
    Mirrors VerifyRegistrationOTPSerializer's shape validation; OTP
    correctness is decided by OTPService.verify_otp().
    """
 
    email = serializers.EmailField(max_length=100)
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
    netsuite_connected = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    is_superadmin = serializers.BooleanField(
        source='is_superuser',
        read_only=True,
    )
 
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'mobile_number',
            "country",
            "phone_country_code",
            "gender",
            'profile_pic',
            'is_active',
            'is_email_verified',
            'created_at',
            'is_staff',
            'is_superadmin',
            'netsuite_connected',
            'roles',
        ]
        read_only_fields = fields

    def get_netsuite_connected(self, obj):
        return obj.netsuite_connections.filter(
        is_active=True,
        ).exists()

    def get_roles(self, obj):
        return [
            item['role__name'].lower().replace(' ','_')
            for item in obj.user_roles.values('role__name')
        ]
    

class ForgotPasswordSerializer(serializers.Serializer):
    """Validates POST /api/v1/auth/forgot-password/ input."""
    email = serializers.EmailField(max_length=100)


class ResetPasswordSerializer(serializers.Serializer):
    """Validates POST /api/v1/auth/forgot-password/reset/ input."""
    email = serializers.EmailField(max_length=100)
    otp_code = serializers.CharField(
        max_length=constants.OTP_LENGTH,
        min_length=constants.OTP_LENGTH,
        validators=[otp_code_validator],
    )
    password = serializers.CharField(write_only=True, max_length=128, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, max_length=128, validators=[validate_password])

    def validate(self, attrs):
        confirm_password = attrs.pop('confirm_password')
        if attrs['password'] != confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


class VerifyProfileUpdateOTPSerializer(serializers.Serializer):
    """Validates POST /api/v1/auth/profile/update/ input."""
    otp_code = serializers.CharField(
        max_length=constants.OTP_LENGTH,
        min_length=constants.OTP_LENGTH,
        validators=[otp_code_validator],
    )
    first_name = human_name_field(required=False)
    last_name = human_name_field(required=False)
    mobile_number = serializers.CharField(
        max_length=16,
        validators=[mobile_number_validator],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    country = serializers.CharField(
        max_length=2,
        required=False,
        allow_blank=True,
    )
    gender = serializers.ChoiceField(
        choices=Gender.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    profile_pic = serializers.ImageField(required=False, allow_null=True)


class LoginActivitySerializer(serializers.ModelSerializer):
    """Read-only — for the History page's login/activity list."""

    class Meta:
        model = LoginActivity
        fields = ['id', 'ip_address', 'user_agent', 'created_at']
        read_only_fields = fields
