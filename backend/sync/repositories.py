"""
Persistence-only operations for SyncRun/SyncStage.

No orchestration logic here (which stages to run, retry decisions) —
that's SyncManager's job (services.py). This class only reads from and
writes to the database, matching the layering used throughout the
project (netsuite/repositories.py, accounts/repositories.py, ...).
"""

from django.utils import timezone

from netsuite.models import NetSuiteConnection
from sync.models import SyncRun, SyncStage


class SyncRunRepository:
    def create(self, *, connection: NetSuiteConnection, triggered_by, record_types: list[str]) -> SyncRun:
        run = SyncRun.objects.create(connection=connection, triggered_by=triggered_by)
        SyncStage.objects.bulk_create([
            SyncStage(run=run, record_type=record_type) for record_type in record_types
        ])
        return run

    def mark_running(self, run: SyncRun) -> SyncRun:
        run.status = 'running'
        run.started_at = timezone.now()
        run.save(update_fields=['status', 'started_at'])
        return run

    def finish(self, run: SyncRun) -> SyncRun:
        """
        Rolls the run's overall status up from its stages: all succeeded
        -> success, all failed -> failed, mixed -> partial_failure.
        """
        stage_statuses = set(run.stages.values_list('status', flat=True))

        if stage_statuses == {'success'}:
            run.status = 'success'
        elif stage_statuses == {'failed'}:
            run.status = 'failed'
        else:
            run.status = 'partial_failure'

        run.records_processed = sum(run.stages.values_list('records_processed', flat=True))
        run.records_failed = run.stages.filter(status='failed').count()
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'records_processed', 'records_failed', 'finished_at'])
        return run

    def list_by_connection(self, connection: NetSuiteConnection, *, limit: int = 20):
        return SyncRun.objects.filter(connection=connection)[:limit]

    def get_by_id(self, connection: NetSuiteConnection, run_id) -> SyncRun | None:
        return SyncRun.objects.filter(connection=connection, id=run_id).first()

    def get_latest_running(self, connection: NetSuiteConnection) -> SyncRun | None:
        """Used to reject a new sync trigger while one is already in progress."""
        return SyncRun.objects.filter(connection=connection, status__in=['pending', 'running']).first()


class SyncStageRepository:
    def mark_running(self, stage: SyncStage) -> SyncStage:
        stage.status = 'running'
        stage.started_at = timezone.now()
        stage.save(update_fields=['status', 'started_at'])
        return stage

    def mark_success(self, stage: SyncStage, *, records_processed: int) -> SyncStage:
        stage.status = 'success'
        stage.records_processed = records_processed
        stage.error_message = None
        stage.finished_at = timezone.now()
        stage.save(update_fields=['status', 'records_processed', 'error_message', 'finished_at'])
        return stage

    def mark_failed(self, stage: SyncStage, *, error_message: str) -> SyncStage:
        stage.status = 'failed'
        stage.error_message = error_message[:2000]
        stage.finished_at = timezone.now()
        stage.save(update_fields=['status', 'error_message', 'finished_at'])
        return stage

    def failed_stages(self, run: SyncRun):
        return run.stages.filter(status='failed')
