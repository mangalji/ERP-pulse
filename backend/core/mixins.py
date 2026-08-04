"""
Reusable abstract mixins for Django models.

Each mixin owns a single concern. Models can compose any combination
of these mixins without inheriting fields they don't need. ``BaseModel``
in ``core/models.py`` combines all three for the common case, but
individual mixins remain available for selective use.

No business logic lives here — only field definitions.

Note: ``AuditMixin`` references ``settings.AUTH_USER_MODEL`` (a lazy
string reference, not a direct User model import). ``BaseModel`` itself
does NOT directly reference User — all user-tracking fields live in
``AuditMixin``. This keeps ``BaseModel`` infrastructure-only.
"""

from django.conf import settings
from django.db import models


class TimestampMixin(models.Model):
    """
    Adds ``created_at`` and ``updated_at`` audit timestamps.

    Every model that needs creation/modification tracking should inherit
    this mixin (directly or via ``BaseModel``) rather than redefining
    the same two fields independently.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Adds soft-delete support via ``is_deleted`` and ``deleted_at``.

    Soft-deleted rows remain in the database with ``is_deleted=True``
    and a timestamp in ``deleted_at``. Querysets that should exclude
    soft-deleted rows filter on ``is_deleted=False``.

    This mixin only provides the fields — no custom manager or queryset
    is implemented yet. A ``SoftDeleteManager`` that automatically
    excludes soft-deleted rows by default will be added in a future
    phase.
    """

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class AuditMixin(models.Model):
    """
    Adds ``created_by`` and ``updated_by`` user-tracking fields.

    Both are nullable ``ForeignKey`` to ``settings.AUTH_USER_MODEL`` with
    ``on_delete=SET_NULL`` so that deleting a user doesn't cascade-delete
    every row they ever touched — the audit trail survives.

    ``related_name='+'`` disables the reverse relation so these generic
    audit fields don't clutter the User model's namespace with
    ``created_<model>_set`` / ``updated_<model>_set`` accessors for every
    model that uses the mixin.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        abstract = True