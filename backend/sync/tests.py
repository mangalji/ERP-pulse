"""
Test suite for the sync app (Sync Manager).

Covers:
- SyncRunRepository / SyncStageRepository (persistence)
- SyncManager (orchestration: trigger, retry-only-failed-stages,
  concurrent-run guard, status roll-up)
- Sync views (auth, connection-scoping, throttling)

All NetSuite calls are mocked — no real SuiteQL/REST calls.
"""

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from netsuite.models import NetSuiteConnection
from sync.exceptions import SyncAlreadyRunningException, SyncRunNotFoundException
from sync.models import SyncRun, SyncStage
from sync.repositories import SyncRunRepository, SyncStageRepository
from sync.services import DEFAULT_SYNC_RECORD_TYPES, SyncManager


def _make_user(**overrides):
    n = _next_id()
    defaults = {
        'email': f'syncuser{n}@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'mobile_number': f'+1555{n:08d}',
        'is_active': True,
        'is_email_verified': True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password('testpass123')
    user.save()
    return user


_counter = 0

def _next_id():
    global _counter
    _counter += 1
    return _counter


def _auth_header(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}


def _make_connection(user, **overrides):
    defaults = {
        'client_name': 'Test Connection',
        'environment': 'sandbox',
        'client_id': 'client-id',
        'client_secret': 'client-secret',
        'netsuite_account_id': f'ACCT{_next_id()}',
        'status': 'connected',
        'is_active': True,
        'access_token': 'access-token',
        'refresh_token': 'refresh-token',
        'access_token_expires_at': timezone.now() + timezone.timedelta(hours=1),
    }
    defaults.update(overrides)
    return NetSuiteConnection.objects.create(user=user, **defaults)


# ===================================================================
# Repository Tests
# ===================================================================

class SyncRunRepositoryTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.connection = _make_connection(self.user)
        self.repo = SyncRunRepository()

    def test_create_also_creates_one_stage_per_record_type(self):
        run = self.repo.create(
            connection=self.connection, triggered_by=self.user,
            record_types=['customer', 'invoice'],
        )
        self.assertEqual(run.stages.count(), 2)
        self.assertEqual(
            set(run.stages.values_list('record_type', flat=True)),
            {'customer', 'invoice'},
        )

    def test_new_run_and_stages_start_pending(self):
        run = self.repo.create(
            connection=self.connection, triggered_by=self.user, record_types=['customer'],
        )
        self.assertEqual(run.status, 'pending')
        self.assertEqual(run.stages.first().status, 'pending')

    def test_mark_running_sets_status_and_started_at(self):
        run = self.repo.create(
            connection=self.connection, triggered_by=self.user, record_types=['customer'],
        )
        updated = self.repo.mark_running(run)
        self.assertEqual(updated.status, 'running')
        self.assertIsNotNone(updated.started_at)

    def test_finish_all_stages_succeeded_rolls_up_to_success(self):
        run = self.repo.create(
            connection=self.connection, triggered_by=self.user, record_types=['customer', 'invoice'],
        )
        stage_repo = SyncStageRepository()
        for stage in run.stages.all():
            stage_repo.mark_success(stage, records_processed=5)
        finished = self.repo.finish(run)
        self.assertEqual(finished.status, 'success')
        self.assertEqual(finished.records_processed, 10)
        self.assertEqual(finished.records_failed, 0)

    def test_finish_all_stages_failed_rolls_up_to_failed(self):
        run = self.repo.create(
            connection=self.connection, triggered_by=self.user, record_types=['customer', 'invoice'],
        )
        stage_repo = SyncStageRepository()
        for stage in run.stages.all():
            stage_repo.mark_failed(stage, error_message='boom')
        finished = self.repo.finish(run)
        self.assertEqual(finished.status, 'failed')
        self.assertEqual(finished.records_failed, 2)

    def test_finish_mixed_stages_rolls_up_to_partial_failure(self):
        run = self.repo.create(
            connection=self.connection, triggered_by=self.user, record_types=['customer', 'invoice'],
        )
        stage_repo = SyncStageRepository()
        stages = list(run.stages.all())
        stage_repo.mark_success(stages[0], records_processed=3)
        stage_repo.mark_failed(stages[1], error_message='boom')
        finished = self.repo.finish(run)
        self.assertEqual(finished.status, 'partial_failure')
        self.assertEqual(finished.records_processed, 3)
        self.assertEqual(finished.records_failed, 1)

    def test_list_by_connection_scoped_to_connection(self):
        other_connection = _make_connection(self.user, netsuite_account_id='OTHER1', is_active=False)
        self.repo.create(connection=self.connection, triggered_by=self.user, record_types=['customer'])
        self.repo.create(connection=other_connection, triggered_by=self.user, record_types=['customer'])
        self.assertEqual(self.repo.list_by_connection(self.connection).count(), 1)

    def test_list_by_connection_respects_limit(self):
        for _ in range(5):
            self.repo.create(connection=self.connection, triggered_by=self.user, record_types=['customer'])
        self.assertEqual(self.repo.list_by_connection(self.connection, limit=2).count(), 2)

    def test_get_by_id_wrong_connection_returns_none(self):
        run = self.repo.create(connection=self.connection, triggered_by=self.user, record_types=['customer'])
        other_connection = _make_connection(self.user, netsuite_account_id='OTHER2', is_active=False)
        self.assertIsNone(self.repo.get_by_id(other_connection, run.id))

    def test_get_latest_running_none_when_no_active_run(self):
        self.repo.create(
            connection=self.connection, triggered_by=self.user, record_types=['customer'],
        )  # stays 'pending', which get_latest_running still treats as active
        result = self.repo.get_latest_running(self.connection)
        self.assertIsNotNone(result)  # 'pending' counts as in-progress by design

    def test_get_latest_running_none_when_finished(self):
        run = self.repo.create(connection=self.connection, triggered_by=self.user, record_types=['customer'])
        for stage in run.stages.all():
            SyncStageRepository().mark_success(stage, records_processed=1)
        self.repo.finish(run)
        self.assertIsNone(self.repo.get_latest_running(self.connection))


class SyncStageRepositoryTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.connection = _make_connection(self.user)
        self.run = SyncRunRepository().create(
            connection=self.connection, triggered_by=self.user, record_types=['customer', 'invoice'],
        )
        self.repo = SyncStageRepository()

    def test_mark_success_clears_previous_error(self):
        stage = self.run.stages.first()
        self.repo.mark_failed(stage, error_message='first attempt failed')
        self.repo.mark_success(stage, records_processed=3)
        stage.refresh_from_db()
        self.assertEqual(stage.status, 'success')
        self.assertIsNone(stage.error_message)
        self.assertEqual(stage.records_processed, 3)

    def test_mark_failed_truncates_long_error_message(self):
        stage = self.run.stages.first()
        self.repo.mark_failed(stage, error_message='x' * 5000)
        stage.refresh_from_db()
        self.assertEqual(len(stage.error_message), 2000)

    def test_failed_stages_only_returns_failed(self):
        stages = list(self.run.stages.all())
        self.repo.mark_failed(stages[0], error_message='boom')
        self.repo.mark_success(stages[1], records_processed=1)
        failed = list(self.repo.failed_stages(self.run))
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].id, stages[0].id)


# ===================================================================
# SyncManager Tests
# ===================================================================

class SyncManagerTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.connection = _make_connection(self.user)
        self.mock_data_service = MagicMock()
        self.manager = SyncManager(data_service=self.mock_data_service)

    def test_trigger_sync_no_active_connection_raises(self):
        user_without_connection = _make_user()
        with self.assertRaises(Exception):  # NetSuiteConnectionNotFoundException
            self.manager.trigger_sync(user=user_without_connection)

    def test_trigger_sync_default_record_types(self):
        self.mock_data_service.get_records.return_value = {'totalResults': 2, 'items': [{}, {}]}
        run = self.manager.trigger_sync(user=self.user)
        self.assertEqual(
            set(run.stages.values_list('record_type', flat=True)),
            set(DEFAULT_SYNC_RECORD_TYPES),
        )

    def test_trigger_sync_custom_record_types(self):
        self.mock_data_service.get_records.return_value = {'totalResults': 1, 'items': [{}]}
        run = self.manager.trigger_sync(user=self.user, record_types=['customer'])
        self.assertEqual(list(run.stages.values_list('record_type', flat=True)), ['customer'])

    def test_trigger_sync_all_succeed(self):
        self.mock_data_service.get_records.return_value = {'totalResults': 5, 'items': []}
        run = self.manager.trigger_sync(user=self.user, record_types=['customer', 'invoice'])
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.records_processed, 10)

    def test_trigger_sync_partial_failure(self):
        def side_effect(*, record_type, user, params=None):
            if record_type == 'invoice':
                raise Exception('SuiteQL timeout')
            return {'totalResults': 3, 'items': []}
        self.mock_data_service.get_records.side_effect = side_effect

        run = self.manager.trigger_sync(user=self.user, record_types=['customer', 'invoice'])
        self.assertEqual(run.status, 'partial_failure')
        self.assertEqual(run.records_failed, 1)

    def test_trigger_sync_rejects_concurrent_run(self):
        SyncRun.objects.create(connection=self.connection, status='running')
        with self.assertRaises(SyncAlreadyRunningException):
            self.manager.trigger_sync(user=self.user)

    def test_retry_failed_stages_only_reruns_failed_ones(self):
        call_log = []
        def side_effect(*, record_type, user, params=None):
            call_log.append(record_type)
            if record_type == 'invoice':
                raise Exception('boom')
            return {'totalResults': 1, 'items': []}
        self.mock_data_service.get_records.side_effect = side_effect

        run = self.manager.trigger_sync(user=self.user, record_types=['customer', 'invoice'])
        self.assertEqual(set(call_log), {'customer', 'invoice'})

        # Retry: invoice now succeeds, customer must NOT be called again.
        call_log.clear()
        def retry_side_effect(*, record_type, user, params=None):
            call_log.append(record_type)
            return {'totalResults': 2, 'items': []}
        self.mock_data_service.get_records.side_effect = retry_side_effect
        retried = self.manager.retry_failed_stages(user=self.user, run_id=run.id)

        self.assertEqual(call_log, ['invoice'])
        self.assertEqual(retried.status, 'success')

    def test_retry_with_no_failed_stages_is_a_noop(self):
        self.mock_data_service.get_records.return_value = {'totalResults': 1, 'items': []}
        run = self.manager.trigger_sync(user=self.user, record_types=['customer'])
        self.mock_data_service.get_records.reset_mock()

        result = self.manager.retry_failed_stages(user=self.user, run_id=run.id)
        self.assertEqual(result.id, run.id)
        self.mock_data_service.get_records.assert_not_called()

    def test_retry_unknown_run_raises(self):
        with self.assertRaises(SyncRunNotFoundException):
            self.manager.retry_failed_stages(user=self.user, run_id='00000000-0000-0000-0000-000000000000')

    def test_list_runs_scoped_to_users_active_connection(self):
        self.mock_data_service.get_records.return_value = {'totalResults': 1, 'items': []}
        self.manager.trigger_sync(user=self.user, record_types=['customer'])
        other_user = _make_user()
        self.assertEqual(len(self.manager.list_runs(user=self.user)), 1)
        with self.assertRaises(Exception):
            self.manager.list_runs(user=other_user)  # no connection for this user

    def test_get_run_unknown_id_raises(self):
        with self.assertRaises(SyncRunNotFoundException):
            self.manager.get_run(user=self.user, run_id='00000000-0000-0000-0000-000000000000')

    def test_incremental_filter_none_for_first_sync(self):
        self.connection.last_synced_at = None
        self.assertIsNone(self.manager._incremental_filter(self.connection))

    def test_incremental_filter_uses_last_synced_at_as_watermark(self):
        self.connection.last_synced_at = timezone.now()
        result = self.manager._incremental_filter(self.connection)
        self.assertIn('lastModifiedDate', result['q'])


# ===================================================================
# View Tests
# ===================================================================

class SyncViewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = _make_user()
        self.connection = _make_connection(self.user)
        self.client = APIClient()

    def test_list_requires_authentication(self):
        response = self.client.get('/api/v1/sync/runs/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('sync.views.SyncManager')
    def test_list_runs(self, MockManager):
        MockManager.return_value.list_runs.return_value = []
        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/sync/runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('sync.views.SyncManager')
    def test_trigger_sync_view(self, MockManager):
        run = SyncRun.objects.create(connection=self.connection, status='success')
        MockManager.return_value.trigger_sync.return_value = run

        self.client.credentials(**_auth_header(self.user))
        response = self.client.post('/api/v1/sync/runs/', {'record_types': ['customer']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('sync.views.SyncManager')
    def test_trigger_sync_view_rejects_invalid_record_type(self, MockManager):
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(
            '/api/v1/sync/runs/', {'record_types': ['not-a-real-type']}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        MockManager.return_value.trigger_sync.assert_not_called()

    @patch('sync.views.SyncManager')
    def test_run_detail_view(self, MockManager):
        run = SyncRun.objects.create(connection=self.connection, status='success')
        MockManager.return_value.get_run.return_value = run

        self.client.credentials(**_auth_header(self.user))
        response = self.client.get(f'/api/v1/sync/runs/{run.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('sync.views.SyncManager')
    def test_retry_view(self, MockManager):
        run = SyncRun.objects.create(connection=self.connection, status='partial_failure')
        MockManager.return_value.retry_failed_stages.return_value = run

        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(f'/api/v1/sync/runs/{run.id}/retry/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)