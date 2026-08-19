"""
Celery configuration for ERP Pulse.

Uses Redis as both broker and result backend.
Auto-discovers tasks from all installed apps.
"""

import os
from celery import Celery
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
app = Celery('erp_pulse')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Run company cleanup once every 24 hours.
    """
    sender.add_periodic_task(
        timedelta(days=1),
        'tenancy.tasks.purge_expired_deleted_companies',
        name='purge companies deleted for 15+ days',
    )
    sender.add_periodic_task(
    timedelta(days=1),
    'superadmin.tasks.sync_company_subscription_statuses',
    name='sync company subscription statuses',
)