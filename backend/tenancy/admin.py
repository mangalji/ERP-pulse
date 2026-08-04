from django.contrib import admin

from tenancy.models import Company, CompanyModule, CompanySettings, Module


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin configuration for the Company model."""

    list_display = ('name', 'code', 'status', 'contact_email', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'code', 'contact_email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    ordering = ('name',)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """Admin configuration for the Module model."""

    list_display = ('name', 'code', 'display_name', 'icon', 'sort_order', 'is_active', 'is_system')
    list_filter = ('is_active', 'is_system')
    search_fields = ('name', 'code', 'display_name')
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')


@admin.register(CompanyModule)
class CompanyModuleAdmin(admin.ModelAdmin):
    """Admin configuration for the CompanyModule model."""

    list_display = ('company', 'module', 'enabled', 'usage_limit', 'activated_at')
    list_filter = ('enabled', 'module')
    search_fields = ('company__name', 'module__name')
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    """Admin configuration for the CompanySettings model."""

    list_display = ('company', 'timezone', 'currency', 'language', 'date_format', 'number_format')
    search_fields = ('company__name',)
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')
