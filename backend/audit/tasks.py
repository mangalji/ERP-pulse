"""Retention jobs for operational audit events."""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from audit.models import AuditActivityType, AuditLog, Notification


logger = logging.getLogger(__name__)


@shared_task
def purge_expired_operational_audit_logs():
    """Delete routine automated diagnostics after 30 days.

    Manual security and business audit evidence remains available. The result
    is written to server logs only, preventing recursive audit events.
    """
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = AuditLog.objects.filter(
        activity_type=AuditActivityType.AUTOMATED,
        created_at__lt=cutoff,
    ).delete()
    logger.info("Purged expired automated audit logs — deleted=%s cutoff=%s", deleted, cutoff.isoformat())
    return {"deleted": deleted, "cutoff": cutoff.isoformat()}


@shared_task
def purge_expired_notifications():
    """Fallback cleanup for delayed tasks missed during worker downtime."""
    deleted, _ = Notification.objects.filter(
        delete_after__isnull=False,
        delete_after__lte=timezone.now(),
    ).delete()
    return {"deleted": deleted}


@shared_task
def purge_notification_after_undo(notification_id):
    """Permanently delete one notification after its undo window."""
    now = timezone.now()
    deleted, _ = Notification.objects.filter(
        pk=notification_id,
        deleted_at__isnull=False,
        delete_after__isnull=False,
        delete_after__lte=now,
    ).delete()
    return {"deleted": deleted, "notification_id": str(notification_id)}
