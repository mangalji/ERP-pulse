from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers
from common import constants
from accounts.models import User, LoginActivity

otp_code_validator = RegexValidator(
    regex = r'^\d+$',
    message = 'OTP code must be digits only'
)

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
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        confirm_password = attrs.pop('confirm_password')
        if attrs['password'] != confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs

class ResendRegistrationOTPSerializer(serializers.Serializer):
    """Validates POST /api/v1/auth/register/resend-otp/ input."""
    email = serializers.EmailField()

class ResendLoginOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyRegistrationOTPSerializer(serializers.Serializer):
    """
    Validates registration OTP verification input.
 
    Whether the OTP actually matches, is expired, or exists at all is
    decided by AuthenticationService.verify_registration_otp() — this
    only checks shape.
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(
        max_length=constants.OTP_LENGTH,
        min_length=constants.OTP_LENGTH,
        validators = [otp_code_validator]
    )

class CompleteProfileSerializer(serializers.Serializer):
    """
    Validates the final registration step: first/last name, mobile
    number, and the signed token issued by VerifyRegistrationOTPView.
    Mobile-number uniqueness is a business rule and stays in
    AuthenticationService.complete_registration().
    """
    registration_token = serializers.CharField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    mobile_number = serializers.CharField(max_length=15)

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
    netsuite_connected = serializers.SerializerMethodField()
 
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
            'netsuite_connected'
        ]
        read_only_fields = fields

    def get_netsuite_connected(self, obj):
        return obj.netsuite_connections.filter(
        is_active=True,
        ).exists()
    
class LoginActivitySerializer(serializers.ModelSerializer):
    """Read-only — for the History page's login/activity list."""

    class Meta:
        model = LoginActivity
        fields = ['id','ip_address','user_agent','created_at']
        read_only_fields = fields