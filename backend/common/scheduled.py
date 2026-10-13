"""
Daily housekeeping jobs, runnable WITHOUT Celery beat.

Celery beat normally triggers these once a day. Hosts without beat can run
``python manage.py run_scheduled_tasks`` from any scheduler (cron, Cloud
Scheduler, Render cron, a Catalyst job ...) or simply keep a
``run_ocr_worker`` process running, which executes them daily. Both jobs are
idempotent, so running them more often than needed is harmless.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def scheduled_tasks():
    from superadmin.tasks import sync_company_subscription_statuses
    from tenancy.tasks import purge_expired_deleted_companies

    return [
        ("purge companies deleted for 15+ days", purge_expired_deleted_companies),
        ("sync company subscription statuses", sync_company_subscription_statuses),
    ]


def run_scheduled_tasks() -> dict:
    """Run every housekeeping job once; one failing job never stops the others."""
    outcome = {}

    for name, task in scheduled_tasks():
        try:
            task()  # a Celery task object runs synchronously when called
            outcome[name] = "ok"
            logger.info("Scheduled task finished — %s", name)
        except Exception:  # noqa: BLE001
            outcome[name] = "failed"
            logger.error("Scheduled task failed — %s", name, exc_info=True)

    return outcome