"""
Abstract BaseModel for all ERP Pulse domain models.

``BaseModel`` composes ``TimestampMixin``, ``SoftDeleteMixin``, and
``AuditMixin`` and adds a UUID primary key — the standard field set
every domain model in this project needs.

Existing models in ``accounts``, ``ai``, ``ocr``, ``netsuite``, ``sync``,
and ``monitoring`` are intentionally NOT migrated to inherit from
``BaseModel`` in this phase. They continue to use their own field
definitions so no migrations are triggered and no existing imports break.
New models created from Phase 0.3 onward should inherit ``BaseModel``
instead of redefining these fields.
"""

import uuid

from django.db import models

from core.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin


class BaseModel(TimestampMixin, SoftDeleteMixin, AuditMixin, models.Model):
    """
    Abstract base model for all ERP Pulse domain models.

    Provides:
    - UUID primary key (``id``)
    - Timestamps (``created_at``, ``updated_at``) via ``TimestampMixin``
    - Soft-delete fields (``is_deleted``, ``deleted_at``) via ``SoftDeleteMixin``
    - Audit user tracking (``created_by``, ``updated_by``) via ``AuditMixin``

    Subclasses only need to define their domain-specific fields — all
    infrastructure fields come from this base.

    Usage::

        from core.models import BaseModel

        class MyModel(BaseModel):
            name = models.CharField(max_length=255)
            # id, created_at, updated_at, is_deleted, deleted_at,
            # created_by, updated_by are all inherited automatically.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True