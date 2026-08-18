"""
Serializers for the Client Company Portal (company-scoped).

Reuses the same User, Role, Company and CompanySettings models as the
rest of the platform — no duplicate models. The company is never
accepted from the client; it is pinned to ``request.user.company`` in
the service/view layer.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from common.contact_validation import normalize_phone
from invitations.models import Invitation, InvitationStatus
from rbac.models import Role
from accounts.models import Gender
from tenancy.models import Company, CompanySettings

User = get_user_model()

def normalize_company_phone(attrs, *, require_country_with_phone=True):
    phone = attrs.get("contact_phone")
    country = attrs.get("country")

    if not phone:
        return attrs

    if not country and require_country_with_phone:
        raise serializers.ValidationError(
            {"country": "Country is required when a contact phone is provided."}
        )

    if not country:
        return attrs

    try:
        normalized = normalize_phone(
            phone=phone,
            country=country,
        )
    except ValueError as exc:
        raise serializers.ValidationError(
            {"contact_phone": str(exc)}
        ) from exc

    attrs["contact_phone"] = normalized.number
    attrs["country"] = normalized.country_code
    attrs["contact_phone_country_code"] = normalized.dial_code
    return attrs


def normalize_employee_phone(attrs):
    phone = attrs.get("mobile_number")
    country = attrs.get("country")

    if not phone:
        return attrs

    if not country:
        raise serializers.ValidationError(
            {"country": "Country is required when a phone number is provided."}
        )

    try:
        normalized = normalize_phone(
            phone=phone,
            country=country,
        )
    except ValueError as exc:
        raise serializers.ValidationError(
            {"mobile_number": str(exc)}
        ) from exc

    attrs["mobile_number"] = normalized.number
    attrs["country"] = normalized.country_code
    attrs["phone_country_code"] = normalized.dial_code
    return attrs



class CompanyEmployeeSerializer(serializers.ModelSerializer):
    """Read representation of a company employee."""

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    company = serializers.UUIDField(source='company_id', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    roles = serializers.SerializerMethodField()
    invitation_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'mobile_number',
            "country",
            "phone_country_code",
            "gender",
            'employee_id',
            'designation',
            'department',
            'is_active',
            'is_email_verified',
            'last_activity',
            'company',
            'company_name',
            'roles',
            'invitation_status',
            'created_at',
        )
        read_only_fields = fields

    def get_roles(self, obj):
        return list(
            obj.user_roles.select_related('role').values('role_id', 'role__name')
        )

    def get_invitation_status(self, obj):
        invitation = Invitation.objects.filter(
            email=obj.email,
            company=obj.company,
        ).order_by('-created_at').first()
        
        if not invitation:
            return 'NONE'
        if invitation.status == InvitationStatus.ACCEPTED:
            return 'ACCEPTED'
        if invitation.is_expired():
            return 'EXPIRED'
        return invitation.status


class CreateEmployeeSerializer(serializers.Serializer):
    """Validates input for creating a company employee via invitation."""

    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    mobile_number = serializers.CharField(required=True,max_length=20)
    country = serializers.CharField(required=True,max_length=2)
    gender = serializers.ChoiceField(choices=Gender.choices,required=True)
    designation = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)
    role_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self,attrs):
        return normalize_employee_phone(attrs)

class UpdateEmployeeSerializer(serializers.ModelSerializer):
    """Validates PATCH input for updating a company employee."""

    role_id = serializers.UUIDField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=Gender.choices,
        required=False,
        allow_null=True,
    )
    country = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2,
    )
    mobile_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=20,
    )

    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            "mobile_number",
            "country",
            "gender",
            'designation',
            'department',
            'role_id',
        )
        extra_kwargs = {
            'first_name': {
                'required': False,
                'allow_blank': True,
                'trim_whitespace': True,
            },
            'last_name': {
                'required': False,
                'allow_blank': True,
                'trim_whitespace': True,
            },
            'designation': {
                'required': False,
                'allow_blank': True,
            },
            'department': {
                'required': False,
                'allow_blank': True,
            },
        }

    def validate(self, attrs):
        return normalize_employee_phone(attrs)


class ClientRoleSerializer(serializers.ModelSerializer):
    """A role that may be assigned to employees of the current company.

    Only global roles (``company IS NULL``) and roles belonging to the
    current user's company are eligible — never another company's roles.
    """

    class Meta:
        model = Role
        fields = ('id', 'name', 'description', 'is_system')
        read_only_fields = fields


class CompanyProfileSerializer(serializers.ModelSerializer):
    """Flattened company profile for the client portal.

    Exposes only fields already present on Company / CompanySettings —
    no new database fields are invented.
    """

    timezone = serializers.CharField(source='settings.timezone', read_only=True)
    currency = serializers.CharField(source='settings.currency', read_only=True)
    language = serializers.CharField(source='settings.language', read_only=True)
    date_format = serializers.CharField(source='settings.date_format', read_only=True)
    number_format = serializers.CharField(source='settings.number_format', read_only=True)
    contact_phone_country_code = serializers.CharField(
        read_only=True,
    )

    class Meta:
        model = Company
        fields = (
            'id',
            'name',
            'code',
            'status',
            'contact_email',
            'contact_phone',
            'contact_phone_country_code',
            'country',
            'timezone',
            'currency',
            'language',
            'date_format',
            'number_format',
        )
        read_only_fields = fields


class CompanySettingsUpdateSerializer(serializers.Serializer):
    """Validates PATCH input for company-level settings.

    Only exposes fields already present on Company and CompanySettings.
    """

    contact_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        max_length=40,
    )
    
    contact_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20,
    )
    
    country = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2,
    )
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=100)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=10)
    language = serializers.CharField(required=False, allow_blank=True, max_length=10)
    date_format = serializers.CharField(required=False, allow_blank=True, max_length=20)
    number_format = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate(self, attrs):
        return normalize_company_phone(attrs)