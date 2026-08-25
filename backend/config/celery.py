"""
Celery configuration for AGSuite ERP.

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
    # Import the task objects lazily (after Django is ready) and pass real
    # signatures. Celery 5.x requires a CallableSignature here; passing a
    # plain string name previously raised ``'str' object has no attribute
    # 'name'`` inside ``add_periodic_task``. The periodic behavior (task,
    # schedule, name) is unchanged.
    from tenancy.tasks import purge_expired_deleted_companies
    from superadmin.tasks import sync_company_subscription_statuses

    sender.add_periodic_task(
        timedelta(days=1),
        purge_expired_deleted_companies.s(),
        name='purge companies deleted for 15+ days',
    )
    sender.add_periodic_task(
        timedelta(days=1),
        sync_company_subscription_statuses.s(),
        name='sync company subscription statuses',
    )