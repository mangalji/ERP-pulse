from rest_framework import serializers
from .models import Plan, CompanyPlan, SupportSession
from tenancy.models import Company, Module
from django.contrib.auth import get_user_model

User = get_user_model()


class PlanSerializer(serializers.ModelSerializer):
    enabled_modules = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name'
    )

    class Meta:
        model = Plan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanyPlanSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CompanyPlan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class SupportSessionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    support_user_name = serializers.CharField(source='support_user.get_full_name', read_only=True)

    class Meta:
        model = SupportSession
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanySerializer(serializers.ModelSerializer):
    # For company detail, we might need nested data, but we'll keep it simple for now
    class Meta:
        model = Company
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanyModuleSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    module_code = serializers.CharField(source='module.code', read_only=True)

    class Meta:
        from tenancy.models import CompanyModule
        model = CompanyModule
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'full_name', 'employee_id', 'designation', 'department', 'is_active', 'is_staff', 'is_email_verified', 'last_activity', 'company')
        read_only_fields = ('id', 'created_at', 'updated_at')