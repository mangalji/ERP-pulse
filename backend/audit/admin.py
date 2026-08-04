from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin configuration for the AuditLog model."""

    list_display = ('company', 'user', 'module', 'action', 'entity', 'entity_id', 'created_at')
    list_filter = ('module', 'action', 'created_at')
    search_fields = ('entity', 'entity_id', 'user__email', 'company__name')
    readonly_fields = ('id', 'company', 'user', 'module', 'action', 'entity', 'entity_id', 'old_value', 'new_value', 'ip_address', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False