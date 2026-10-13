"""
Run the daily housekeeping jobs once (what Celery beat would run).

    python manage.py run_scheduled_tasks

Safe to call from any scheduler; the jobs are idempotent.
"""

from django.core.management.base import BaseCommand

from common.scheduled import run_scheduled_tasks


class Command(BaseCommand):
    help = "Run the daily housekeeping jobs once (no Celery beat required)."

    def handle(self, *args, **options):
        outcome = run_scheduled_tasks()
        for name, state in outcome.items():
            self.stdout.write(f"{state:>6}  {name}")