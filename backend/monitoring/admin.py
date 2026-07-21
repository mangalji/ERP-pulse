from django.contrib import admin

from monitoring.models import ErrorLog, RequestLog


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    ordering = ('-created_at',)
    list_display = ('level', 'method', 'path', 'status_code', 'user', 'created_at')
    list_filter = ('level', 'status_code')
    search_fields = ('message', 'path', 'exception_type', 'user__email')
    readonly_fields = (
        'id', 'level', 'message', 'exception_type', 'traceback',
        'method', 'path', 'status_code', 'user', 'created_at',
    )

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    ordering = ('-created_at',)
    list_display = ('method', 'path', 'status_code', 'response_time_ms', 'is_throttled', 'created_at')
    list_filter = ('method', 'is_throttled')
    search_fields = ('path', 'user__email')
    readonly_fields = (
        'id', 'method', 'path', 'status_code', 'response_time_ms',
        'is_throttled', 'user', 'created_at',
    )

    def has_add_permission(self, request) -> bool:
        return False