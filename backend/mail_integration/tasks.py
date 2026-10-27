"""Celery entry points for mailbox sync and automatic bill processing."""

from celery import shared_task
from django.utils import timezone

from mail_integration.pipeline import EmailBillPipeline
from mail_integration.sync import EmailSyncService
from mail_integration.health import record_scheduler_heartbeat
from mail_integration.models import EmailIntegration


@shared_task
def email_scheduler_heartbeat():
    """Beat dispatches this task; a worker records proof of execution."""
    record_scheduler_heartbeat()


@shared_task
def sync_due_mailboxes():
    """Stage new messages, then promote due email bills FIFO."""
    sync = EmailSyncService().sync_due_integrations()
    pipeline = EmailBillPipeline().process_due_messages()
    sync_details = sync.pop("by_integration", {})
    pipeline_details = pipeline.pop("by_integration", {})
    for integration_id in set(sync_details) | set(pipeline_details):
        fetch_result = sync_details.get(integration_id, {})
        processing_result = pipeline_details.get(integration_id, {})
        summary = {
            "completed_at": timezone.now().isoformat(),
            "checked_at": fetch_result.get("checked_at"),
            "emails_fetched": fetch_result.get("fetched", 0),
            "emails_processed": processing_result.get("processed", 0),
            "vendor_bill_records_created": processing_result.get("promoted", 0),
            "emails_ignored": processing_result.get("discarded", 0),
            "emails_deferred": processing_result.get("deferred", 0),
        }
        EmailIntegration.objects.filter(pk=integration_id).update(
            last_sync_summary=summary,
            updated_at=timezone.now(),
        )
    return {"sync": sync, "pipeline": pipeline}


@shared_task
def process_due_email_messages():
    return EmailBillPipeline().process_due_messages()
