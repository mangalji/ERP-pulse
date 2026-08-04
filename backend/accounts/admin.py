from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import OTP, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Admin configuration for the custom User model.

    Extends Django's built-in UserAdmin but replaces its username-based
    fieldsets/list views, since this project has no `username` field and
    uses email as USERNAME_FIELD instead.
    """

    ordering = ('email',)
    list_display = (
        'email',
        'first_name',
        'last_name',
        'mobile_number',
        'company',
        'designation',
        'department',
        'is_active',
        'is_email_verified',
        'is_staff',
    )
    list_filter = ('is_active', 'is_staff', 'is_email_verified', 'company')
    search_fields = ('email', 'first_name', 'last_name', 'mobile_number', 'employee_id', 'designation', 'department')
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_login', 'last_login_at')

    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'mobile_number')}),
        (
            'Company',
            {
                'fields': (
                    'company',
                    'employee_id',
                    'designation',
                    'department',
                    'last_activity',
                )
            },
        ),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_email_verified',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        (
            'Important Dates',
            {'fields': ('last_login', 'last_login_at', 'created_at', 'updated_at')},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'first_name',
                    'last_name',
                    'mobile_number',
                    'company',
                    'employee_id',
                    'designation',
                    'department',
                    'password1',
                    'password2',
                ),
            },
        ),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """
    Admin configuration for the OTP model.

    Read-only by design: OTP rows must only ever be created by OTPService
    (a later task), never manually through the admin, so add permission is
    disabled entirely. `is_used` remains editable so support staff can
    manually invalidate a live OTP (e.g. a user reports a suspected leak)
    without being able to forge a valid hash, expiry, or purpose.
    """

    ordering = ('-created_at',)
    list_display = ('user', 'purpose', 'is_used', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_used')
    search_fields = ('user__email',)
    readonly_fields = (
        'id', 'user', 'otp_hash', 'purpose', 'expires_at', 'created_at', 'updated_at',
    )

    def has_add_permission(self, request) -> bool:
        return False
