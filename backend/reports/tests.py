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
from reports.services import ReportsService


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

    """
    ReportsService is now a thin pass-through to AnalyticsService (Phase
    3) — the month-bucketing/clamping logic these tests used to exercise
    directly now lives in, and is tested by,
    analytics.tests.AnalyticsServiceTests.test_sales_trend_by_month_*.
    These tests only need to prove the delegation itself is correct.
    """

    def setUp(self):
        self.user = _make_user()
        self.mock_analytics = MagicMock()
        self.service = ReportsService(analytics_service=self.mock_analytics)

    def test_get_sales_trend_delegates_to_analytics_service(self):
        self.mock_analytics.get_sales_trend_by_month.return_value = {
            'months': 6, 'currency': 'USD', 'trend': [{'period': '2026-05'}],
        }

        result = self.service.get_sales_trend(user=self.user, months=6)

        self.mock_analytics.get_sales_trend_by_month.assert_called_once_with(
            user=self.user, months=6
        )
        self.assertEqual(result, {
            'months': 6, 'currency': 'USD', 'trend': [{'period': '2026-05'}],
        })

    def test_get_sales_trend_passes_months_through_unmodified(self):
        # Clamping/defaulting is AnalyticsService's job now — ReportsService
        # must not second-guess it by clamping again itself.
        self.mock_analytics.get_sales_trend_by_month.return_value = {
            'months': 999, 'currency': 'USD', 'trend': [],
        }
        self.service.get_sales_trend(user=self.user, months=999)
        self.mock_analytics.get_sales_trend_by_month.assert_called_once_with(user=self.user,months=999)



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