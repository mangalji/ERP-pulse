"""
Business logic for the Sync Manager (P1).

SyncManager orchestrates *which* entity types to sync, in what order,
and how to record the outcome — it contains zero NetSuite HTTP logic
(that stays inside netsuite/client.py) and zero business decisions
about what a "record" means (that stays inside NetSuiteDataService,
which already owns token refresh + health tracking per call). This
class's only job is sequencing + retry-of-failed-stages + persisting
SyncRun/SyncStage state via sync/repositories.py.

Scope note (see the P1 plan's "Future Improvements"): this is
manual/on-demand sync only. `SyncRun.trigger='scheduled'` exists as a
choice for forward compatibility, but nothing in this file can actually
schedule a run — that needs a task queue (Celery + Redis), which isn't
in this project yet (see requirements.txt). Wiring a scheduler onto
trigger_sync() later is additive, not a redesign of anything here.

Incremental sync: each stage only fetches records NetSuite has changed
since the connection's last successful sync (connection.last_synced_at
as the watermark), via the `lastModifiedDate` filter already supported
by NetSuite's REST Record API `params`. First-ever sync for a
connection (last_synced_at is None) has no watermark, so it pulls
everything — same as NetSuiteDataService.get_records() already does
with no filter.
"""

import logging
from accounts.models import User
from netsuite.exceptions import NetSuiteConnectionNotFoundException
from netsuite.models import NetSuiteConnection
from netsuite.repositories import NetSuiteConnectionRepository
from netsuite.services import NetSuiteDataService
from sync.exceptions import SyncAlreadyRunningException, SyncRunNotFoundException
from sync.models import SyncRun
from sync.repositories import SyncRunRepository, SyncStageRepository

logger = logging.getLogger(__name__)

# Core entity types synced by default — mirrors the NetSuiteDataService
# convenience methods (get_customers/get_employees/...) already exposed
# to the frontend's record pages. Extensible: adding a future entity
# type here (once NetSuiteRecordType supports it) is the only change
# needed — no other code in this file assumes a fixed entity list.
DEFAULT_SYNC_RECORD_TYPES = [
    'customer',
    'employee',
    'vendor',
    'salesOrder',
    'purchaseOrder',
    'invoice',
]


class SyncManager:
    def __init__(
        self,
        connection_repository: NetSuiteConnectionRepository | None = None,
        run_repository: SyncRunRepository | None = None,
        stage_repository: SyncStageRepository | None = None,
        data_service: NetSuiteDataService | None = None,
    ):
        self.connection_repository = connection_repository or NetSuiteConnectionRepository()
        self.run_repository = run_repository or SyncRunRepository()
        self.stage_repository = stage_repository or SyncStageRepository()
        self.data_service = data_service or NetSuiteDataService(repository=self.connection_repository)

    def trigger_sync(
        self, *, user: User, record_types: list[str] | None = None,
    ) -> SyncRun:
        """
        Start a new sync run for `user`'s active NetSuite connection,
        covering `record_types` (defaults to DEFAULT_SYNC_RECORD_TYPES).

        Rejects a new trigger if a run is already pending/running for
        this connection — prevents two overlapping syncs from racing
        each other's stage updates.
        """
        connection = self._require_connection(user)

        if self.run_repository.get_latest_running(connection) is not None:
            raise SyncAlreadyRunningException(
                'A sync is already in progress for this connection.'
            )

        run = self.run_repository.create(
            connection=connection,
            triggered_by=user,
            record_types=record_types or DEFAULT_SYNC_RECORD_TYPES,
        )
        self._execute(run, connection)
        return run

    def retry_failed_stages(self, *, user: User, run_id) -> SyncRun:
        """
        Re-run only the stages that failed in a previous run, instead of
        starting a whole new sync — the point of tracking per-stage
        status rather than one pass/fail flag on the run.
        """
        connection = self._require_connection(user)
        run = self.run_repository.get_by_id(connection, run_id)
        if run is None:
            raise SyncRunNotFoundException('Sync run not found.')

        failed_stages = list(self.stage_repository.failed_stages(run))
        if not failed_stages:
            return run

        self.run_repository.mark_running(run)
        for stage in failed_stages:
            self._run_stage(stage, connection)
        return self.run_repository.finish(run)

    def list_runs(self, *, user: User, limit: int = 20):
        connection = self._require_connection(user)
        return self.run_repository.list_by_connection(connection, limit=limit)

    def get_run(self, *, user: User, run_id) -> SyncRun:
        connection = self._require_connection(user)
        run = self.run_repository.get_by_id(connection, run_id)
        if run is None:
            raise SyncRunNotFoundException('Sync run not found.')
        return run

    # -----------------------------------------------------------------
    # Internal orchestration
    # -----------------------------------------------------------------

    def _execute(self, run: SyncRun, connection: NetSuiteConnection) -> None:
        self.run_repository.mark_running(run)
        for stage in run.stages.all():
            self._run_stage(stage, connection)
        self.run_repository.finish(run)

    def _run_stage(self, stage, connection: NetSuiteConnection) -> None:
        self.stage_repository.mark_running(stage)
        try:
            params = self._incremental_filter(connection)
            response = self.data_service.get_records(
                record_type=stage.record_type,
                user=connection.user,
                params=params,
            )
            records_processed = response.get('totalResults') or len(response.get('items', []))
            self.stage_repository.mark_success(stage, records_processed=records_processed)
        except Exception as exc:
            logger.warning(
                'Sync stage failed (record_type=%s, connection=%s): %s',
                stage.record_type, connection.id, exc,
            )
            self.stage_repository.mark_failed(stage, error_message=str(exc))

    @staticmethod
    def _incremental_filter(connection: NetSuiteConnection) -> dict | None:
        """
        Builds the `lastModifiedDate` filter for incremental sync, using
        the connection's last successful sync as the watermark. Returns
        None (fetch everything) for a connection's first-ever sync.

        NOTE: `lastModifiedDate` as a REST Record collection query filter
        has not been confirmed against a live NetSuite sandbox — same
        "please verify before relying on this in production" caveat
        already used elsewhere in this codebase for unverified NetSuite
        request/response shapes (see dashboard/services.py, reports/services.py).
        """
        if connection.last_synced_at is None:
            return None
        return {
            'q': f'lastModifiedDate ON_OR_AFTER "{connection.last_synced_at.strftime("%m/%d/%Y")}"',
        }

    def _require_connection(self, user: User) -> NetSuiteConnection:
        connection = self.connection_repository.get_by_user(user)
        if connection is None or not connection.is_active:
            raise NetSuiteConnectionNotFoundException(
                'No active NetSuite connection found. Please connect your NetSuite account first.'
            )
        return connection
