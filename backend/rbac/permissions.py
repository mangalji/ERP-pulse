"""
Reusable permission classes for RBAC — foundation only.

These classes verify role membership, permission codes, and module
access for the requesting user. They are NOT yet integrated into any
views — that integration happens in a later phase.

Each class extends DRF's BasePermission and returns True/False from
has_permission(). Results are cached per-user (or per-user+company)
for a short TTL to reduce unnecessary database queries.
"""

from django.core.cache import cache

from rest_framework.permissions import BasePermission

from rbac.models import RolePermission, UserRole
from tenancy.models import CompanyModule

# Short TTL so permission changes propagate quickly.
CACHE_TTL_SECONDS = 60


def _cache_key(prefix: str, user_id) -> str:
    return f'rbac:{prefix}:{user_id}'


class HasRole(BasePermission):
    """
    Allow access only if the user has at least one of the given roles.

    Usage::

        permission_classes = [HasRole]
        HasRole.roles = ['ADMIN', 'MANAGER']
    """

    roles: list[str] = []

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        role_names = set(self.roles or [])
        if not role_names:
            return False

        cache_key = _cache_key('roles', user.id)
        user_role_names = cache.get(cache_key)
        if user_role_names is None:
            user_role_names = set(
                UserRole.objects.filter(user=user).values_list('role__name', flat=True)
            )
            cache.set(cache_key, user_role_names, CACHE_TTL_SECONDS)

        return bool(user_role_names & role_names)


class HasPermission(BasePermission):
    """
    Allow access only if the user has at least one of the given
    permission codes (via their roles).

    Usage::

        permission_classes = [HasPermission]
        HasPermission.codes = ['invoice.read', 'invoice.write']
    """

    codes: list[str] = []

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        permission_codes = set(self.codes or [])
        if not permission_codes:
            return False

        cache_key = _cache_key('permissions', user.id)
        user_codes = cache.get(cache_key)
        if user_codes is None:
            user_codes = set(
                RolePermission.objects.filter(
                    role__user_roles__user=user,
                ).values_list('permission__code', flat=True).distinct()
            )
            cache.set(cache_key, user_codes, CACHE_TTL_SECONDS)

        return bool(user_codes & permission_codes)


class HasModuleAccess(BasePermission):
    """
    Allow access only if the user's company has the given module
    enabled.

    Usage::

        permission_classes = [HasModuleAccess]
        HasModuleAccess.code = 'netsuite'
    """

    code: str | None = None

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        company = getattr(user, 'company', None)
        if company is None:
            return False
        module_code = self.code
        if not module_code:
            return False

        cache_key = _cache_key(f'module:{module_code}', company.id)
        has_access = cache.get(cache_key)
        if has_access is None:
            has_access = CompanyModule.objects.filter(
                company=company,
                module__code=module_code,
                enabled=True,
            ).exists()
            cache.set(cache_key, has_access, CACHE_TTL_SECONDS)

        return has_access