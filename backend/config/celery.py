"""
Celery configuration for ERP Pulse.

Uses Redis as both broker and result backend.
Auto-discovers tasks from all installed apps.
"""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('erp_pulse')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Optional: Add periodic tasks here."""
    pass