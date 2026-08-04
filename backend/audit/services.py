"""
Reusable AuditService — foundation only.

Provides a simple API for manually writing audit log entries.
No automatic logging is wired up yet.
"""

from audit.models import AuditAction, AuditLog, AuditModule


class AuditService:
    """Write audit log entries."""

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
    ) -> AuditLog:
        """Create a single audit log entry."""
        return AuditLog.objects.create(
            company=company,
            user=user,
            module=module,
            action=action,
            entity=entity,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )


# Module-level singleton, matching the pattern used elsewhere.
audit_service = AuditService()