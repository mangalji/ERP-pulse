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


class CanVerifyInvitationEmail(permissions.BasePermission):
    """Only users who can create an invitation may consume verification API credits."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
            return True
        role = getattr(user, 'role', None)
        if role is None:
            return False
        role_name = str(getattr(role, 'name', '')).strip().casefold()
        return (
            (getattr(role, 'company_id', None) is None and role_name == 'super admin')
            or (getattr(user, 'company_id', None) is not None and role_name == 'company admin')
        )
