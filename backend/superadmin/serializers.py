import re
from common.contact_validation import normalize_phone
from common.email_verification import ensure_email_deliverable
from rest_framework import serializers
from .models import (
    Plan, 
    Transaction,
)
from tenancy.models import Company
from django.contrib.auth import get_user_model
from django.utils import timezone
from invitations.status import get_user_invitation_status

User = get_user_model()


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'description', 'price', 'validity_days', 'status', 'created_at', 'updated_at']
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanySerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = Company

        fields = "__all__"

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "status",
            "suspension_reason",
            "plan",
            "plan_start_date",
            "plan_end_date",
        )
        extra_kwargs = {
        "code": {
            "validators": [],
            "required": False,
        },
    }

    def validate(self, attrs):
        is_create = self.instance is None

        name = (attrs.get("name") or "").strip()
        code = (attrs.get("code") or "").strip()
        email = (attrs.get("contact_email") or "").strip()
        country_input = (attrs.get("country") or "").strip()
        country = country_input.upper()
        phone = (attrs.get("contact_phone") or "").strip()

        if is_create and not code and name:
            base = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").upper() or "COMPANY"
            base = base[:20]
            candidate = base
            suffix = 2
            while Company.objects.filter(code__iexact=candidate).exists():
                suffix_text = f"-{suffix}"
                candidate = f"{base[:20 - len(suffix_text)]}{suffix_text}"
                suffix += 1
            code = candidate
            attrs["code"] = code
        # Prevent duplicate company identity.
        # Name and code are compared case-insensitively.
        name_queryset = Company.objects.filter(
            name__iexact=name,
        )

        code_queryset = Company.objects.filter(
            code__iexact=code,
        )

        if self.instance:
            name_queryset = name_queryset.exclude(
                pk=self.instance.pk,
            )
            code_queryset = code_queryset.exclude(
                pk=self.instance.pk,
            )

        if name_queryset.exists():
            raise serializers.ValidationError({
                "name": "A company with this name is already registered."
            })

        if code_queryset.exists():
            raise serializers.ValidationError({
                "code": "This company code is already assigned to another company."
            })        

        # Required fields on company creation.
        if is_create:
            if not name:
                raise serializers.ValidationError({
                    "name": "Company name is required."
                })

            if not email:
                raise serializers.ValidationError({
                    "contact_email": "Contact email is required."
                })

            if not country:
                raise serializers.ValidationError({
                    "country": "Country is required."
                })

            if not phone:
                raise serializers.ValidationError({
                    "contact_phone": "Contact phone is required."
                })

        # Company name
        if name:
            if len(name) > 100:
                raise serializers.ValidationError({
                    "name": "Company name must not exceed 100 characters."
                })
            attrs["name"] = name

        # Company code
        if code:
            if len(code) < 2:
                raise serializers.ValidationError({
                    "code": "Company code must contain at least 2 characters."
                })

            if len(code) > 20:
                raise serializers.ValidationError({
                    "code": "Company code must not exceed 20 characters."
                })

            if not re.fullmatch(r"^[A-Za-z0-9_-]+$", code):
                raise serializers.ValidationError({
                    "code": "Company code may contain only letters, numbers, hyphens and underscores."
                })

            attrs["code"] = code

        # Contact email
        if email:
            if len(email) > 40:
                raise serializers.ValidationError({
                    "contact_email": "Contact email must not exceed 40 characters."
                })

            if is_create:
                try:
                    ensure_email_deliverable(email)
                except ValueError as exc:
                    raise serializers.ValidationError({
                        "contact_email": str(exc)
                    }) from exc

            attrs["contact_email"] = email

        # Country + phone
        if country or phone:
            if not country:
                raise serializers.ValidationError({
                    "country": "Country is required when a contact phone is provided.",
             })

            if not phone:
                raise serializers.ValidationError({
                    "contact_phone": "Contact phone is required."
                })

            if len(country) == 2 and country.isalpha():
                try:
                    normalized = normalize_phone(
                        phone=phone,
                        country=country,
                    )
                except ValueError as exc:
                    raise serializers.ValidationError({
                        "contact_phone": str(exc)
                    }) from exc

                attrs["contact_phone"] = normalized.number
                attrs["country"] = normalized.country_code
                attrs["contact_phone_country_code"] = normalized.dial_code
            else:
                custom_code = (attrs.get("contact_phone_country_code") or "").strip()
                digits = "".join(character for character in phone if character.isdigit())
                if not re.fullmatch(r"\+[1-9]\d{0,2}", custom_code):
                    raise serializers.ValidationError({
                        "contact_phone_country_code": "Enter a valid country calling code, e.g. +91."
                    })
                if len(digits) < 7 or len(digits) > 15:
                    raise serializers.ValidationError({
                        "contact_phone": "Phone number must contain between 7 and 15 digits."
                    })
                if len(custom_code[1:]) + len(digits) > 15:
                    raise serializers.ValidationError({
                        "contact_phone": "The international phone number cannot exceed 15 digits."
                    })
                attrs["country"] = country_input
                attrs["contact_phone"] = digits
                attrs["contact_phone_country_code"] = custom_code

        return attrs

    # Legacy onboarding note: company creation previously accepted admin
    # fields and sent an invitation here. User onboarding now belongs solely
    # to SuperAdminService.create_employee(), so this serializer intentionally
    # uses ModelSerializer's default company-only create behavior.


class CompanyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company

        fields = [
            'name',
            'code',
            'contact_email',
            'contact_phone_country_code',
            'contact_phone',
            'country',
        ]
        read_only_fields = (
            'code',
            'contact_email',
            'contact_phone_country_code',
        )

    def validate(self, attrs):
        country = (attrs.get('country') or '').strip().upper()
        phone = (attrs.get('contact_phone') or '').strip()

        if not country and not phone:
            return attrs
        if not country:
            raise serializers.ValidationError({'country': 'Country is required.'})
        if not phone:
            raise serializers.ValidationError({'contact_phone': 'Contact phone is required.'})

        try:
            normalized = normalize_phone(phone=phone, country=country)
        except ValueError as exc:
            raise serializers.ValidationError({'contact_phone': str(exc)}) from exc

        attrs['contact_phone'] = normalized.number
        attrs['country'] = normalized.country_code
        attrs['contact_phone_country_code'] = normalized.dial_code
        return attrs


class PlanDetailSerializer(serializers.ModelSerializer):
    """Extended plan serializer for detail page."""

    class Meta:
        model = Plan
        fields = ['id', 'name', 'description', 'price', 'validity_days', 'status', 'created_at', 'updated_at']
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(
        source="get_full_name",
        read_only=True,
    )

    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    class Meta:
        model = User

        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "employee_id",
            "designation",
            "department",
            "is_active",
            "is_staff",
            "is_email_verified",
            "last_activity",
            "company",
            "company_name",
        )

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "is_staff",
            "is_active",
            "company",
        )

class SuperAdminEmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(
        source="get_full_name",
        read_only=True,
    )

    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )
    company_status = serializers.CharField(
        source="company.status",
        read_only=True,
    )

    role = serializers.SerializerMethodField()
    invitation_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "employee_id",
            "designation",
            "department",
            "company",
            "company_name",
            "is_active",
            "company_status",
            "is_staff",
            "is_email_verified",
            "role",
            "invitation_status",
            "last_activity",
        )
        read_only_fields = fields

    def get_role(self, obj):
        return obj.role.name if obj.role_id else None

    def get_invitation_status(self, obj):
        return get_user_invitation_status(
            obj,
            latest_invitation_by_email=self.context.get(
                'latest_invitation_by_email'
            ),
        )


class TransactionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ('id', 'transaction_id', 'created_at', 'updated_at')


class CompanyDetailSerializer(serializers.ModelSerializer):
    """Extended company serializer for the detail page.
    Includes subscription plan, assigned modules, employee stats, and NetSuite connection status.
    """
    user_count = serializers.SerializerMethodField()
    active_user_count = serializers.SerializerMethodField()
    current_plan = serializers.SerializerMethodField()
    admin_email = serializers.SerializerMethodField()
    netsuite_connected = serializers.SerializerMethodField()
    netsuite_account_id = serializers.SerializerMethodField()
    netsuite_environment = serializers.SerializerMethodField()
    netsuite_last_sync = serializers.SerializerMethodField()
    netsuite_connections = serializers.SerializerMethodField()
    netsuite_connection_count = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'code', 'status', 'contact_email', 'contact_phone',
            'country', 'created_at', 'updated_at',
            'user_count', 'active_user_count',
            'current_plan', 'admin_email',
            'netsuite_connected', 'netsuite_account_id', 'netsuite_environment', 'netsuite_last_sync',
            'netsuite_connections', 'netsuite_connection_count',
            'transactions', 'suspension_reason',
        ]
        read_only_fields = fields

    def get_user_count(self, obj):
        return obj.users.count()

    def get_active_user_count(self, obj):
        return obj.users.filter(is_active=True).count()
    
    def get_admin_email(self, obj):
        admin = obj.users.filter(role__name='Company Admin').first()
        return admin.email if admin else None

    def get_current_plan(self, obj):
        if not obj.plan_id:
            return None
        # Subscription status is derived from the assigned dates.
        # "status" below is the Plan catalog status, not the subscription's.
        today = timezone.now().date()
        if obj.plan_start_date and obj.plan_start_date > today:
            subscription_status = "UPCOMING"
        elif obj.plan_end_date and obj.plan_end_date < today:
            subscription_status = "EXPIRED"
        else:
            subscription_status = "ACTIVE"

        return {
            "id": str(obj.plan.id),
            "name": obj.plan.name,
            "description": obj.plan.description,
            "price": str(obj.plan.price),
            "validity_days": obj.plan.validity_days,
            "status": obj.plan.status,
            "subscription_status": subscription_status,
            "start_date": obj.plan_start_date,
            "end_date": obj.plan_end_date,
        }

    def get_netsuite_connected(self, obj):
        return obj.netsuite_connections.filter(is_active=True, status='connected').exists()

    def _current_netsuite_connection(self, obj):
        return obj.netsuite_connections.filter(
            is_active=True,
            status='connected',
        ).order_by('-updated_at').first()

    def get_netsuite_account_id(self, obj):
        conn = self._current_netsuite_connection(obj)
        return conn.netsuite_account_id if conn else None

    def get_netsuite_environment(self, obj):
        conn = self._current_netsuite_connection(obj)
        return conn.get_environment_display() if conn and conn.environment else None

    def get_netsuite_last_sync(self, obj):
        conn = self._current_netsuite_connection(obj)
        return conn.last_synced_at if conn else None

    def get_netsuite_connection_count(self, obj):
        return obj.netsuite_connections.count()

    def get_netsuite_connections(self, obj):
        return [
            {
                'id': str(connection.id),
                'client_name': connection.client_name,
                'netsuite_account_id': connection.netsuite_account_id,
                'environment': connection.get_environment_display(),
                'status': connection.status,
                'is_current': bool(connection.is_active and connection.status == 'connected'),
                'last_synced_at': connection.last_synced_at,
                'connected_at': connection.connected_at,
            }
            for connection in obj.netsuite_connections.all().order_by('-updated_at')
        ]

    def get_transactions(self, obj):
        transactions = obj.transactions.all()[:10]
        return [
            {
                'transaction_id': t.transaction_id,
                'plan_name': t.plan.name if t.plan else None,
                'original_amount': str(t.original_amount),
                'discount_amount': str(t.discount_amount),
                'total_amount': str(t.total_amount),
                'transaction_status': t.transaction_status,
                'payment_method': t.payment_method,
                'payment_status': t.payment_status,
                'created_at': t.created_at,
            }
            for t in transactions
        ]
