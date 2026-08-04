from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsSuperAdmin(permissions.BasePermission):
    """
    Allows access only to super admin users.
    Super admin is defined as either:
    1. A Django superuser (is_superuser=True)
    2. A user with the global 'super_admin' role (company=None)
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if getattr(request.user, 'is_superuser', False):
            return True

        return request.user.user_roles.filter(
            role__company__isnull=True,
            role__name='super_admin',
        ).exists()