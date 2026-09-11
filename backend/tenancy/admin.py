from django.contrib import admin

from tenancy.models import Company, CompanySettings


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin configuration for the Company model."""

    list_display = ('name', 'code', 'status', 'contact_email', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'code', 'contact_email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    ordering = ('name',)


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    """Admin configuration for the CompanySettings model."""

    list_display = ('company', 'timezone', 'currency', 'language', 'date_format', 'number_format')
    search_fields = ('company__name',)
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')
