from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import User


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
        'is_active',
        'is_email_verified',
        'is_staff',
    )
    list_filter = ('is_active', 'is_staff', 'is_email_verified')
    search_fields = ('email', 'first_name', 'last_name', 'mobile_number')
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_login', 'last_login_at')

    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'mobile_number')}),
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
                    'password1',
                    'password2',
                ),
            },
        ),
    )
