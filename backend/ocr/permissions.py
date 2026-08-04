"""
Custom DRF permissions for the OCR application.

Phase 1 only defines a thin permission layer; finer-grained rules
(e.g. per-tenant quotas, paid-plan gating) can be added here later
without touching views or services.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthenticatedReadOnly(BasePermission):
    """
    Allows read access to any authenticated user.

    Write operations (POST, PUT, PATCH, DELETE) are denied — the OCR
    pipeline is not yet implemented, so no client should be mutating
    state. This keeps the placeholder endpoint locked down while still
    allowing future GET endpoints (e.g. listing past extractions) to
    work for any logged-in user.
    """

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.method in SAFE_METHODS
        )