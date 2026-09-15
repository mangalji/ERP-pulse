from django.contrib import admin
from rbac.models import Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'company',
        'is_system',
        'created_at',
    )

    list_filter = (
        'is_system',
        'company',
    )

    search_fields = (
        'name',
        'description',
        'company__name',
    )

    readonly_fields = (
        'id',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'name',
                    'description',
                    'company',
                    'is_system',
                    'permissions',
                )
            },
        ),
        (
            'Audit',
            {
                'fields': (
                    'id',
                    'created_by',
                    'updated_by',
                    'created_at',
                    'updated_at',
                )
            },
        ),
    )

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return False

        return super().has_delete_permission(request, obj)