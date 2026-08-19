from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import Invitation, InvitationStatus
from accounts.models import User


# Keep invitation-specific mobile validation intentionally limited to
# number shape here. The selected country already belongs to the User record
# because the administrator sets it during employee creation. The service
# should normalize/validate the mobile against that stored country.
mobile_number_validator = RegexValidator(
    regex=r"^\+?[1-9]\d{6,14}$",
    message="Enter a valid mobile number.",
)


class InvitationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )
    role_name = serializers.CharField(
        source="role.name",
        read_only=True,
    )
    created_by_email = serializers.CharField(
        source="created_by.email",
        read_only=True,
    )

    class Meta:
        model = Invitation
        fields = (
            "id",
            "token",
            "email",
            "company",
            "company_name",
            "role",
            "role_name",
            "status",
            "expires_at",
            "accepted_at",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "token",
            "created_at",
            "updated_at",
        )


class CreateInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100)
    company_id = serializers.UUIDField()
    role_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    # expires_in_days = serializers.IntegerField(
    #     required=False,
    #     default=7,
    #     min_value=1,
    #     max_value=30,
    # )

    def validate_company_id(self, value):
        from tenancy.models import Company

        if not Company.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Company not found.")
        return value

    def validate_role_id(self, value):
        from rbac.models import Role

        if value is not None and not Role.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Role not found.")
        return value


class RequestInvitationOTPSerializer(serializers.Serializer):
    """
    First invitation-setup step.

    The administrator already created the user's:
    - first name
    - last name
    - country
    - gender

    The invitee only supplies the password at this step.
    Mobile number is handled during final acceptance.
    """

    token = serializers.UUIDField()

    password = serializers.CharField(
        write_only=True,
        max_length=128,
        validators=[validate_password],
    )

    confirm_password = serializers.CharField(
        write_only=True,
        max_length=128,
    )

    def validate(self, attrs):
        confirm_password = attrs.pop("confirm_password")

        if attrs["password"] != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        return attrs


class AcceptInvitationSerializer(serializers.Serializer):
    """
    Final invitation acceptance.

    The invitee is NOT allowed to modify administrator-controlled identity
    fields. First name, last name, country, and gender are intentionally
    absent.

    The invitee may optionally provide/update only the mobile number.
    """

    token = serializers.UUIDField()

    password = serializers.CharField(
        write_only=True,
        max_length=128,
        validators=[validate_password],
    )

    otp = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
        validators=[
            RegexValidator(
                regex=r"^\d{6}$",
                message="OTP must be exactly 6 digits.",
            )
        ],
    )

    mobile_number = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=20,
        validators=[mobile_number_validator],
    )


class InvitationValidateSerializer(serializers.Serializer):
    token = serializers.UUIDField()