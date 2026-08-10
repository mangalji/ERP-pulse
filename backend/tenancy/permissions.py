"""
Tenancy permission classes.

Client portal endpoints are company-scoped: only authenticated users who
belong to a company may access them. The company is always derived from
``request.user.company`` (never from the client), so a user can never
reach data belonging to another company.
"""

from rest_framework import permissions
from rbac.permissions import HasPermission

class IsCompanyUser(permissions.BasePermission):
    """
    Allows access only to authenticated users who belong to a company.
    """

    message = 'A company account is required to access this resource.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return bool(getattr(request.user, 'company', None))

class CanManageEmployees(HasPermission):
    codes = ['employee.manage']