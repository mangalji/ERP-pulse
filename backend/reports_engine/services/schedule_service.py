"""
ScheduleService — manage scheduled report lifecycle.

Stores schedules in the database and computes ``next_run_at`` for the
supported frequencies. The actual dispatch to Celery is handled by
``tasks.scheduled_report_task`` (driven by Celery beat / manual runs).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from reports_engine.models import ScheduleFrequency, ScheduledReport


class ScheduleService:
    """Business logic for scheduled reports."""

    def compute_next_run(self, *, schedule: ScheduledReport, from_date=None):
        """Returns the next run datetime for a schedule's frequency."""
        base = from_date or timezone.now()
        freq = schedule.frequency

        if freq == ScheduleFrequency.DAILY:
            return base + timedelta(days=1)
        if freq == ScheduleFrequency.WEEKLY:
            return base + timedelta(weeks=1)
        if freq == ScheduleFrequency.MONTHLY:
            return self._add_months(base, 1)
        if freq == ScheduleFrequency.QUARTERLY:
            return self._add_months(base, 3)
        if freq == ScheduleFrequency.YEARLY:
            return base.replace(year=base.year + 1)
        if freq == ScheduleFrequency.CRON:
            # Future-ready: cron scheduling not yet implemented.
            return base + timedelta(days=1)
        return base + timedelta(days=1)

    def activate(self, *, schedule: ScheduledReport) -> ScheduledReport:
        schedule.is_active = True
        schedule.next_run_at = self.compute_next_run(schedule=schedule)
        schedule.save(update_fields=['is_active', 'next_run_at', 'updated_at'])
        return schedule

    def deactivate(self, *, schedule: ScheduledReport) -> ScheduledReport:
        schedule.is_active = False
        schedule.save(update_fields=['is_active', 'updated_at'])
        return schedule

    def record_run(self, *, schedule: ScheduledReport) -> ScheduledReport:
        schedule.last_run_at = timezone.now()
        schedule.next_run_at = self.compute_next_run(schedule=schedule)
        schedule.save(update_fields=['last_run_at', 'next_run_at', 'updated_at'])
        return schedule

    @staticmethod
    def _add_months(dt, months: int):
        month_index = dt.month - 1 + months
        year = dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(dt.day, 28)
        return dt.replace(year=year, month=month, day=day)
