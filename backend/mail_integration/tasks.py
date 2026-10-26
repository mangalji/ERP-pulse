"""Celery entry points for mailbox sync and automatic bill processing."""

from celery import shared_task

from mail_integration.pipeline import EmailBillPipeline
from mail_integration.sync import EmailSyncService
from mail_integration.health import record_scheduler_heartbeat


@shared_task
def email_scheduler_heartbeat():
    """Beat dispatches this task; a worker records proof of execution."""
    record_scheduler_heartbeat()


@shared_task
def sync_due_mailboxes():
    """Stage new messages, then promote due email bills FIFO."""
    sync = EmailSyncService().sync_due_integrations()
    pipeline = EmailBillPipeline().process_due_messages()
    return {"sync": sync, "pipeline": pipeline}


@shared_task
def process_due_email_messages():
    return EmailBillPipeline().process_due_messages()
