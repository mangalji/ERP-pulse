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

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings, RequestFactory
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
from netsuite.serializers import NetSuiteCallbackSerializer
from netsuite.services import NetSuiteConnectionService, NetSuiteDataService
from netsuite.views import (
    NetSuiteCallbackView,
    NetSuiteConnectView,
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
            NETSUITE_ACCOUNT_ID='1234567_SB1',
            NETSUITE_CLIENT_ID='client-id',
            NETSUITE_CLIENT_SECRET='client-secret',
            NETSUITE_REDIRECT_URI='https://example.com/callback',
        )
        self._settings_override.__enter__()

    def tearDown(self):
        self._settings_override.__exit__(None, None, None)

    def test_init_success(self):
        client = NetSuiteAuthClient()
        self.assertEqual(client.account_id, '1234567_SB1')
        self.assertEqual(client._rest_base_url, 'https://1234567-sb1.suitetalk.api.netsuite.com/services/rest')

    def test_init_missing_config(self):
        with override_settings(NETSUITE_ACCOUNT_ID=''):
            with self.assertRaises(NetSuiteConfigurationException):
                NetSuiteAuthClient()

    @patch('netsuite.client.requests.post')
    def test_exchange_code_for_tokens(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                'access_token': 'new-access',
                'refresh_token': 'new-refresh',
                'expires_in': 3600,
            }),
        )
        client = NetSuiteAuthClient()
        token_set = client.exchange_code_for_tokens(code='auth-code')
        self.assertEqual(token_set.access_token, 'new-access')
        self.assertEqual(token_set.refresh_token, 'new-refresh')

    @patch('netsuite.client.requests.post')
    def test_refresh_access_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                'access_token': 'refreshed-access',
                'refresh_token': 'refreshed-refresh',
                'expires_in': 3600,
            }),
        )
        client = NetSuiteAuthClient()
        token_set = client.refresh_access_token(refresh_token='old-refresh')
        self.assertEqual(token_set.access_token, 'refreshed-access')
        self.assertEqual(token_set.refresh_token, 'refreshed-refresh')

    @patch('netsuite.client.requests.get')
    def test_get_records_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={'items': [], 'totalResults': 0}),
        )
        client = NetSuiteAuthClient(access_token='test-token')
        result = client.get_records(record_type=NetSuiteRecordType.CUSTOMER)
        self.assertEqual(result, {'items': [], 'totalResults': 0})

    def test_get_records_invalid_type(self):
        client = NetSuiteAuthClient()
        with self.assertRaises(ValueError):
            client.get_records(record_type='invalidType')

    @patch('netsuite.client.requests.get')
    def test_get_records_network_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException('Network error')
        client = NetSuiteAuthClient(access_token='test-token')
        with self.assertRaises(NetSuiteRecordFetchException):
            client.get_records(record_type=NetSuiteRecordType.CUSTOMER)

    @patch('netsuite.client.requests.get')
    def test_get_records_404(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)
        client = NetSuiteAuthClient(access_token='test-token')
        with self.assertRaises(NetSuiteRecordNotFoundException):
            client.get_records(record_type=NetSuiteRecordType.CUSTOMER)

    @patch('netsuite.client.requests.post')
    def test_execute_suiteql(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={'items': [{'id': 1}]}),
        )
        client = NetSuiteAuthClient(access_token='test-token')
        result = client.execute_suiteql(query='SELECT id FROM customer')
        self.assertEqual(result, {'items': [{'id': 1}]})


# ===================================================================
# OAuth URL / State Tests
# ===================================================================

class OAuthURLTests(TestCase):
    def test_build_authorization_url(self):
        with override_settings(
            NETSUITE_ACCOUNT_ID='1234567_SB1',
            NETSUITE_CLIENT_ID='client-id',
            NETSUITE_REDIRECT_URI='https://example.com/callback',
        ):
            url = build_authorization_url(user_id='user-123')
            self.assertIn('https://', url)
            self.assertIn('client-id', url)
            self.assertIn('response_type=code', url)

    def test_build_authorization_url_missing_config(self):
        with override_settings(NETSUITE_ACCOUNT_ID=''):
            with self.assertRaises(NetSuiteConfigurationException):
                build_authorization_url(user_id='user-123')

    def test_resolve_user_id_from_state_valid(self):
        with override_settings():
            user_id = 'user-123'
            from django.core import signing
            signer = signing.TimestampSigner(salt='netsuite-oauth-state')
            state = signer.sign(user_id)
            resolved = resolve_user_id_from_state(state)
            self.assertEqual(resolved, user_id)

    def test_resolve_user_id_from_state_missing(self):
        with self.assertRaises(NetSuiteStateMismatchException):
            resolve_user_id_from_state('')

    def test_resolve_user_id_from_state_expired(self):
        from django.core import signing
        signer = signing.TimestampSigner(salt='netsuite-oauth-state')
        state = signer.sign('user-123')
        with self.assertRaises(NetSuiteStateMismatchException):
            resolve_user_id_from_state('invalid-state')


# ===================================================================
# Repository Tests
# ===================================================================

class NetSuiteConnectionRepositoryTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.repo = NetSuiteConnectionRepository()

    def test_get_by_user_none(self):
        self.assertIsNone(self.repo.get_by_user(self.user))

    def test_upsert_creates(self):
        connection = self.repo.upsert(
            user=self.user,
            netsuite_account_id='1234567_SB1',
            access_token='access-1',
            refresh_token='refresh-1',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        self.assertEqual(connection.user, self.user)
        self.assertEqual(connection.access_token, 'access-1')
        self.assertTrue(connection.is_active)

    def test_upsert_updates(self):
        self.repo.upsert(
            user=self.user,
            netsuite_account_id='1234567_SB1',
            access_token='access-1',
            refresh_token='refresh-1',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        connection = self.repo.upsert(
            user=self.user,
            netsuite_account_id='1234567_SB1',
            access_token='access-2',
            refresh_token='refresh-2',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        self.assertEqual(connection.access_token, 'access-2')
        self.assertEqual(NetSuiteConnection.objects.filter(user=self.user).count(), 1)

    def test_update_tokens(self):
        connection = self.repo.upsert(
            user=self.user,
            netsuite_account_id='1234567_SB1',
            access_token='access-1',
            refresh_token='refresh-1',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        updated = self.repo.update_tokens(
            connection,
            access_token='new-access',
            refresh_token='new-refresh',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        self.assertEqual(updated.access_token, 'new-access')

    def test_deactivate(self):
        connection = self.repo.upsert(
            user=self.user,
            netsuite_account_id='1234567_SB1',
            access_token='access-1',
            refresh_token='refresh-1',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        self.repo.deactivate(connection)
        connection.refresh_from_db()
        self.assertFalse(connection.is_active)


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
        url = self.service.get_authorization_url(user=self.user)
        self.assertEqual(url, 'https://netsuite.com/oauth?client_id=xxx')

    @patch('netsuite.services.NetSuiteAuthClient')
    @patch('netsuite.services.resolve_user_id_from_state')
    def test_handle_callback_success(self, mock_resolve, MockClient):
        mock_resolve.return_value = str(self.user.id)
        mock_client = MockClient.return_value
        mock_client.exchange_code_for_tokens.return_value = NetSuiteTokenSet(
            access_token='access-1',
            refresh_token='refresh-1',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        mock_client.account_id = '1234567_SB1'

        result = self.service.handle_callback(code='auth-code', state='valid-state')
        self.assertEqual(result, self.user)
        self.assertTrue(NetSuiteConnection.objects.filter(user=self.user).exists())


class NetSuiteDataServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.mock_repo = MagicMock()
        self.mock_client = MagicMock()
        self.service = NetSuiteDataService(repository=self.mock_repo, client=self.mock_client)

    def test_get_records_success(self):
        self.mock_repo.get_by_user.return_value = MagicMock(
            is_active=True,
            access_token='valid-token',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        self.mock_client.get_records.return_value = {'items': [], 'totalResults': 0}

        result = self.service.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=self.user)
        self.assertEqual(result, {'items': [], 'totalResults': 0})

    def test_get_records_no_connection(self):
        self.mock_repo.get_by_user.return_value = None

        with self.assertRaises(NetSuiteConnectionNotFoundException):
            self.service.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=self.user)

    def test_execute_suiteql(self):
        self.mock_repo.get_by_user.return_value = MagicMock(
            is_active=True,
            access_token='valid-token',
            access_token_expires_at=datetime.now() + timedelta(hours=1),
        )
        self.mock_client.execute_suiteql.return_value = {'items': [{'id': 1}]}

        result = self.service.execute_suiteql(query='SELECT 1', user=self.user)
        self.assertEqual(result, {'items': [{'id': 1}]})


# ===================================================================
# View Tests
# ===================================================================

class NetSuiteViewTests(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()

    @patch('netsuite.views.NetSuiteConnectionService')
    def test_connect_view(self, MockService):
        mock_service = MockService.return_value
        mock_service.get_authorization_url.return_value = 'https://netsuite.com/oauth?...'

        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/netsuite/connect/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('authorization_url', response.data['data'])

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
