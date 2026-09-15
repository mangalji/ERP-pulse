from django.core.cache import cache
from rest_framework.permissions import BasePermission


CACHE_TTL_SECONDS = 60


def _cache_key(prefix: str, user_id) -> str:
    return f'rbac:{prefix}:{user_id}'


class HasPermission(BasePermission):
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
            user_codes = set()

            if user.role_id:
                user_codes = set(user.role.permissions or [])

            cache.set(
                cache_key,
                user_codes,
                CACHE_TTL_SECONDS,
            )

        return bool(user_codes & permission_codes)