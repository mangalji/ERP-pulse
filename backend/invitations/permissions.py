from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    """
    Allows access only to super admin users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False):
            return True
        return request.user.user_roles.filter(
            role__company__isnull=True,
            role__name__iexact='super_admin',
        ).exists()


class IsInvitationOwner(permissions.BasePermission):
    """
    Allows access only to the invited email or super admins.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False):
            return True
        return request.user.user_roles.filter(
            role__company__isnull=True,
            role__name__iexact='super_admin',
        ).exists()
