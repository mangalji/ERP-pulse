"""
Reusable permission base classes for AGSuite ERP.

Only generic, cross-cutting permission classes belong here.
Business-specific permissions (e.g., "only the connection owner can
modify this NetSuite connection") stay in the respective app's own
permissions module (see ``ocr/permissions.py`` for an existing example).

These classes extend DRF's ``BasePermission`` so they can be used in
``permission_classes`` on any view.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthenticatedReadOnly(BasePermission):
    """
    Allow read access (GET, HEAD, OPTIONS) to any authenticated user.
    Write access (POST, PUT, PATCH, DELETE) is denied.

    Useful for list/detail views where all authenticated users can
    view data but only specific roles should modify it.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.method in SAFE_METHODS
        )


class IsOwnerOrReadOnly(BasePermission):
    """
    Read access for any authenticated user.
    Write access only if the object's ``user`` field matches the
    requesting user.

    The object must have a ``user`` attribute (FK to AUTH_USER_MODEL).
    If the object doesn't have a ``user`` attribute, write access is
    denied — this is a safe default that forces the view to explicitly
    override ``has_object_permission`` for objects without a user FK.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.method in SAFE_METHODS
                or request.method in ('POST',)
            )
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, 'user', None)
        if owner is None:
            return False
        return owner == request.user