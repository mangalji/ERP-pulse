import re
from common.contact_validation import normalize_phone
from rest_framework import serializers
from .models import (
    Plan, CompanyPlan, SupportSession,
    SubscriptionHistory, Transaction,
    DiscountType, BillingCycle, CompanyPlanStatus,
)
from tenancy.models import Company, CompanyModule, Module
from django.contrib.auth import get_user_model
from invitations.models import Invitation, InvitationStatus

User = get_user_model()


class PlanSerializer(serializers.ModelSerializer):
    enabled_models = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Module.objects.all(),
        required=False,
    )

    class Meta:
        model = Plan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanyPlanSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    assigned_by_email = serializers.CharField(source='assigned_by.email', read_only=True)
    discount_display = serializers.SerializerMethodField()
    effective_price = serializers.SerializerMethodField()

    class Meta:
        model = CompanyPlan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'original_price', 'final_price')

    def get_discount_display(self, obj):
        if obj.discount_type == DiscountType.NONE:
            return None
        if obj.discount_type == DiscountType.PERCENTAGE:
            return f'{obj.discount_value}%'
        return f'₹{obj.discount_value}'

    def get_effective_price(self, obj):
        return obj.final_price


class SupportSessionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    support_user_name = serializers.CharField(source='support_user.get_full_name', read_only=True)
    support_user_email = serializers.EmailField(source='support_user.email',read_only=True)

    class Meta:
        model = SupportSession
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanySerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(
        read_only=True,
    )

    module_count = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = Company

        fields = "__all__"

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "contact_phone_country_code",
        )
        extra_kwargs = {
        "code": {
            "validators": [],
        },
    }

    def validate(self, attrs):
        is_create = self.instance is None

        name = (attrs.get("name") or "").strip()
        code = (attrs.get("code") or "").strip()
        email = (attrs.get("contact_email") or "").strip()
        country = (attrs.get("country") or "").strip().upper()
        phone = (attrs.get("contact_phone") or "").strip()
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

            if not code:
                raise serializers.ValidationError({
                    "code": "Company code is required."
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
            if len(name) < 3:
                raise serializers.ValidationError({
                    "name": "Company name must contain at least 3 characters."
                })

            if len(name) > 100:
                raise serializers.ValidationError({
                    "name": "Company name must not exceed 100 characters."
                })

            if not re.fullmatch(
                r"^[A-Za-z0-9À-ÖØ-öø-ÿ&().,'\- ]+$",
                name,
            ):
                raise serializers.ValidationError({
                    "name": "Company name contains unsupported characters."
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

        return attrs

    # Legacy onboarding note: company creation previously accepted admin
    # fields and sent an invitation here. User onboarding now belongs solely
    # to SuperAdminService.create_employee(), so this serializer intentionally
    # uses ModelSerializer's default company-only create behavior.


class PlanDetailSerializer(serializers.ModelSerializer):
    """Extended plan serializer for detail page."""
    enabled_modules = serializers.SerializerMethodField()
    included_modules_count = serializers.SerializerMethodField()
    companies_using_count = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_enabled_modules(self, obj):
        return [
            {
                'id': m.id,
                'name': m.name,
                'code': m.code,
                'display_name': m.display_name,
            }
            for m in obj.enabled_models.all()
        ]

    def get_included_modules_count(self, obj):
        return obj.enabled_models.count()

    def get_companies_using_count(self, obj):
        return obj.company_plans.filter(
            status__in=[CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL]
        ).count()


class CompanyPlanSummarySerializer(serializers.ModelSerializer):
    """Lightweight plan summary for company detail page."""
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    discount_display = serializers.SerializerMethodField()

    class Meta:
        model = CompanyPlan
        fields = [
            'id', 'plan_name', 'status', 'start_date', 'end_date', 'is_auto_renew',
            'discount_type', 'discount_value', 'billing_cycle', 'original_price', 'final_price',
            'discount_display',
        ]

    def get_discount_display(self, obj):
        if obj.discount_type == DiscountType.NONE:
            return None
        if obj.discount_type == DiscountType.PERCENTAGE:
            return f'{obj.discount_value}%'
        return f'₹{obj.discount_value}'


class CompanyDetailSerializer(serializers.ModelSerializer):
    """DEPRECATED: This class is overwritten by the one below (line ~328).
    Kept commented for traceability — the active class includes `transactions` + `admin_email`.
    """
    pass

    def get_current_plan(self, obj):
        plan = obj.company_plans.filter(
            status__in=['ACTIVE', 'TRIAL']
        ).select_related('plan').first()
        if plan:
            return CompanyPlanSummarySerializer(plan).data
        return None

    def get_assigned_modules(self, obj):
        modules = obj.company_modules.select_related('module').filter(enabled=True)
        return [
            {
                'id': cm.module.id,
                'name': cm.module.name,
                'code': cm.module.code,
                'display_name': cm.module.display_name,
                'enabled': cm.enabled,
            }
            for cm in modules
        ]

    def get_netsuite_connected(self, obj):
        return obj.netsuite_connections.filter(is_active=True).exists()

    def get_netsuite_account_id(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.netsuite_account_id if conn else None

    def get_netsuite_environment(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.get_environment_display() if conn and conn.environment else None

    def get_netsuite_last_sync(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.last_synced_at if conn else None


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanyModuleSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    module_code = serializers.CharField(source='module.code', read_only=True)
    company_code = serializers.CharField(
    source="company.code",
    read_only=True,
)

    class Meta:
        from tenancy.models import CompanyModule
        model = CompanyModule
        fields = '__all__'
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
            "is_staff",
            "is_email_verified",
            "role",
            "invitation_status",
            "last_activity",
        )
        read_only_fields = fields

    def get_role(self, obj):
        user_role = (
            obj.user_roles
            .select_related("role")
            .first()
        )

        if user_role:
            return user_role.role.name

        return None

    def get_invitation_status(self, obj):
        invitation = Invitation.objects.filter(email__iexact=obj.email,company=obj.company).order_by("-created_at").first()
        
        if not invitation:
            return "ACTIVE" if obj.is_active else "INACTIVE"

        if invitation.status == InvitationStatus.PENDING:
            if invitation.is_expired():
                return "EXPIRED"
            return "PENDING"

        if invitation.status == InvitationStatus.ACCEPTED:
            return "ACTIVE" if obj.is_active else "INACTIVE"

        if invitation.status == InvitationStatus.EXPIRED:
            return "EXPIRED"

        if invitation.status == InvitationStatus.CANCELLED:
            return "CANCELLED"

        return "INACTIVE"

class SubscriptionHistorySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    assigned_by_email = serializers.CharField(source='assigned_by.email', read_only=True)
    discount_display = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionHistory
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_discount_display(self, obj):
        if obj.discount_type == DiscountType.NONE:
            return None
        if obj.discount_type == DiscountType.PERCENTAGE:
            return f'{obj.discount_value}%'
        return f'₹{obj.discount_value}'


class TransactionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    discount_amount = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ('id', 'created_at')

    def get_discount_amount(self, obj):
        return obj.original_amount - obj.final_amount


class CompanyDetailSerializer(serializers.ModelSerializer):
    """Extended company serializer for the detail page.
    Includes subscription plan, assigned modules, employee stats, and NetSuite connection status.
    """
    user_count = serializers.SerializerMethodField()
    module_count = serializers.SerializerMethodField()
    active_user_count = serializers.SerializerMethodField()
    current_plan = serializers.SerializerMethodField()
    assigned_modules = serializers.SerializerMethodField()
    admin_email = serializers.SerializerMethodField()
    netsuite_connected = serializers.SerializerMethodField()
    netsuite_account_id = serializers.SerializerMethodField()
    netsuite_environment = serializers.SerializerMethodField()
    netsuite_last_sync = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'code', 'status', 'contact_email', 'contact_phone',
            'country', 'created_at', 'updated_at',
            'user_count', 'active_user_count', 'module_count',
            'current_plan', 'assigned_modules', 'admin_email',
            'netsuite_connected', 'netsuite_account_id', 'netsuite_environment', 'netsuite_last_sync',
            'transactions',
        ]
        read_only_fields = fields

    def get_user_count(self, obj):
        return obj.users.count()

    def get_active_user_count(self, obj):
        return obj.users.filter(is_active=True).count()

    def get_module_count(self, obj):
        return obj.company_modules.count()

    def get_admin_email(self, obj):
        admin = obj.users.filter(user_roles__role__name='Company Admin').first()
        return admin.email if admin else None

    def get_current_plan(self, obj):
        plan = obj.company_plans.filter(
            status__in=['ACTIVE', 'TRIAL']
        ).select_related('plan').first()
        if plan:
            return CompanyPlanSummarySerializer(plan).data
        return None

    def get_assigned_modules(self, obj):
        modules = obj.company_modules.select_related('module').filter(enabled=True)
        return [
            {
                'id': cm.module.id,
                'name': cm.module.name,
                'code': cm.module.code,
                'display_name': cm.module.display_name,
                'enabled': cm.enabled,
            }
            for cm in modules
        ]

    def get_netsuite_connected(self, obj):
        return obj.netsuite_connections.filter(is_active=True).exists()

    def get_netsuite_account_id(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.netsuite_account_id if conn else None

    def get_netsuite_environment(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.get_environment_display() if conn and conn.environment else None

    def get_netsuite_last_sync(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.last_synced_at if conn else None

    def get_transactions(self, obj):
        transactions = obj.transactions.all()[:10]
        return [
            {
                'transaction_id': t.transaction_id,
                'plan_name': t.plan.name if t.plan else None,
                'original_amount': str(t.original_amount),
                'discount_amount': str(t.original_amount - t.final_amount),
                'final_amount': str(t.final_amount),
                'payment_status': t.payment_status,
                'billing_cycle': t.billing_cycle,
                'created_at': t.created_at,
            }
            for t in transactions
        ]
