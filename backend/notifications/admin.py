from django.contrib import admin

from notifications.models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for the Notification model."""

    list_display = ('title', 'user', 'company', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__email', 'company__name')
    readonly_fields = ('id', 'company', 'user', 'title', 'message', 'type', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin configuration for the NotificationPreference model."""

    list_display = ('user', 'category', 'email_enabled', 'in_app_enabled', 'push_enabled')
    list_filter = ('category', 'email_enabled', 'in_app_enabled', 'push_enabled')
    search_fields = ('user__email', 'category')