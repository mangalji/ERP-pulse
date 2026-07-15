"""
Comprehensive test suite for the dashboard app.

Covers:
- DashboardService (get_summary, get_recent_*)
- BusinessInsightsService (get_top_customers, get_overdue_invoices, get_low_inventory, get_inactive_vendors, get_sales_summary)
- Dashboard views (DashboardSummaryView, RecentSalesOrdersView, RecentInvoicesView, RecentCustomersView)
- Throttle classes

All NetSuite dependencies are mocked.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings, RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from dashboard.services import DashboardService, BusinessInsightsService
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


# ===================================================================
# BusinessInsightsService Tests
# ===================================================================

class BusinessInsightsServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.mock_ns = MagicMock(spec=NetSuiteDataService)
        self.service = BusinessInsightsService(netsuite_data_service=self.mock_ns)

    # -- get_top_customers ---------------------------------------------
    def test_get_top_customers(self):
        self.mock_ns.get_customers.return_value = {
            'items': [
                {'id': 1, 'companyname': 'Acme', 'entityid': 'ACME', 'email': 'acme@test.com', 'balancesearch': 5000},
                {'id': 2, 'companyname': 'Beta', 'entityid': 'BETA', 'email': 'beta@test.com', 'balancesearch': 3000},
            ]
        }

        result = self.service.get_top_customers(user=self.user, limit=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'Acme')
        self.assertEqual(result[0]['balance'], 5000)
        self.assertEqual(result[1]['name'], 'Beta')
        self.assertEqual(result[1]['balance'], 3000)

    def test_get_top_customers_empty(self):
        self.mock_ns.get_customers.return_value = {'items': []}

        result = self.service.get_top_customers(user=self.user)
        self.assertEqual(result, [])

    # -- get_overdue_invoices ------------------------------------------
    def test_get_overdue_invoices(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [
                {
                    'id': 1,
                    'tranid': 'INV-001',
                    'duedate': '15/08/2023',
                    'total': '95000',
                    'currency': 'USD',
                    'entity': 101,
                    'foreignamountunpaid': '500',
                    'daysoverduesearch': '30',
                },
                {
                    'id': 2,
                    'tranid': 'INV-002',
                    'duedate': '20/08/2023',
                    'total': '120000',
                    'currency': 'USD',
                    'entity': 102,
                    'foreignamountunpaid': '0',
                    'daysoverduesearch': '0',
                },
            ]
        }

        result = self.service.get_overdue_invoices(user=self.user, limit=20)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['total'], 95000.0)
        self.assertEqual(result[0]['unpaid_amount'], 500.0)
        self.assertEqual(result[0]['days_overdue'], 30)
        self.assertTrue(result[0]['is_overdue'])
        self.assertEqual(result[1]['total'], 120000.0)
        self.assertEqual(result[1]['unpaid_amount'], 0.0)
        self.assertFalse(result[1]['is_overdue'])

    def test_get_overdue_invoices_missing_duedate(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [
                {
                    'id': 1,
                    'tranid': 'INV-001',
                    'duedate': None,
                    'total': '1000',
                    'currency': 'USD',
                    'entity': 101,
                    'foreignamountunpaid': '100',
                    'daysoverduesearch': '0',
                },
            ]
        }

        result = self.service.get_overdue_invoices(user=self.user)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]['due_date'])
        self.assertEqual(result[0]['days_overdue'], 0)

    def test_get_overdue_invoices_sorting(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [
                {'id': 1, 'tranid': 'A', 'duedate': '01/01/2023', 'total': '100', 'currency': 'USD', 'entity': 1, 'foreignamountunpaid': '10', 'daysoverduesearch': '5'},
                {'id': 2, 'tranid': 'B', 'duedate': '01/01/2023', 'total': '200', 'currency': 'USD', 'entity': 2, 'foreignamountunpaid': '20', 'daysoverduesearch': '15'},
                {'id': 3, 'tranid': 'C', 'duedate': '01/01/2023', 'total': '300', 'currency': 'USD', 'entity': 3, 'foreignamountunpaid': '30', 'daysoverduesearch': '10'},
            ]
        }

        result = self.service.get_overdue_invoices(user=self.user)
        self.assertEqual(result[0]['tran_id'], 'B')
        self.assertEqual(result[1]['tran_id'], 'C')
        self.assertEqual(result[2]['tran_id'], 'A')

    # -- get_low_inventory ---------------------------------------------
    @patch('dashboard.services.logger')
    def test_get_low_inventory_returns_empty(self, mock_logger):
        result = self.service.get_low_inventory(user=self.user)
        self.assertEqual(result, [])
        mock_logger.info.assert_called_once()

    # -- get_inactive_vendors ------------------------------------------
    def test_get_inactive_vendors(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [
                {'id': 1, 'companyname': 'Old Vendor', 'entityid': 'OLD', 'email': 'old@test.com'},
            ]
        }

        result = self.service.get_inactive_vendors(user=self.user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Old Vendor')
        self.assertEqual(result[0]['email'], 'old@test.com')
        self.assertNotIn('status', result[0])

    # -- get_sales_summary ---------------------------------------------
    def test_get_sales_summary(self):
        self.mock_ns.execute_suiteql.side_effect = [
            {'items': [{'row_count': '10', 'revenue': '50000'}]},
            {'items': [{'row_count': '5', 'revenue': '25000'}]},
        ]

        result = self.service.get_sales_summary(user=self.user)
        self.assertEqual(result['total_sales_orders'], 10)
        self.assertEqual(result['total_invoices'], 5)
        self.assertEqual(result['total_sales_revenue'], 50000.0)
        self.assertEqual(result['total_invoice_revenue'], 25000.0)
        self.assertEqual(result['average_order_value'], 5000.0)
        self.assertEqual(result['currency'], 'USD')

    def test_get_sales_summary_empty(self):
        self.mock_ns.execute_suiteql.return_value = {'items': []}

        result = self.service.get_sales_summary(user=self.user)
        self.assertEqual(result['total_sales_orders'], 0)
        self.assertEqual(result['total_invoices'], 0)
        self.assertEqual(result['average_order_value'], 0.0)


# ===================================================================
# Dashboard View Tests
# ===================================================================

class DashboardViewTests(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()

    @patch('dashboard.views.DashboardService')
    def test_dashboard_summary(self, MockDashboardService):
        mock_service = MockDashboardService.return_value
        mock_service.get_summary.return_value = {'total_customers': 10, 'total_employees': 5}

        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['total_customers'], 10)

    @patch('dashboard.views.DashboardService')
    def test_recent_sales_orders(self, MockDashboardService):
        mock_service = MockDashboardService.return_value
        mock_service.get_recent_sales_orders.return_value = [{'id': 1, 'tranId': 'SO-001'}]

        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/dashboard/recent-sales-orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['items']), 1)

    def test_dashboard_requires_auth(self):
        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===================================================================
# Throttle Tests
# ===================================================================

class DashboardThrottleTests(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()

    @patch('dashboard.views.DashboardService')
    def test_dashboard_throttle(self, MockDashboardService):
        mock_service = MockDashboardService.return_value
        mock_service.get_summary.return_value = {'total_customers': 1}
        self.client.credentials(**_auth_header(self.user))

        # Make 120 requests (should all succeed with default 120/min)
        for _ in range(120):
            response = self.client.get('/api/v1/dashboard/summary/')
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # 121st request should be throttled
        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
