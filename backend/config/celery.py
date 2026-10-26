"""
Celery configuration for AGSuite ERP.

Uses Redis as both broker and result backend.
Auto-discovers tasks from all installed apps.
"""

import os
from celery import Celery
from datetime import timedelta

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
# app = Celery('erp_pulse')
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    debug_value = os.environ.get(
        "DJANGO_DEBUG",
        os.environ.get("DEBUG", "True")
    )
    debug = debug_value.strip().lower() in (
        "true", "1", "yes", "on"
    )
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "config.settings.local" if debug else "config.settings.production",
    )

app = Celery('erp_pulse')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Run company cleanup once every 24 hours.
    """
    # Use sender-bound task signatures instead of ``shared_task`` proxies.
    # During Django startup a proxy can resolve against a not-yet-populated
    # task registry and abort this entire signal handler.  The workers still
    # autodiscover these task modules; this only makes beat registration safe.
    sender.add_periodic_task(
        timedelta(days=1),
        sender.signature("tenancy.tasks.purge_expired_deleted_companies"),
        name='purge companies deleted for 15+ days',
    )
    sender.add_periodic_task(
        timedelta(days=1),
        sender.signature("superadmin.tasks.sync_company_subscription_statuses"),
        name='sync company subscription statuses',
    )
    # Each mailbox's selected sync interval is enforced by the task itself.
    sender.add_periodic_task(
        timedelta(minutes=5),
        sender.signature("mail_integration.tasks.sync_due_mailboxes"),
        name="sync and process due email bills",
    )
    sender.add_periodic_task(
        timedelta(seconds=20),
        sender.signature("mail_integration.tasks.email_scheduler_heartbeat"),
        name="email scheduler health heartbeat",
    )
