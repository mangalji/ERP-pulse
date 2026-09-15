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

        role = getattr(request.user, 'role', None)

        return (
            role is not None
            and role.company_id is None
            and role.name.lower() == 'super admin'
        )