"""Safe, structured company audit logging."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from audit.models import AuditAction, AuditActivityType, AuditLog, AuditModule, AuditStatus


logger = logging.getLogger(__name__)

SENSITIVE_DETAIL_KEYS = {
    "access_token", "refresh_token", "token", "client_secret", "secret",
    "password", "otp", "raw_body", "normalized_body", "authorization",
}


def redact_detail(value, *, key: str = ""):
    """Keep audit evidence useful without persisting secrets or email bodies."""
    if key.casefold() in SENSITIVE_DETAIL_KEYS:
        return "[redacted]"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_detail(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_detail(item, key=key) for item in value]
    if isinstance(value, str):
        return value[:4000]
    return value


class AuditService:
    """Write immutable audit entries without blocking source workflows."""

    def log(
        self,
        *,
        module: AuditModule,
        action: AuditAction,
        entity: str,
        entity_id: str | None = None,
        company=None,
        user=None,
        old_value: dict | None = None,
        new_value: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        activity_type: str | None = None,
        status: str = AuditStatus.SUCCESS,
        detail: dict | None = None,
    ) -> AuditLog | None:
        """Create a single audit entry; a logging failure never breaks work."""
        try:
            resolved_activity_type = activity_type or (
                AuditActivityType.MANUAL if user is not None else AuditActivityType.AUTOMATED
            )
            return AuditLog.objects.create(
                company=company,
                user=user,
                module=module,
                action=action,
                entity=entity[:100],
                entity_id=str(entity_id)[:100] if entity_id else None,
                old_value=redact_detail(old_value or {}),
                new_value=redact_detail(new_value or {}),
                ip_address=ip_address,
                user_agent=(user_agent or "")[:512] or None,
                activity_type=resolved_activity_type,
                status=status,
                detail=redact_detail(detail or {}),
            )
        except Exception:
            logger.exception(
                "Audit log write failed — module=%s action=%s entity=%s",
                module, action, entity,
            )
            return None


audit_service = AuditService()
