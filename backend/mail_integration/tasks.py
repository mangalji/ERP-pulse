"""Celery entry points for mailbox sync and automatic bill processing."""

import logging

from celery import shared_task
from django.utils import timezone

from mail_integration.pipeline import EmailBillPipeline
from mail_integration.sync import EmailSyncService
from mail_integration.health import record_scheduler_heartbeat
from mail_integration.models import EmailIntegration

logger = logging.getLogger(__name__)


def enqueue_next_mailbox_run(integration_id):
    """Queue the next user-configured run instead of polling at a fixed interval."""
    integration = EmailIntegration.objects.filter(pk=integration_id).only("next_sync_at", "is_active", "is_paused").first()
    if not integration or not integration.is_active or integration.is_paused or not integration.next_sync_at:
        return False
    run_scheduled_mailbox.apply_async(args=[str(integration_id)], eta=integration.next_sync_at)
    return True


@shared_task
def run_scheduled_mailbox(integration_id):
    """Run one mailbox at its configured next-run time."""
    integration = EmailIntegration.objects.filter(pk=integration_id).first()
    if not integration or not integration.is_active or integration.is_fetching_stopped:
        return {"skipped": True}
    if integration.next_sync_at and integration.next_sync_at > timezone.now():
        return {"skipped": True, "next_sync_at": integration.next_sync_at.isoformat()}
    try:
        staged = EmailSyncService().sync_integration(integration_id=integration_id)
        pipeline = EmailBillPipeline().process_due_messages()
        _record_mailbox_sync_summary(integration_id=integration_id, emails_fetched=staged, pipeline=pipeline)
        return {"integration_id": str(integration_id), "emails_fetched": staged, "pipeline": pipeline}
    finally:
        enqueue_next_mailbox_run(integration_id)


def _record_mailbox_sync_summary(*, integration_id, emails_fetched, pipeline):
    """Keep ``last_sync_summary`` current for the per-mailbox scheduling path.

    This is the UI's "Latest processing result" line. ``process_due_messages``
    is not scoped to one mailbox — it drains whatever is due system-wide — so
    this mailbox's own counts are read back out of its ``by_integration``
    breakdown rather than the run's totals, which can include other mailboxes.

    Failures here must never break mailbox fetching itself: this is a
    best-effort status write, logged and swallowed on error so the calling
    task still returns its real result and still re-enqueues its next run.
    """
    try:
        own_counts = (pipeline or {}).get("by_integration", {}).get(str(integration_id), {})
        now = timezone.now()
        summary = {
            "completed_at": now.isoformat(),
            "checked_at": now.isoformat(),
            "emails_fetched": emails_fetched,
            "emails_processed": own_counts.get("processed", 0),
            "vendor_bill_records_created": own_counts.get("promoted", 0),
            "emails_ignored": own_counts.get("discarded", 0),
            "emails_deferred": own_counts.get("deferred", 0),
        }
        EmailIntegration.objects.filter(pk=integration_id).update(
            last_sync_summary=summary,
            updated_at=now,
        )
    except Exception:
        logger.exception(
            "Failed to record mailbox sync summary — integration=%s", integration_id,
        )


@shared_task
def email_scheduler_heartbeat():
    """Beat dispatches this task; a worker records proof of execution."""
    record_scheduler_heartbeat()
    # This also catches connections that became unhealthy while a worker or
    # scheduler was down; no request needs to be made for the alert to resume.
    from audit.integration_alerts import check_integration_failure_alerts
    check_integration_failure_alerts()
