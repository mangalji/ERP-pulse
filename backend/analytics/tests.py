"""
Test suite for analytics/services.py (AnalyticsService).

All NetSuite dependencies are mocked.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.test import TestCase
from accounts.models import User
from analytics.services import AnalyticsService
from netsuite.services import NetSuiteDataService


def _make_user(**overrides):
    n = _next_id()
    defaults = {
        'email': f'user{n}@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'mobile_number': f'1555{n:08d}',
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
    _counter = 1
    return _counter


# ===================================================================
# AnalyticsService Tests
#
# Moved here from dashboard/tests.py (Phase 3 moved the class itself
# from dashboard/services.py to analytics/services.py; this test file
# had been left behind).
# ===================================================================

class AnalyticsServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.mock_ns = MagicMock(spec=NetSuiteDataService)
        self.service = AnalyticsService(netsuite_data_service=self.mock_ns)

    # -- get_top_customers ---------------------------------------------
    def test_get_top_customers(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [
                {'id': 1, 'companyname': 'Acme', 'entityid': 'ACME', 'email': 'acme@test.com', 'balancesearch': '5000'},
                {'id': 2, 'companyname': 'Beta', 'entityid': 'BETA', 'email': 'beta@test.com', 'balancesearch': '3000'},
            ]
        }

        result = self.service.get_top_customers(user=self.user, limit=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'Acme')
        self.assertEqual(result[0]['balance'], 5000)
        self.assertEqual(result[1]['name'], 'Beta')
        self.assertEqual(result[1]['balance'], 3000)

    def test_get_top_customers_empty(self):
        self.mock_ns.execute_suiteql.return_value = {'items': []}

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
    @patch('analytics.services.logger')
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

    def test_get_revenue_by_customer(self):
        self.mock_ns.execute_suiteql.side_effect = [
            {'items': [
                {'entity': 101, 'revenue': '9000'},
                {'entity': 102, 'revenue': '4000'},
            ]},
            {'items': [
                {'id': 101, 'companyname': 'Acme', 'entityid': 'ACME'},
                {'id': 102, 'companyname': 'Beta', 'entityid': 'BETA'},
            ]},
        ]

        result = self.service.get_revenue_by_customer(user=self.user, limit=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'Acme')
        self.assertEqual(result[0]['revenue'], 9000.0)
        self.assertEqual(result[1]['name'], 'Beta')
        self.assertEqual(result[1]['revenue'], 4000.0)

    def test_get_revenue_by_customer_missing_customer_record(self):
        """A revenue row whose customer lookup returns nothing should still be included."""
        self.mock_ns.execute_suiteql.side_effect = [
            {'items': [{'entity': 999, 'revenue': '1000'}]},
            {'items': []},
        ]

        result = self.service.get_revenue_by_customer(user=self.user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Customer 999')
        self.assertEqual(result[0]['revenue'], 1000.0)

    def test_get_revenue_by_customer_empty(self):
        self.mock_ns.execute_suiteql.return_value = {'items': []}

        result = self.service.get_revenue_by_customer(user=self.user)
        self.assertEqual(result, [])

    def test_get_revenue_for_period(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [{'revenue': '15000', 'row_count': '7'}]
        }

        result = self.service.get_revenue_for_period(
            user=self.user, start_date='2025-04-01', end_date='2026-04-01'
        )
        self.assertEqual(result['revenue'], 15000.0)
        self.assertEqual(result['transaction_count'], 7)
        self.assertEqual(result['start_date'], '2025-04-01')
        self.assertEqual(result['end_date'], '2026-04-01')

    def test_get_revenue_for_period_empty(self):
        self.mock_ns.execute_suiteql.return_value = {'items': []}

        result = self.service.get_revenue_for_period(
            user=self.user, start_date='2025-04-01', end_date='2026-04-01'
        )
        self.assertEqual(result['revenue'], 0.0)
        self.assertEqual(result['transaction_count'], 0)

    def test_get_sales_summary_includes_average_invoice_value(self):
        self.mock_ns.execute_suiteql.side_effect = [
            {'items': [{'row_count': '10', 'revenue': '50000'}]},
            {'items': [{'row_count': '5', 'revenue': '25000'}]},
        ]

        result = self.service.get_sales_summary(user=self.user)
        self.assertEqual(result['average_invoice_value'], 5000.0)

    def test_get_sales_summary_empty_average_invoice_value(self):
        self.mock_ns.execute_suiteql.return_value = {'items': []}

        result = self.service.get_sales_summary(user=self.user)
        self.assertEqual(result['average_invoice_value'], 0.0)

    def test_get_total_receivables(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [{'total_receivable': '125000', 'customer_count': '42'}]
        }

        result = self.service.get_total_receivables(user=self.user)
        self.assertEqual(result['total_receivable'], 125000.0)
        self.assertEqual(result['customers_with_balance'], 42)

    def test_get_total_receivables_empty(self):
        self.mock_ns.execute_suiteql.return_value = {'items': []}

        result = self.service.get_total_receivables(user=self.user)
        self.assertEqual(result['total_receivable'], 0.0)
        self.assertEqual(result['customers_with_balance'], 0)

    def test_get_overdue_invoices_summary(self):
        self.mock_ns.execute_suiteql.return_value = {
            'items': [{'invoice_count': '8', 'total_overdue': '32000'}]
        }

        result = self.service.get_overdue_invoices_summary(user=self.user)
        self.assertEqual(result['overdue_invoice_count'], 8)
        self.assertEqual(result['total_overdue_amount'], 32000.0)

    def test_get_overdue_invoices_summary_empty(self):
        self.mock_ns.execute_suiteql.return_value = {'items': []}

        result = self.service.get_overdue_invoices_summary(user=self.user)
        self.assertEqual(result['overdue_invoice_count'], 0)
        self.assertEqual(result['total_overdue_amount'], 0.0)


# ===================================================================
# get_sales_trend_by_month Tests
#
# Moved from reports/tests.py (Phase 3 moved this method's logic from
# ReportsService into AnalyticsService; ReportsService.get_sales_trend
# is now a thin pass-through — see reports/tests.py for its delegation
# test).
# ===================================================================

class SalesTrendByMonthTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.mock_ns = MagicMock(spec=NetSuiteDataService)
        self.service = AnalyticsService(netsuite_data_service=self.mock_ns)

    def test_merges_sales_orders_and_invoices_by_period(self):
        # Two SuiteQL calls happen per call: sales orders first, then
        # invoices (see _monthly_query call order).
        self.mock_ns.execute_suiteql.side_effect = [
            {'items': [{'period': '2026-05', 'revenue': '1000', 'row_count': '2'}]},
            {'items': [{'period': '2026-05', 'revenue': '800', 'row_count': '1'}]},
        ]

        result = self.service.get_sales_trend_by_month(user=self.user, months=6)

        self.assertEqual(result['trend'], [{
            'period': '2026-05',
            'sales_orders_total': 1000.0,
            'sales_orders_count': 2,
            'invoice_revenue_total': 800.0,
            'invoice_count': 1,
        }])

    def test_periods_present_in_only_one_series_still_included(self):
        self.mock_ns.execute_suiteql.side_effect = [
            {'items': [{'period': '2026-04', 'revenue': '500', 'row_count': '1'}]},
            {'items': [{'period': '2026-05', 'revenue': '300', 'row_count': '1'}]},
        ]

        result = self.service.get_sales_trend_by_month(user=self.user, months=6)
        periods = [row['period'] for row in result['trend']]
        self.assertEqual(periods, ['2026-04', '2026-05'])

        april_row = result['trend'][0]
        self.assertEqual(april_row['sales_orders_total'], 500.0)
        self.assertEqual(april_row['invoice_revenue_total'], 0.0)

    def test_empty_results(self):
        self.mock_ns.execute_suiteql.side_effect = [{'items': []}, {'items': []}]
        result = self.service.get_sales_trend_by_month(user=self.user, months=6)
        self.assertEqual(result['trend'], [])

    def test_months_clamped_to_max(self):
        self.mock_ns.execute_suiteql.side_effect = [{'items': []}, {'items': []}]
        result = self.service.get_sales_trend_by_month(user=self.user, months=999)
        self.assertEqual(result['months'], 24)

    def test_months_defaults_when_invalid(self):
        self.mock_ns.execute_suiteql.side_effect = [{'items': []}, {'items': []}]
        result = self.service.get_sales_trend_by_month(user=self.user, months='not-a-number')
        self.assertEqual(result['months'], 6)

    def test_months_floor_is_one(self):
        self.mock_ns.execute_suiteql.side_effect = [{'items': []}, {'items': []}]
        result = self.service.get_sales_trend_by_month(user=self.user, months=0)
        self.assertEqual(result['months'], 1)