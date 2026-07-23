"""
Comprehensive test suite for the netsuite app.

Covers:
- NetSuiteAuthClient (token exchange, refresh, record fetching, SuiteQL)
- NetSuiteConnectionService (OAuth flow)
- NetSuiteDataService (token refresh, record fetching)
- NetSuiteConnectionRepository
- NetSuite views (connect, callback, CRUD endpoints)
- NetSuite serializers
- NetSuite exceptions
- OAuth URL building and state signing

All external HTTP calls are mocked. No real NetSuite API calls.
"""
import requests
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings, RequestFactory
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from netsuite.client import NetSuiteAuthClient, NetSuiteTokenSet
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import (
    NetSuiteAuthorizationDeniedException,
    NetSuiteConfigurationException,
    NetSuiteConnectionNotFoundException,
    NetSuiteRecordFetchException,
    NetSuiteRecordNotFoundException,
    NetSuiteStateMismatchException,
    NetSuiteTokenExchangeException,
)
from netsuite.models import NetSuiteConnection
from netsuite.oauth import build_authorization_url, netsuite_account_domain, resolve_user_id_from_state
from netsuite.repositories import NetSuiteConnectionRepository
from netsuite.serializers import NetSuiteCallbackSerializer, NetSuiteConnectionCreateSerializer
from netsuite.services import NetSuiteConnectionService, NetSuiteDataService
from netsuite.views import (
    NetSuiteCallbackView,
    # NetSuiteConnectView,
    NetSuiteCustomerDetailView,
    NetSuiteCustomersView,
    NetSuiteEmployeeDetailView,
    NetSuiteEmployeesView,
    NetSuiteInvoicesView,
    NetSuiteInvoiceDetailView,
    NetSuiteItemDetailView,
    NetSuiteItemsView,
    NetSuitePurchaseOrderDetailView,
    NetSuitePurchaseOrderView,
    NetSuiteSalesOrderDetailView,
    NetSuiteSalesOrdersView,
    NetSuiteVendorDetailView,
    NetSuiteVendorsView,
    NetSuiteConnectionListCreateView,
    NetSuiteConnectionDetailView,
    NetSuiteConnectionSwitchView,
)


def _make_user(**overrides):
    n = _next_id()
    defaults = {
        'email': f'user{n}@example.com',
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

def _make_connection(user,**overrides):
    """
    Directly create a NetSuiteConnection row for a test, bypassing the
    repository/service layers when a test only needs a connection to
    exist rather than exercising how it's created.
    """

    defaults = {
        'client_name':'Test Connection',
        'environment':'sandbox',
        'client_id':'client-id',
        'client_secret':'client-secret',
        'netsuite_account_id': f'ACCT{_next_id()}',
        'status':'connected',
        'is_active':True,
        'access_token':'access-token',
        'refresh_token':'refresh-token',
        'access_token_expires_at': timezone.now() + timedelta(hours=1),
    }
    defaults.update(overrides)
    return NetSuiteConnection.objects.create(user=user,**defaults)

# ===================================================================
# OAuth / Client Tests
# ===================================================================

class NetSuiteAccountDomainTests(TestCase):
    def test_sandbox_account(self):
        self.assertEqual(netsuite_account_domain('1234567_SB1'), '1234567-sb1')

    def test_production_account(self):
        self.assertEqual(netsuite_account_domain('1234567'), '1234567')


class NetSuiteAuthClientTests(TestCase):
    def setUp(self):
        self._settings_override = override_settings(
            NETSUITE_REDIRECT_URI='https://example.com/callback',
        )
        self._settings_override.__enter__()

    def tearDown(self):
        self._settings_override.__exit__(None, None, None)

    def _client(self,**overrides):
        kwargs={
            'account_id':'1234567_SB1',
            'client_id':'client-id',
            'client_secret':'client-secret',
        }
        kwargs.update(overrides)
        return NetSuiteAuthClient(**kwargs)

    def test_init_success(self):
        client = self._client()
        self.assertEqual(client.account_id, '1234567_SB1')
        self.assertEqual(client._rest_base_url, 'https://1234567-sb1.suitetalk.api.netsuite.com/services/rest')

    def test_init_missing_config(self):
        # with override_settings(NETSUITE_ACCOUNT_ID=''):
        with self.assertRaises(NetSuiteConfigurationException):
            self._client(account_id='')

    def test_init_missing_redirect_uri(self):
        with override_settings(NETSUITE_REDIRECT_URI=''):
            with self.assertRaises(NetSuiteConfigurationException):
                self._client()

    @patch('netsuite.http.send')
    def test_exchange_code_for_tokens(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={
                'access_token': 'new-access',
                'refresh_token': 'new-refresh',
                'expires_in': 3600,
            }),
        )
        client = self._client()
        token_set = client.exchange_code_for_tokens(code='auth-code')
        self.assertEqual(token_set.access_token, 'new-access')
        self.assertEqual(token_set.refresh_token, 'new-refresh')

    @patch('netsuite.http.send')
    def test_refresh_access_token(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={
                'access_token': 'refreshed-access',
                'refresh_token': 'refreshed-refresh',
                'expires_in': 3600,
            }),
        )
        client = self._client()
        token_set = client.refresh_access_token(refresh_token='old-refresh')
        self.assertEqual(token_set.access_token, 'refreshed-access')
        self.assertEqual(token_set.refresh_token, 'refreshed-refresh')

    @patch('netsuite.http.send')
    def test_token_request_rejected(self,mock_post):
        mock_post.return_value = MagicMock(ok=False,status_code=400)
        client = self._client()
        with self.assertRaises(NetSuiteTokenExchangeException):
            client.exchange_code_for_tokens(code="bad-code")

    @patch('netsuite.client.requests.get')
    def test_get_records_success(self,mock_get):
        mock_get.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={'items':[],'totalResults':0}),
        )
        client = self._client(access_token='test-token')
        result = client.get_records(record_type=NetSuiteRecordType.CUSTOMER)
        self.assertEqual(result,{'items':[],'totalResults':0})

    def test_get_records_invalid_type(self):
        client = self._client()
        with self.assertRaises(ValueError):
            client.get_records(record_type='invalidType')

    @patch('netsuite.client.requests.get')
    def test_got_records_network_error(self,mock_get):
        mock_get.side_effect = requests.RequestException('NetWork error')
        client = self._client(access_token='test-token')
        with self.assertRaises(NetSuiteRecordFetchException):
            client.get_records(record_type=NetSuiteRecordType.CUSTOMER)

    @patch('netsuite.client.requests.get')
    def test_get_records_404(self, mock_get):
        mock_get.return_value = MagicMock(ok=False,status_code=404)
        client = self._client(access_token='test-token')
        with self.assertRaises(NetSuiteRecordNotFoundException):
            client.get_records(record_type=NetSuiteRecordType.CUSTOMER)

    @patch('netsuite.http.send')
    def test_execute_suiteql(self, mock_post):
        mock_post.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={'items': [{'id': 1}]}),
        )
        client = self._client(access_token='test-token')
        result = client.execute_suiteql(query='SELECT id FROM customer')
        self.assertEqual(result, {'items': [{'id': 1}]})


# ===================================================================
# OAuth URL / State Tests
# ===================================================================

class OAuthURLTests(TestCase):
    def test_build_authorization_url(self):
        with override_settings(
            NETSUITE_REDIRECT_URI='https://example.com/callback',
        ):
            url = build_authorization_url(
                user_id='user-123',
                connection_id='conn-456',
                account_id='1234567_SB1',
                client_id='client-id',
            )
            self.assertIn('https://', url)
            self.assertIn('client-id', url)
            self.assertIn('response_type=code', url)

    def test_build_authorization_url_missing_redirect_uri(self):
        with override_settings(NETSUITE_REDIRECT_URI=''):
            with self.assertRaises(NetSuiteConfigurationException):
                build_authorization_url(
                    user_id='user-123',
                    connection_id='conn-456',
                    account_id='1234567_SB1',
                    client_id='client-id',
                )

    def test_resolve_user_id_from_state_valid(self):
        with override_settings(NETSUITE_REDIRECT_URI='https://example.com/callback'):
            url = build_authorization_url(
                user_id='user-123',
                connection_id='conn-456',
                account_id='1234567_SB1',
                client_id='client-id',
            )
        from urllib.parse import urlparse, parse_qs
        state = parse_qs(urlparse(url).query)['state'][0]
 
        user_id, connection_id = resolve_user_id_from_state(state)
        self.assertEqual(user_id, 'user-123')
        self.assertEqual(connection_id, 'conn-456')

    def test_resolve_user_id_from_state_missing(self):
        with self.assertRaises(NetSuiteStateMismatchException):
            resolve_user_id_from_state('')
 
    def test_resolve_user_id_from_state_invalid(self):
        with self.assertRaises(NetSuiteStateMismatchException):
            resolve_user_id_from_state('not-a-real-signed-value')
    
    def test_resolve_user_id_from_state_malformed_payload(self):
        # Signed correctly, but payload doesn't contain "user_id:connection_id"
        from django.core import signing
        signer = signing.TimestampSigner(salt='netsuite-oauth-state')
        state = signer.sign('just-a-user-id-no-colon')
        with self.assertRaises(NetSuiteStateMismatchException):
            resolve_user_id_from_state(state)


# ===================================================================
# Repository Tests
# ===================================================================

class NetSuiteConnectionRepositoryTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.repo = NetSuiteConnectionRepository()

    def test_get_by_user_none(self):
        self.assertIsNone(self.repo.get_by_user(self.user))

    def test_get_by_user_returns_active_only(self):
        _make_connection(self.user,is_active=False,status='disconnected')
        active = _make_connection(self.user,is_active=True,status='connected')
        self.assertEqual(self.repo.get_by_user(self.user),active)

    def test_create_starts_pending_and_inactive(self):
        connection = self.repo.create(
            user=self.user,
            client_name='Acme Corp',
            environment='sandbox',
            client_id='client-id',
            client_secret='client-secret',
            netsuite_account_id='ACCT1',
        )
        self.assertEqual(connection.status, 'pending')
        self.assertFalse(connection.is_active)
        self.assertEqual(connection.client_secret, 'client-secret')

    def test_complete_oauth_activates_connection(self):
        connection = self.repo.create(
            user=self.user,
            client_name='Acme Corp',
            environment='sandbox',
            client_id='client-id',
            client_secret='client-secret',
            netsuite_account_id='ACCT1',
        )
        updated = self.repo.complete_OAuth(
            connection,
            access_token='access-1',
            refresh_token='refresh-1',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertEqual(updated.status, 'connected')
        self.assertTrue(updated.is_active)
        self.assertEqual(updated.access_token, 'access-1')

    def test_complete_oauth_deactivates_other_connections(self):
        first = self.repo.create(
            user=self.user, client_name='First', environment='sandbox',
            client_id='c1', client_secret='s1', netsuite_account_id='ACCT1',
        )
        self.repo.complete_OAuth(
            first, access_token='a1', refresh_token='r1',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
        second = self.repo.create(
            user=self.user, client_name='Second', environment='sandbox',
            client_id='c2', client_secret='s2', netsuite_account_id='ACCT2',
        )
        self.repo.complete_OAuth(
            second, access_token='a2', refresh_token='r2',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)


    def test_update_tokens(self):
        connection = _make_connection(self.user)
        updated = self.repo.update_tokens(
            connection,
            access_token='new-access',
            refresh_token='new-refresh',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertEqual(updated.access_token, 'new-access')

    def test_switch_active_connection(self):
        first = _make_connection(self.user, is_active=True)
        second = _make_connection(self.user, is_active=False)
        self.repo.switch_active_connection(self.user, second)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
 
    def test_list_by_user(self):
        _make_connection(self.user)
        _make_connection(self.user)
        other_user = _make_user()
        _make_connection(other_user)
        self.assertEqual(self.repo.list_by_user(self.user).count(), 2)

    def test_get_by_id_found(self):
        connection = _make_connection(self.user)
        found = self.repo.get_by_id(self.user, connection.id)
        self.assertEqual(found, connection)
 
    def test_get_by_id_wrong_user_returns_none(self):
        connection = _make_connection(self.user)
        other_user = _make_user()
        self.assertIsNone(self.repo.get_by_id(other_user, connection.id))
 
    def test_rename(self):
        connection = _make_connection(self.user, client_name='Old Name')
        renamed = self.repo.rename(connection, 'New Name')
        self.assertEqual(renamed.client_name, 'New Name')

    def test_delete_promotes_next_connection_if_active(self):
        active = _make_connection(self.user, is_active=True, status='connected')
        other = _make_connection(self.user, is_active=False, status='connected')
        self.repo.delete(active)
        other.refresh_from_db()
        self.assertTrue(other.is_active)
        self.assertFalse(NetSuiteConnection.objects.filter(id=active.id).exists())
 
    def test_delete_inactive_connection_does_not_touch_others(self):
        active = _make_connection(self.user, is_active=True, status='connected')
        inactive = _make_connection(self.user, is_active=False, status='connected')
        self.repo.delete(inactive)
        active.refresh_from_db()
        self.assertTrue(active.is_active)

# ===================================================================
# Service Tests
# ===================================================================

class NetSuiteConnectionServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.service = NetSuiteConnectionService()
 
    @patch('netsuite.services.build_authorization_url')
    def test_get_authorization_url(self, mock_build):
        mock_build.return_value = 'https://netsuite.com/oauth?client_id=xxx'
        connection = _make_connection(self.user)
        url = self.service.get_authorization_url(user=self.user, connection=connection)
        self.assertEqual(url, 'https://netsuite.com/oauth?client_id=xxx')
        mock_build.assert_called_once_with(
            user_id=str(self.user.id),
            connection_id=str(connection.id),
            account_id=connection.netsuite_account_id,
            client_id=connection.client_id,
        )
 
    @patch('netsuite.services.build_authorization_url')
    def test_create_connection_returns_authorization_url(self, mock_build):
        mock_build.return_value = 'https://netsuite.com/oauth?client_id=xxx'
        result = self.service.create_connection(
            user=self.user,
            client_name='Acme Corp',
            environment='sandbox',
            client_id='client-id',
            client_secret='client-secret',
            netsuite_account_id='ACCT1',
        )
        self.assertEqual(result['authorization_url'], 'https://netsuite.com/oauth?client_id=xxx')
        self.assertEqual(result['connection'].status, 'pending')
 
    def test_list_connections(self):
        _make_connection(self.user)
        _make_connection(self.user)
        self.assertEqual(len(self.service.list_connections(user=self.user)), 2)
 
    def test_rename_connection(self):
        connection = _make_connection(self.user, client_name='Old')
        renamed = self.service.rename_connection(
            user=self.user, connection_id=connection.id, client_name='New',
        )
        self.assertEqual(renamed.client_name, 'New')
 
    def test_rename_connection_not_found_raises(self):
        with self.assertRaises(NetSuiteConnectionNotFoundException):
            self.service.rename_connection(
                user=self.user, connection_id='00000000-0000-0000-0000-000000000000',
                client_name='New',
            )
 
    def test_delete_connection(self):
        connection = _make_connection(self.user)
        self.service.delete_connection(user=self.user, connection_id=connection.id)
        self.assertFalse(NetSuiteConnection.objects.filter(id=connection.id).exists())
 
    def test_delete_connection_not_found_raises(self):
        with self.assertRaises(NetSuiteConnectionNotFoundException):
            self.service.delete_connection(
                user=self.user, connection_id='00000000-0000-0000-0000-000000000000',
            )
 
    def test_switch_connection(self):
        _make_connection(self.user, is_active=True)
        target = _make_connection(self.user, is_active=False)
        switched = self.service.switch_connection(user=self.user, connection_id=target.id)
        self.assertTrue(switched.is_active)
 
    @patch('netsuite.services.NetSuiteAuthClient')
    @patch('netsuite.services.resolve_user_id_from_state')
    def test_handle_callback_success(self, mock_resolve, MockClient):
        # Build the pending connection directly via the repository so the
        # test doesn't depend on build_authorization_url succeeding too.
        connection = NetSuiteConnectionRepository().create(
            user=self.user, client_name='Acme', environment='sandbox',
            client_id='client-id', client_secret='client-secret',
            netsuite_account_id='ACCT1',
        )
        mock_resolve.return_value = (str(self.user.id), str(connection.id))
        mock_client = MockClient.return_value
        mock_client.exchange_code_for_tokens.return_value = NetSuiteTokenSet(
            access_token='access-1',
            refresh_token='refresh-1',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
 
        result_user = self.service.handle_callback(code='auth-code', state='valid-state')
        self.assertEqual(result_user, self.user)
        connection.refresh_from_db()
        self.assertEqual(connection.status, 'connected')
        self.assertTrue(connection.is_active)
 
    @patch('netsuite.services.resolve_user_id_from_state')
    def test_handle_callback_unknown_connection_raises(self, mock_resolve):
        mock_resolve.return_value = (str(self.user.id), '00000000-0000-0000-0000-000000000000')
        with self.assertRaises(NetSuiteConnectionNotFoundException):
            self.service.handle_callback(code='auth-code', state='valid-state')
 
    @patch('netsuite.services.resolve_user_id_from_state')
    def test_handle_callback_unknown_user_raises(self, mock_resolve):
        mock_resolve.return_value = ('00000000-0000-0000-0000-000000000000', 'conn-1')
        with self.assertRaises(NetSuiteStateMismatchException):
            self.service.handle_callback(code='auth-code', state='valid-state')
 
 
class NetSuiteDataServiceTests(TestCase):
    """
    NetSuiteDataService no longer takes a `client` constructor arg — it
    builds a fresh NetSuiteAuthClient per-connection internally (since
    each connection has its own account_id/client_id/client_secret), so
    NetSuiteAuthClient itself is patched at the module level instead.
    """
 
    def setUp(self):
        self.user = _make_user()
        self.mock_repo = MagicMock()
        self.service = NetSuiteDataService(repository=self.mock_repo)
 
    def _active_connection(self, **overrides):
        connection = MagicMock(
            is_active=True,
            access_token='valid-token',
            refresh_token='refresh-token',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
            netsuite_account_id='ACCT1',
            client_id='client-id',
            client_secret='client-secret',
        )
        for key, value in overrides.items():
            setattr(connection, key, value)
        return connection
 
    @patch('netsuite.services.NetSuiteAuthClient')
    def test_get_records_success(self, MockClient):
        self.mock_repo.get_by_user.return_value = self._active_connection()
        mock_client = MockClient.return_value
        mock_client.get_records.return_value = {'items': [], 'totalResults': 0}
 
        result = self.service.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=self.user)
        self.assertEqual(result, {'items': [], 'totalResults': 0})
 
    def test_get_records_no_connection(self):
        self.mock_repo.get_by_user.return_value = None
        with self.assertRaises(NetSuiteConnectionNotFoundException):
            self.service.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=self.user)
 
    def test_get_records_inactive_connection(self):
        self.mock_repo.get_by_user.return_value = self._active_connection(is_active=False)
        with self.assertRaises(NetSuiteConnectionNotFoundException):
            self.service.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=self.user)
 
    @patch('netsuite.services.NetSuiteAuthClient')
    def test_execute_suiteql(self, MockClient):
        self.mock_repo.get_by_user.return_value = self._active_connection()
        mock_client = MockClient.return_value
        mock_client.execute_suiteql.return_value = {'items': [{'id': 1}]}
 
        result = self.service.execute_suiteql(query='SELECT 1', user=self.user)
        self.assertEqual(result, {'items': [{'id': 1}]})
 
    @patch('netsuite.services.NetSuiteAuthClient')
    @patch('netsuite.token_manager.NetSuiteAuthClient')
    def test_expired_token_triggers_refresh(self, MockTokenManagerClient, MockServicesClient):
        connection = self._active_connection(
            access_token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.mock_repo.get_by_user.return_value = connection
        # NetSuiteTokenManager re-fetches the connection under a row lock
        # before refreshing — for this mocked repository, hand back the
        # same (still-expired) connection so the refresh path is taken.
        self.mock_repo.get_locked.return_value = connection
        refreshed_connection = self._active_connection(access_token='refreshed-token')
        self.mock_repo.update_tokens.return_value = refreshed_connection

        refresh_client = MockTokenManagerClient.return_value
        refresh_client.refresh_access_token.return_value = NetSuiteTokenSet(
            access_token='refreshed-token',
            refresh_token='refreshed-refresh',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )

        data_client = MockServicesClient.return_value
        data_client.get_records.return_value = {'items': [], 'totalResults': 0}

        self.service.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=self.user)
        self.mock_repo.update_tokens.assert_called_once()


# ===================================================================
# View Tests
# ===================================================================

class NetSuiteViewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = _make_user()
        self.client = APIClient()
 
    @patch('netsuite.views.NetSuiteConnectionService')
    def test_create_connection_view(self, MockService):
        mock_service = MockService.return_value
        mock_service.create_connection.return_value = {
            'connection': _make_connection(self.user, status='pending', is_active=False),
            'authorization_url': 'https://netsuite.com/oauth?...',
        }
 
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post('/api/v1/netsuite/connections/', {
            'client_name': 'Acme Corp',
            'environment': 'sandbox',
            'client_id': 'client-id',
            'client_secret': 'client-secret',
            'netsuite_account_id': 'ACCT1',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('authorization_url', response.data['data'])
 
    @patch('netsuite.views.NetSuiteConnectionService')
    def test_list_connections_view(self, MockService):
        mock_service = MockService.return_value
        mock_service.list_connections.return_value = []
 
        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/netsuite/connections/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
 
    @patch('netsuite.views.NetSuiteConnectionService')
    def test_delete_connection_view(self, MockService):
        self.client.credentials(**_auth_header(self.user))
        response = self.client.delete('/api/v1/netsuite/connections/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
 
    @patch('netsuite.views.NetSuiteConnectionService')
    def test_switch_connection_view(self, MockService):
        mock_service = MockService.return_value
        mock_service.switch_connection.return_value = _make_connection(self.user)
 
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post('/api/v1/netsuite/connections/00000000-0000-0000-0000-000000000000/switch/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
 
    @patch('netsuite.views.NetSuiteConnectionService')
    def test_callback_view_redirect(self, MockService):
        mock_service = MockService.return_value
        mock_service.handle_callback.return_value = self.user
 
        response = self.client.get('/api/v1/netsuite/callback/', {
            'code': 'auth-code',
            'state': 'valid-state',
        })
        self.assertEqual(response.status_code, 302)
 
    def test_callback_view_missing_code(self):
        response = self.client.get('/api/v1/netsuite/callback/', {
            'state': 'valid-state',
        })
        self.assertEqual(response.status_code, 400)
 
    def test_callback_view_error_param(self):
        response = self.client.get('/api/v1/netsuite/callback/', {
            'state': 'valid-state',
            'error': 'access_denied',
        })
        self.assertEqual(response.status_code, 400)
 
    @patch('netsuite.views.NetSuiteDataService')
    def test_customers_view(self, MockDataService):
        mock_ns = MockDataService.return_value
        mock_ns.get_customers.return_value = {'items': [], 'totalResults': 0}
 
        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/netsuite/customers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
 
    @patch('netsuite.views.NetSuiteDataService')
    def test_customer_detail_view(self, MockDataService):
        mock_ns = MockDataService.return_value
        mock_ns.get_record.return_value = {'id': '123', 'entityId': 'CUST-001'}
 
        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/netsuite/customers/123/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['id'], '123')
 
    @patch('netsuite.views.NetSuiteDataService')
    def test_invoices_view(self, MockDataService):
        mock_ns = MockDataService.return_value
        mock_ns.get_invoices.return_value = {'items': [], 'totalResults': 0}
 
        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/netsuite/invoices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

# ===================================================================
# Serializer Tests
# ===================================================================

class NetSuiteCallbackSerializerTests(TestCase):
    def test_valid_data(self):
        serializer = NetSuiteCallbackSerializer(data={'state': 'abc', 'code': 'code-123'})
        self.assertTrue(serializer.is_valid())
 
    def test_missing_state(self):
        serializer = NetSuiteCallbackSerializer(data={'code': 'code-123'})
        self.assertFalse(serializer.is_valid())
 
 
class NetSuiteConnectionCreateSerializerTests(TestCase):
    def test_valid_data(self):
        serializer = NetSuiteConnectionCreateSerializer(data={
            'client_name': 'Acme Corp',
            'environment': 'sandbox',
            'client_id': 'client-id',
            'client_secret': 'client-secret',
            'netsuite_account_id': 'ACCT1',
        })
        self.assertTrue(serializer.is_valid())
 
    def test_invalid_environment_rejected(self):
        serializer = NetSuiteConnectionCreateSerializer(data={
            'client_name': 'Acme Corp',
            'environment': 'staging',  # not a valid choice
            'client_id': 'client-id',
            'client_secret': 'client-secret',
            'netsuite_account_id': 'ACCT1',
        })
        self.assertFalse(serializer.is_valid())
 
    def test_missing_client_secret_rejected(self):
        serializer = NetSuiteConnectionCreateSerializer(data={
            'client_name': 'Acme Corp',
            'environment': 'sandbox',
            'client_id': 'client-id',
            'netsuite_account_id': 'ACCT1',
        })
        self.assertFalse(serializer.is_valid())

# ===================================================================
# Exception Tests
# ===================================================================

class NetSuiteExceptionTests(TestCase):
    def test_exception_status_codes(self):
        self.assertEqual(NetSuiteConfigurationException.status_code, 500)
        self.assertEqual(NetSuiteStateMismatchException.status_code, 400)
        self.assertEqual(NetSuiteAuthorizationDeniedException.status_code, 400)
        self.assertEqual(NetSuiteTokenExchangeException.status_code, 502)
        self.assertEqual(NetSuiteConnectionNotFoundException.status_code, 404)
        self.assertEqual(NetSuiteRecordFetchException.status_code, 502)
        self.assertEqual(NetSuiteRecordNotFoundException.status_code, 404)


# ===================================================================
# OAuth Integration Tests
#
# Unlike the unit tests above (which mock the Service or the Client),
# these drive a real request through URL -> View -> Serializer ->
# Service -> Repository -> DB, with only the outermost HTTP boundary
# (requests.post, inside client.py) mocked. This is what actually proves
# the callback endpoint works end-to-end, not just that each layer's
# unit behaves correctly in isolation.
# ===================================================================

@override_settings(NETSUITE_REDIRECT_URI='https://example.com/callback')
class NetSuiteOAuthIntegrationTests(APITestCase):
    def setUp(self):
        from netsuite.oauth import _state_signer

        self.user = _make_user()
        self.connection = NetSuiteConnection.objects.create(
            user=self.user,
            client_name='Acme Corp',
            environment='sandbox',
            client_id='client-id',
            client_secret='client-secret',
            netsuite_account_id='ACCT1',
            status='pending',
            is_active=False,
        )
        self.state = _state_signer.sign(f'{self.user.id}:{self.connection.id}')

    def _mock_token_response(self, **overrides):
        payload = {
            'access_token': 'exchanged-access-token',
            'refresh_token': 'exchanged-refresh-token',
            'expires_in': 3600,
        }
        payload.update(overrides)
        response = MagicMock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = payload
        return response

    @patch('netsuite.http.send')
    def test_callback_persists_connection_end_to_end(self, mock_post):
        mock_post.return_value = self._mock_token_response()

        response = self.client.get(
            '/api/v1/netsuite/callback/',
            {'code': 'auth-code-123', 'state': self.state},
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('/settings?netsuite=connected', response['Location'])

        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, 'connected')
        self.assertTrue(self.connection.is_active)
        self.assertEqual(self.connection.access_token, 'exchanged-access-token')
        self.assertEqual(self.connection.refresh_token, 'exchanged-refresh-token')
        self.assertIsNotNone(self.connection.access_token_expires_at)

    @patch('netsuite.http.send')
    def test_callback_deactivates_other_connections_end_to_end(self, mock_post):
        other_connection = _make_connection(self.user, is_active=True, status='connected')
        mock_post.return_value = self._mock_token_response()

        self.client.get(
            '/api/v1/netsuite/callback/',
            {'code': 'auth-code-123', 'state': self.state},
        )

        self.connection.refresh_from_db()
        other_connection.refresh_from_db()
        self.assertTrue(self.connection.is_active)
        self.assertFalse(other_connection.is_active)

    def test_callback_invalid_state_does_not_touch_db(self):
        response = self.client.get(
            '/api/v1/netsuite/callback/',
            {'code': 'auth-code-123', 'state': 'tampered-state-value'},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, 'pending')

    def test_callback_denied_authorization_returns_400(self):
        response = self.client.get(
            '/api/v1/netsuite/callback/',
            {'error': 'access_denied', 'state': self.state},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, 'pending')

    @patch('netsuite.http.send')
    def test_callback_netsuite_rejection_returns_502(self, mock_post):
        rejected_response = MagicMock()
        rejected_response.ok = False
        rejected_response.status_code = 400
        mock_post.return_value = rejected_response

        response = self.client.get(
            '/api/v1/netsuite/callback/',
            {'code': 'auth-code-123', 'state': self.state},
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, 'pending')


# ===================================================================
# NetSuiteTokenManager Tests
# ===================================================================

class NetSuiteTokenManagerTests(TestCase):
    def setUp(self):
        from netsuite.token_manager import NetSuiteTokenManager

        self.user = _make_user()
        self.mock_repo = MagicMock()
        self.manager = NetSuiteTokenManager(repository=self.mock_repo)

    def _connection(self, **overrides):
        connection = MagicMock(
            id=1,
            user_id=self.user.id,
            access_token='current-token',
            refresh_token='current-refresh',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
            netsuite_account_id='ACCT1',
            client_id='client-id',
            client_secret='client-secret',
        )
        for key, value in overrides.items():
            setattr(connection, key, value)
        return connection

    def test_returns_existing_token_without_refresh_when_valid(self):
        connection = self._connection()
        token = self.manager.get_valid_access_token(connection)

        self.assertEqual(token, 'current-token')
        self.mock_repo.get_locked.assert_not_called()

    @patch('netsuite.token_manager.NetSuiteAuthClient')
    def test_refreshes_when_expired(self, MockClient):
        connection = self._connection(
            access_token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.mock_repo.get_locked.return_value = connection
        self.mock_repo.update_tokens.return_value = self._connection(access_token='new-token')

        mock_client = MockClient.return_value
        mock_client.refresh_access_token.return_value = NetSuiteTokenSet(
            access_token='new-token',
            refresh_token='new-refresh',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )

        token = self.manager.get_valid_access_token(connection)

        self.assertEqual(token, 'new-token')
        mock_client.refresh_access_token.assert_called_once_with(refresh_token='current-refresh')
        self.mock_repo.update_tokens.assert_called_once()

    @patch('netsuite.token_manager.NetSuiteAuthClient')
    def test_does_not_refresh_if_already_refreshed_under_lock(self, MockClient):
        """
        Simulates the concurrency case the lock exists for: by the time
        this caller acquires the row lock, another request already
        refreshed the token — get_locked() returns a connection whose
        token is valid again, so no second NetSuite call should happen.
        """
        connection = self._connection(
            access_token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        already_refreshed = self._connection(
            access_token='refreshed-by-another-request',
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.mock_repo.get_locked.return_value = already_refreshed

        token = self.manager.get_valid_access_token(connection)

        self.assertEqual(token, 'refreshed-by-another-request')
        MockClient.return_value.refresh_access_token.assert_not_called()
        self.mock_repo.update_tokens.assert_not_called()

    @patch('netsuite.token_manager.NetSuiteAuthClient')
    def test_refresh_failure_records_sync_failure_and_reraises(self, MockClient):
        connection = self._connection(
            access_token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.mock_repo.get_locked.return_value = connection
        MockClient.return_value.refresh_access_token.side_effect = NetSuiteTokenExchangeException(
            'refresh failed'
        )

        with self.assertRaises(NetSuiteTokenExchangeException):
            self.manager.get_valid_access_token(connection)

        self.mock_repo.record_sync_failure.assert_called_once()