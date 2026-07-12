from django.contrib import admin

from netsuite.models import NetSuiteConnection


@admin.register(NetSuiteConnection)
class NetSuiteConnectionAdmin(admin.ModelAdmin):
    """
    Read-only admin view for support/debugging — connections are only
    ever created by NetSuiteConnectionService via the OAuth callback, and
    tokens must never be hand-edited.
    """

    ordering = ('-connected_at',)
    list_display = (
        'user', 'netsuite_account_id', 'is_active', 'access_token_expires_at', 'connected_at',
    )
    list_filter = ('is_active',)
    search_fields = ('user__email', 'netsuite_account_id')
    readonly_fields = (
        'id', 'user', 'netsuite_account_id', 'access_token', 'refresh_token',
        'access_token_expires_at', 'refresh_token_expires_at', 'connected_at', 'updated_at',
    )

    def has_add_permission(self, request) -> bool:
        return False
