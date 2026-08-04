from django.contrib import admin

from rbac.models import Permission, Role, RolePermission, UserRole


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_system', 'created_at')
    list_filter = ('is_system', 'company')
    search_fields = ('name', 'description', 'company__name')
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'module', 'is_system')
    list_filter = ('module', 'is_system')
    search_fields = ('code', 'name', 'module')
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission')
    list_filter = ('role',)
    search_fields = ('role__name', 'permission__code')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__email', 'role__name')