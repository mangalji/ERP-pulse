"""
Test suite for the reports app.

Covers:
- ReportsService.get_sales_trend (month bucketing, empty results, clamping)
- SalesTrendView (auth required, months query param)

All NetSuite dependencies are mocked — no real SuiteQL calls.
"""

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from reports.services import MAX_MONTHS, ReportsService


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


class ReportsServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.mock_data_service = MagicMock()
        self.service = ReportsService(netsuite_data_service=self.mock_data_service)

    def test_merges_sales_orders_and_invoices_by_period(self):
        # Two SuiteQL calls happen per get_sales_trend() call: sales
        # orders first, then invoices (see _monthly_query call order).
        self.mock_data_service.execute_suiteql.side_effect = [
            {'items': [{'period': '2026-05', 'revenue': '1000', 'row_count': '2'}]},
            {'items': [{'period': '2026-05', 'revenue': '800', 'row_count': '1'}]},
        ]

        result = self.service.get_sales_trend(user=self.user, months=6)

        self.assertEqual(result['trend'], [{
            'period': '2026-05',
            'sales_orders_total': 1000.0,
            'sales_orders_count': 2,
            'invoice_revenue_total': 800.0,
            'invoice_count': 1,
        }])

    def test_periods_present_in_only_one_series_still_included(self):
        self.mock_data_service.execute_suiteql.side_effect = [
            {'items': [{'period': '2026-04', 'revenue': '500', 'row_count': '1'}]},
            {'items': [{'period': '2026-05', 'revenue': '300', 'row_count': '1'}]},
        ]

        result = self.service.get_sales_trend(user=self.user, months=6)
        periods = [row['period'] for row in result['trend']]
        self.assertEqual(periods, ['2026-04', '2026-05'])

        april_row = result['trend'][0]
        self.assertEqual(april_row['sales_orders_total'], 500.0)
        self.assertEqual(april_row['invoice_revenue_total'], 0.0)

    def test_empty_results(self):
        self.mock_data_service.execute_suiteql.side_effect = [
            {'items': []},
            {'items': []},
        ]
        result = self.service.get_sales_trend(user=self.user, months=6)
        self.assertEqual(result['trend'], [])

    def test_months_clamped_to_max(self):
        self.mock_data_service.execute_suiteql.side_effect = [
            {'items': []},
            {'items': []},
        ]
        result = self.service.get_sales_trend(user=self.user, months=999)
        self.assertEqual(result['months'], MAX_MONTHS)

    def test_months_defaults_when_invalid(self):
        self.mock_data_service.execute_suiteql.side_effect = [
            {'items': []},
            {'items': []},
        ]
        result = self.service.get_sales_trend(user=self.user, months='not-a-number')
        self.assertEqual(result['months'], 6)

    def test_months_floor_is_one(self):
        self.mock_data_service.execute_suiteql.side_effect = [
            {'items': []},
            {'items': []},
        ]
        result = self.service.get_sales_trend(user=self.user, months=0)
        self.assertEqual(result['months'], 1)


class SalesTrendViewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = _make_user()
        self.client = APIClient()

    def test_requires_authentication(self):
        response = self.client.get('/api/v1/reports/sales-trend/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('reports.views.ReportsService')
    def test_returns_trend_data(self, MockService):
        mock_service = MockService.return_value
        mock_service.get_sales_trend.return_value = {
            'months': 6, 'currency': 'USD', 'trend': [],
        }

        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/reports/sales-trend/?months=3')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        mock_service.get_sales_trend.assert_called_once_with(user=self.user, months='3')