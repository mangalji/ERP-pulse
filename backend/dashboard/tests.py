"""
Test suite for the dashboard app.

Covers:
- DashboardService (get_summary, get_recent_*)
- Dashboard views (DashboardSummaryView, RecentSalesOrdersView, RecentInvoicesView, RecentCustomersView)
- Throttle classes
AnalyticsService tests live in analytics/tests.py.
All NetSuite dependencies are mocked.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings, RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from dashboard.services import DashboardService
from dashboard.views import (
    DashboardSummaryView,
    RecentCustomersView,
    RecentInvoicesView,
    RecentSalesOrdersView,
)
from netsuite.services import NetSuiteDataService


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
# DashboardService Tests
# ===================================================================

class DashboardServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        # Create a mock NetSuiteDataService and pass it to DashboardService
        self.mock_ns = MagicMock(spec=NetSuiteDataService)
        self.service = DashboardService(netsuite_data_service=self.mock_ns)

    def test_get_summary(self):
        self.mock_ns.get_records.return_value = {'totalResults': 42}

        result = self.service.get_summary(user=self.user)

        self.assertEqual(result['total_customers'], 42)
        self.assertEqual(result['total_employees'], 42)
        self.assertEqual(result['total_vendors'], 42)
        self.assertEqual(result['total_inventory_items'], 42)
        self.assertEqual(result['total_sales_orders'], 42)
        self.assertEqual(result['total_purchase_orders'], 42)
        self.assertEqual(result['total_invoices'], 42)
        self.assertEqual(self.mock_ns.get_records.call_count, 7)

    def test_get_summary_zero(self):
        self.mock_ns.get_records.return_value = {'totalResults': 0}

        result = self.service.get_summary(user=self.user)
        self.assertEqual(result['total_customers'], 0)

    def test_get_recent_sales_orders(self):
        self.mock_ns.get_records.return_value = {
            'items': [{'id': 1, 'tranId': 'SO-001'}],
            'totalResults': 1,
        }

        result = self.service.get_recent_sales_orders(user=self.user, limit=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)

    def test_get_recent_invoices(self):
        self.mock_ns.get_records.return_value = {
            'items': [{'id': 2, 'tranId': 'INV-001'}],
            'totalResults': 1,
        }

        result = self.service.get_recent_invoices(user=self.user, limit=5)
        self.assertEqual(len(result), 1)

    def test_get_recent_customers(self):
        self.mock_ns.get_records.return_value = {
            'items': [{'id': 3, 'entityId': 'CUST-001'}],
            'totalResults': 1,
        }

        result = self.service.get_recent_customers(user=self.user, limit=5)
        self.assertEqual(len(result), 1)

    def test_get_recent_employees(self):
        self.mock_ns.get_records.return_value = {
            'items': [{'id': 7, 'entityId': 'EMP-001'}],
            'totalResults': 1,
        }

        result = self.service.get_recent_employees(user=self.user, limit=5)
        self.assertEqual(len(result), 1)


# ===================================================================
# Dashboard View Tests
# ===================================================================

class DashboardViewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = _make_user()
        self.client = APIClient()

    @patch('dashboard.views.dashboard_service')
    def test_dashboard_summary(self, mock_dashboard_service):
        mock_dashboard_service.get_summary.return_value = {'total_customers': 10, 'total_employees': 5}

        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['total_customers'], 10)

    @patch('dashboard.views.dashboard_service')
    def test_recent_sales_orders(self, mock_dashboard_service):
        mock_dashboard_service.get_recent_sales_orders.return_value = [{'id': 1, 'tranId': 'SO-001'}]

        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/dashboard/recent-sales-orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)

    def test_dashboard_requires_auth(self):
        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===================================================================
# Throttle Tests
# ===================================================================

class DashboardThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = _make_user()
        self.client = APIClient()

    @patch('dashboard.views.dashboard_service')
    def test_dashboard_throttle(self, mock_dashboard_service):
        mock_dashboard_service.get_summary.return_value = {'total_customers': 1}
        self.client.credentials(**_auth_header(self.user))

        # Make 120 requests (should all succeed with default 120/min)
        for _ in range(120):
            response = self.client.get('/api/v1/dashboard/summary/')
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # 121st request should be throttled
        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
