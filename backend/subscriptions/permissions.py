from rest_framework import permissions


class IsSuperAdminOrCompanyAdmin(permissions.BasePermission):
    """
    Allows access to super admins or company admins.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False):
            return True
        if getattr(request.user, 'is_staff', False):
            return True
        return bool(
            getattr(request.user, 'company_id', None)
            and getattr(request.user, 'role', None) is not None
            and request.user.role.name.casefold() == 'company admin'
        )


class IsSuperAdminOrInternalUser(permissions.BasePermission):
    """Allow platform Super Admins and AGSuite internal users only.

    Internal users are platform accounts, represented by ``company=None``;
    client-company users must never be able to view billing records.
    """

    message = 'Only Super Admin or internal AGSuite users can view billing transactions.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
            return True

        return getattr(user, 'company_id', None) is None
