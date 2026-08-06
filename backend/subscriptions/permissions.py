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
        # Company admin check
        if getattr(request.user, 'company', None) is not None:
            return True
        return False
