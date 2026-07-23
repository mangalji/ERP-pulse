"""
Comprehensive test suite for the ai app.

Covers:
- AIService (ask, conversation management, history, context)
- OpenAIProvider (mocked HTTP)
- GeminiProvider (mocked HTTP)
- AIProviderFactory
- AIChatRequestSerializer
- AIConversationSerializer
- AIMessageSerializer
- ConversationRepository
- MessageRepository
- build_system_prompt
- build_user_prompt
- build_context

All external dependencies are mocked:
- AI provider HTTP calls (OpenAI, Gemini)
- NetSuite data fetching
- Email sending
"""

import json
from unittest.mock import MagicMock, patch
from ai.business_context import AIRequestContext, BusinessContext
from django.core.cache import cache
from django.test import TestCase, override_settings, RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from ai.context_builder import (
    build_context,
    _current_fiscal_year_range,
    _current_month_range,
    _previous_month_range,
)
from ai.exceptions import AIConversationNotFoundException, AIProviderNotConfiguredException, AIProviderRequestException
from ai.models import AIConversation, AIMessage, AIAuditLog
from ai.prompts import build_system_prompt, build_user_prompt, PROMPT_VERSION
from ai.repositories import ConversationRepository, MessageRepository
from ai.serializers import AIChatRequestSerializer, AIConversationSerializer, AIMessageSerializer
from ai.services import AIService, NETSUITE_NOT_CONNECTED_ANSWER
from ai.views import ChatView, ConversationHistoryView, ConversationMessagesView


_user_counter = 0


def _make_user(**overrides):
    global _user_counter
    _user_counter = 1
    defaults = {
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'mobile_number': f'1234{_user_counter:06d}',
        'is_active': True,
        'is_email_verified': True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password('testpass123')
    user.save()
    return user


def _auth_header(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}


# ===================================================================
# Prompt Tests
# ===================================================================

class PromptTests(TestCase):
    def test_build_system_prompt(self):
        prompt = build_system_prompt()
        self.assertIn('ERP Pulse', prompt)
        self.assertIn('Business Intelligence Assistant', prompt)

    def test_build_user_prompt_with_context(self):
        context = AIRequestContext(
            netsuite_connected=True,
            business_context=BusinessContext(summary={'total_customers':10}),
        )
        prompt = build_user_prompt(context=context, message='How many customers?')
        self.assertIn('How many customers?', prompt)
        self.assertIn('Business context:', prompt)

    def test_build_user_prompt_without_context(self):
        context = AIRequestContext(netsuite_connected=False, business_context=None)
        prompt = build_user_prompt(context=context, message='How many customers?')
        self.assertIn('How many customers?', prompt)
        self.assertIn('NetSuite is not connected', prompt)


# ===================================================================
# Context Builder Tests
# ===================================================================

class ContextBuilderTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('ai.context_builder.AnalyticsService')
    @patch('ai.context_builder.DashboardService')
    @patch('ai.context_builder.NetSuiteConnectionRepository')
    def test_build_context_connected(self, MockRepo, MockDashboardService, MockAnalyticsService):
        mock_repo = MockRepo.return_value
        mock_repo.get_by_user.return_value = MagicMock(is_active=True)

        mock_dashboard = MockDashboardService.return_value
        mock_dashboard.get_summary.return_value = {'total_customers': 10}
        mock_dashboard.get_recent_customers.return_value = []
        mock_dashboard.get_recent_invoices.return_value = []
        mock_dashboard.get_recent_sales_orders.return_value = []
        mock_dashboard.get_recent_employees.return_value = []

        mock_analytics = MockAnalyticsService.return_value
        mock_analytics.get_sales_summary.return_value = {'total_sales_orders':3}
        mock_analytics.get_top_customers.return_value = [{'name':'Acme'}]
        mock_analytics.get_overdue_invoices.return_value = []
        mock_analytics.get_overdue_invoices_summary.return_value = {
            'overdue_invoice_count':2,'total_overdue_amount':4000.0,
        }

        mock_analytics.get_inactive_vendors.return_value = []
        mock_analytics.get_low_inventory.return_value = []
        mock_analytics.get_total_receivables.return_value = {
             'total_receivable': 20000.0, 'customers_with_balance': 15,
         }
        mock_analytics.get_revenue_by_customer.return_value = [{'name': 'Acme', 'revenue': 9000.0}]
        mock_analytics.get_revenue_for_period.return_value = {'revenue': 5000.0, 'transaction_count': 2}

        context = build_context(self.user)
        self.assertTrue(context.netsuite_connected)
        self.assertIsNotNone(context.business_context)

        # Pre-existing Dashboard fields — unchanged, still present.
        self.assertEqual(context.business_context.summary['total_customers'], 10)
        self.assertEqual(context.business_context.recent_customers, [])
        self.assertEqual(context.business_context.recent_invoices, [])
        self.assertEqual(context.business_context.recent_sales_orders, [])
        self.assertEqual(context.business_context.recent_employees, [])

        # New Business Insights fields — additive.
        self.assertEqual(context.business_context.sales_summary['total_sales_orders'], 3)
        self.assertEqual(context.business_context.top_customers, [{'name': 'Acme'}])
        self.assertEqual(context.business_context.overdue_invoices, [])
        self.assertEqual(context.business_context.overdue_invoices_summary['overdue_invoice_count'], 2)
        self.assertEqual(context.business_context.inactive_vendors, [])
        self.assertEqual(context.business_context.low_inventory, [])
        self.assertEqual(context.business_context.total_receivables['total_receivable'], 20000.0)

        # New revenue fields — additive.
        self.assertEqual(context.business_context.top_customers_by_revenue,[{'name':'Acme','revenue':9000.0}],)
        self.assertEqual(context.business_context.revenue_this_month['revenue'],5000.0)
        self.assertEqual(context.business_context.revenue_last_month['revenue'],5000.0)
        self.assertEqual(context.business_context.revenue_this_fiscal_year['revenue'],5000.0)
        # get_revenue_for_period is called three times (this month, last
        # month, this fiscal year) with distinct, non-overlapping ranges.
        call_ranges = [
            (c.kwargs['start_date'], c.kwargs['end_date'])
            for c in mock_analytics.get_revenue_for_period.call_args_list
        ]
        self.assertEqual(len(call_ranges), 3)
        self.assertEqual(len(set(call_ranges)), 3)

        # Also confirm as_dict() round-trips correctly — this is exactly
        # what ai/prompts.py's json.dumps() call relies on, and what the
        # missing BusinessContext(**business_context) wrap (fixed this
        # session) would have crashed on with AttributeError.
        as_dict = context.as_dict()
        self.assertEqual(as_dict['business_context']['summary']['total_customers'], 10)

    @patch('ai.context_builder.NetSuiteConnectionRepository')
    def test_build_context_not_connected(self, MockRepo):
        mock_repo = MockRepo.return_value
        mock_repo.get_by_user.return_value = None

        context = build_context(self.user)
        self.assertFalse(context.netsuite_connected)
        self.assertIsNone(context.business_context)

    @patch('ai.context_builder.AnalyticsService')
    @patch('ai.context_builder.DashboardService')
    @patch('ai.context_builder.NetSuiteConnectionRepository')
    def test_build_context_degrades_gracefully_on_partial_failure(
        self, MockRepo, MockDashboardService, MockAnalyticsService
    ):
        """
        One failing insight (top_customers) must not prevent the rest of
        business_context from being built, and must not raise out of
        build_context() at all.
        """
        mock_repo = MockRepo.return_value
        mock_repo.get_by_user.return_value = MagicMock(is_active=True)

        mock_dashboard = MockDashboardService.return_value
        mock_dashboard.get_summary.return_value = {'total_customers': 10}
        mock_dashboard.get_recent_customers.return_value = []
        mock_dashboard.get_recent_invoices.return_value = []
        mock_dashboard.get_recent_sales_orders.return_value = []
        mock_dashboard.get_recent_employees.return_value = []

        mock_analytics = MockAnalyticsService.return_value
        mock_analytics.get_sales_summary.return_value = {'total_sales_orders': 3}
        mock_analytics.get_top_customers.side_effect = Exception('SuiteQL timeout')
        mock_analytics.get_overdue_invoices.return_value = []
        mock_analytics.get_overdue_invoices_summary.return_value = {}
        mock_analytics.get_inactive_vendors.return_value = []
        mock_analytics.get_low_inventory.return_value = []
        mock_analytics.get_total_receivables.return_value = {}
        mock_analytics.get_revenue_by_customer.return_value = []
        mock_analytics.get_revenue_for_period.return_value = {}

        context = build_context(self.user)

        # The whole request survives — no exception propagated.
        self.assertTrue(context.netsuite_connected)
        self.assertIsNotNone(context.business_context)

        # The failing insight is omitted (None), not fabricated.
        self.assertIsNone(context.business_context.top_customers)

        # Every other insight still built normally.
        self.assertEqual(context.business_context.summary['total_customers'], 10)
        self.assertEqual(context.business_context.sales_summary['total_sales_orders'], 3)
        self.assertEqual(context.business_context.overdue_invoices, [])

    @patch('ai.context_builder.AnalyticsService')
    @patch('ai.context_builder.DashboardService')
    @patch('ai.context_builder.NetSuiteConnectionRepository')
    def test_build_context_is_cached_for_60_seconds(
        self, MockRepo, MockDashboardService, MockAnalyticsService
    ):
        """
        No test coverage existed for this at all before this session.
        build_context() runs ~15 live SuiteQL-backed calls, so a second
        call within the cache TTL must reuse the cached result rather
        than re-querying every service again.
        """
        mock_repo = MockRepo.return_value
        mock_repo.get_by_user.return_value = MagicMock(is_active=True)
        mock_dashboard = MockDashboardService.return_value
        mock_dashboard.get_summary.return_value = {'total_customers': 10}
        mock_dashboard.get_recent_customers.return_value = []
        mock_dashboard.get_recent_invoices.return_value = []
        mock_dashboard.get_recent_sales_orders.return_value = []
        mock_dashboard.get_recent_employees.return_value = []
        mock_analytics = MockAnalyticsService.return_value
        for method in (
            'get_sales_summary', 'get_top_customers', 'get_overdue_invoices',
            'get_overdue_invoices_summary', 'get_inactive_vendors', 'get_low_inventory',
            'get_total_receivables', 'get_revenue_by_customer', 'get_revenue_for_period',
        ):
            getattr(mock_analytics, method).return_value = {}

        first = build_context(self.user)
        second = build_context(self.user)

        self.assertEqual(first, second)
        # Only the first call should have actually hit the mocked services.
        self.assertEqual(mock_dashboard.get_summary.call_count, 1)
        self.assertEqual(mock_analytics.get_sales_summary.call_count, 1)

    @patch('ai.context_builder.NetSuiteConnectionRepository')
    def test_build_context_cache_is_scoped_per_user(self, MockRepo):
        mock_repo = MockRepo.return_value
        mock_repo.get_by_user.return_value = None

        other_user = _make_user(email='other@example.com')
        build_context(self.user)
        # A cached "not connected" result for one user must not leak to
        # another user's context lookup.
        self.assertEqual(mock_repo.get_by_user.call_count, 1)
        build_context(other_user)
        self.assertEqual(mock_repo.get_by_user.call_count, 2)

class DateRangeHelperTests(TestCase):
    """
    `_current_month_range` and `_current_fiscal_year_range` are plain date
    math (no NetSuite call), so these are tested directly against fixed,
    mocked "now" values rather than through build_context().
    """

    @patch('ai.context_builder.timezone')
    def test_current_month_range(self, mock_timezone):
        import datetime
        mock_timezone.now.return_value.date.return_value = datetime.date(2026, 7, 16)

        start, end = _current_month_range()
        self.assertEqual(start, '2026-07-01')
        self.assertEqual(end, '2026-08-01')

    @patch('ai.context_builder.timezone')
    def test_current_month_range_december(self, mock_timezone):
        import datetime
        mock_timezone.now.return_value.date.return_value = datetime.date(2026, 12, 25)

        start, end = _current_month_range()
        self.assertEqual(start, '2026-12-01')
        self.assertEqual(end, '2027-01-01')

    @patch('ai.context_builder.timezone')
    def test_previous_month_range(self, mock_timezone):
        import datetime
        mock_timezone.now.return_value.date.return_value = datetime.date(2026, 7, 16)

        start, end = _previous_month_range()
        self.assertEqual(start, '2026-06-01')
        self.assertEqual(end, '2026-07-01')

    @patch('ai.context_builder.timezone')
    def test_previous_month_range_january_rollover(self, mock_timezone):
        import datetime
        mock_timezone.now.return_value.date.return_value = datetime.date(2026, 1, 15)

        start, end = _previous_month_range()
        self.assertEqual(start, '2025-12-01')
        self.assertEqual(end, '2026-01-01')

    @patch('ai.context_builder.timezone')
    def test_current_fiscal_year_range_after_april(self, mock_timezone):
        import datetime
        # July 2026 falls in FY 2026-2027 (Apr 2026 - Mar 2027).
        mock_timezone.now.return_value.date.return_value = datetime.date(2026, 7, 16)

        start, end = _current_fiscal_year_range()
        self.assertEqual(start, '2026-04-01')
        self.assertEqual(end, '2027-04-01')

    @patch('ai.context_builder.timezone')
    def test_current_fiscal_year_range_before_april(self, mock_timezone):
        import datetime
        # January 2026 falls in FY 2025-2026 (Apr 2025 - Mar 2026).
        mock_timezone.now.return_value.date.return_value = datetime.date(2026, 1, 15)

        start, end = _current_fiscal_year_range()
        self.assertEqual(start, '2025-04-01')
        self.assertEqual(end, '2026-04-01')


# ===================================================================
# Repository Tests
# ===================================================================

class ConversationRepositoryTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.repo = ConversationRepository()

    def test_create_conversation(self):
        conv = self.repo.create(user=self.user, title='Test Chat')
        self.assertEqual(conv.user, self.user)
        self.assertEqual(conv.title, 'Test Chat')

    def test_get_by_id_for_user_found(self):
        conv = AIConversation.objects.create(user=self.user, title='Test')
        fetched = self.repo.get_by_id_for_user(conversation_id=conv.id, user=self.user)
        self.assertEqual(fetched, conv)

    def test_get_by_id_for_user_wrong_user(self):
        other_user = _make_user(email='other@example.com')
        conv = AIConversation.objects.create(user=other_user, title='Test')
        fetched = self.repo.get_by_id_for_user(conversation_id=conv.id, user=self.user)
        self.assertIsNone(fetched)

    def test_get_all_for_user(self):
        AIConversation.objects.create(user=self.user, title='Chat 1')
        AIConversation.objects.create(user=self.user, title='Chat 2')
        result = self.repo.get_all_for_user(user=self.user)
        self.assertEqual(result.count(), 2)


class MessageRepositoryTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.conversation = AIConversation.objects.create(user=self.user, title='Test')
        self.repo = MessageRepository()

    def test_save_message(self):
        msg = self.repo.save(conversation=self.conversation, role=AIMessage.Role.USER, content='Hello')
        self.assertEqual(msg.conversation, self.conversation)
        self.assertEqual(msg.content, 'Hello')

    def test_get_history(self):
        self.repo.save(conversation=self.conversation, role=AIMessage.Role.USER, content='Hello')
        self.repo.save(conversation=self.conversation, role=AIMessage.Role.ASSISTANT, content='Hi')
        result = list(self.repo.get_history(conversation=self.conversation))
        self.assertEqual(len(result), 2)

    def test_get_recent_history(self):
        for i in range(10):
            self.repo.save(conversation=self.conversation, role=AIMessage.Role.USER, content=f'Msg {i}')
        result = self.repo.get_recent_history(conversation=self.conversation, limit=3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].content, 'Msg 9')


# ===================================================================
# AI Provider Tests
# ===================================================================

class OpenAIProviderTests(TestCase):
    @patch('ai.providers.settings')
    def test_init_no_api_key(self, mock_settings):
        mock_settings.OPENAI_API_KEY = ''
        mock_settings.OPENAI_MODEL = 'gpt-4o-mini'
        from ai.providers import OpenAIProvider
        provider = OpenAIProvider()
        with self.assertRaises(AIProviderNotConfiguredException):
            provider.generate_response(system_prompt='You are helpful.', user_prompt='Hi')

    @patch('ai.providers.requests.post')
    @patch('ai.providers.settings')
    def test_generate_response_success(self, mock_settings, mock_post):
        mock_settings.OPENAI_API_KEY = 'test-key'
        mock_settings.OPENAI_MODEL = 'gpt-4o-mini'
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                'choices': [{'message': {'content': 'Hello from OpenAI'}}]
            }),
        )

        from ai.providers import OpenAIProvider
        provider = OpenAIProvider()
        result = provider.generate_response(
            system_prompt='You are helpful.',
            user_prompt='Say hello.',
        )
        self.assertEqual(result, 'Hello from OpenAI')


class GeminiProviderTests(TestCase):
    @patch('ai.providers.settings')
    def test_init_no_api_key(self, mock_settings):
        mock_settings.GEMINI_API_KEY = ''
        mock_settings.GEMINI_MODEL = 'gemini-1.5-flash'
        from ai.providers import GeminiProvider
        provider = GeminiProvider()
        with self.assertRaises(AIProviderNotConfiguredException):
            provider.generate_response(system_prompt='You are helpful.', user_prompt='Hi')

    @patch('ai.providers.requests.post')
    @patch('ai.providers.settings')
    def test_generate_response_success(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = 'test-key'
        mock_settings.GEMINI_MODEL = 'gemini-2.5-flash'
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                'candidates': [{'content': {'parts': [{'text': 'Hello from Gemini'}]}}]
            }),
        )

        from ai.providers import GeminiProvider
        provider = GeminiProvider()
        result = provider.generate_response(
            system_prompt='You are helpful.',
            user_prompt='Say hello.',
        )
        self.assertEqual(result, 'Hello from Gemini')

    @patch('ai.providers.requests.post')
    @patch('ai.providers.settings')
    def test_generate_response_network_error(self, mock_settings, mock_post):
        import requests
        mock_settings.GEMINI_API_KEY = 'test-key'
        mock_settings.GEMINI_MODEL = 'gemini-2.5-flash'
        mock_post.side_effect = requests.RequestException('Network error')

        from ai.providers import GeminiProvider
        provider = GeminiProvider()
        with self.assertRaises(AIProviderRequestException):
            provider.generate_response(
                system_prompt='You are helpful.',
                user_prompt='Say hello.',
            )

    @patch('ai.providers.requests.post')
    @patch('ai.providers.settings')
    def test_generate_response_unexpected_shape(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = 'test-key'
        mock_settings.GEMINI_MODEL = 'gemini-2.5-flash'
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={'unexpected': 'shape'}),
        )

        from ai.providers import GeminiProvider
        provider = GeminiProvider()
        with self.assertRaises(AIProviderRequestException):
            provider.generate_response(
                system_prompt='You are helpful.',
                user_prompt='Say hello.',
            )


# ===================================================================
# AI Provider Factory Tests
# ===================================================================

class AIProviderFactoryTests(TestCase):
    @patch('ai.providers.settings')
    def test_create_openai_provider(self, mock_settings):
        mock_settings.AI_PROVIDER = 'openai'
        mock_settings.OPENAI_API_KEY = 'test-key'
        from ai.providers import AIProviderFactory, OpenAIProvider
        provider = AIProviderFactory.create()
        self.assertIsInstance(provider, OpenAIProvider)

    @patch('ai.providers.settings')
    def test_create_gemini_provider(self, mock_settings):
        mock_settings.AI_PROVIDER = 'gemini'
        mock_settings.GEMINI_API_KEY = 'test-key'
        from ai.providers import AIProviderFactory, GeminiProvider
        provider = AIProviderFactory.create()
        self.assertIsInstance(provider, GeminiProvider)

    @patch('ai.providers.settings')
    def test_create_unsupported_provider(self, mock_settings):
        mock_settings.AI_PROVIDER = 'unknown'
        with self.assertRaises(AIProviderNotConfiguredException):
            from ai.providers import AIProviderFactory
            AIProviderFactory.create()


# ===================================================================
# AIService Tests
# ===================================================================

class AIServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        # AIService resolves its provider once in __init__ (`provider or
        # AIProviderFactory.create()`). Patching AIProviderFactory.create via
        # a per-test decorator has no effect on a service already built in
        # setUp, since setUp runs before the patch context is active. Inject
        # a mock provider directly instead — AIService already supports this.
        self.mock_provider = MagicMock()
        self.mock_provider.model = 'test-model'
        self.service = AIService(provider=self.mock_provider)

    @patch('ai.services.build_context')
    def test_ask_returns_answer(self, mock_build_context):
        mock_build_context.return_value = AIRequestContext(
            netsuite_connected=True, business_context=BusinessContext(),
        )
        self.mock_provider.generate_response.return_value = 'Test answer'

        result = self.service.ask(user=self.user, message='Hello')
        self.assertEqual(result['answer'], 'Test answer')
        self.assertIsNotNone(result['conversation_id'])

    @patch('ai.services.build_context')
    def test_ask_returns_disconnected_answer(self, mock_build_context):
        mock_build_context.return_value = AIRequestContext(
            netsuite_connected=False, business_context=None,
        )

        result = self.service.ask(user=self.user, message='Hello')
        self.assertEqual(result['answer'], NETSUITE_NOT_CONNECTED_ANSWER)

    @patch('ai.services.build_context')
    def test_ask_with_existing_conversation(self, mock_build_context):
        mock_build_context.return_value = AIRequestContext(
            netsuite_connected=True, business_context=BusinessContext(),
        )
        self.mock_provider.generate_response.return_value = 'Follow-up answer'

        conversation = AIConversation.objects.create(user=self.user, title='Existing')
        result = self.service.ask(user=self.user, message='Follow-up', conversation_id=str(conversation.id))
        self.assertEqual(result['answer'], 'Follow-up answer')

    def test_ask_invalid_conversation(self):
        with self.assertRaises(AIConversationNotFoundException):
            self.service.ask(user=self.user, message='Hello', conversation_id='00000000-0000-0000-0000-000000000000')

    @patch('ai.services.build_context')
    def test_ask_saves_messages(self, mock_build_context):
        mock_build_context.return_value = AIRequestContext(
            netsuite_connected=True, business_context=BusinessContext(),
        )
        self.mock_provider.generate_response.return_value = 'Answer'

        result = self.service.ask(user=self.user, message='Hello')
        conversation_id = result['conversation_id']
        conversation = AIConversation.objects.get(id=conversation_id)
        messages = AIMessage.objects.filter(conversation=conversation)
        self.assertEqual(messages.count(), 2)
        self.assertEqual(messages[0].role, AIMessage.Role.USER)
        self.assertEqual(messages[1].role, AIMessage.Role.ASSISTANT)

    def test_build_title_short(self):
        title = AIService._build_title('Short title')
        self.assertEqual(title, 'Short title')

    def test_build_title_long(self):
        long_text = 'A' * 100
        title = AIService._build_title(long_text)
        self.assertEqual(len(title), 60)
        self.assertTrue(title.endswith('\u2026'))


# ===================================================================
# AIAuditLog Tests
#
# No coverage existed for any of this before this session — added per
# claude_phase4.md Task 1B.
# ===================================================================

class AIAuditLogTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.mock_provider = MagicMock()
        self.mock_provider.model = 'test-model'
        self.mock_provider.__class__.__name__ = 'MockProvider'
        self.service = AIService(provider=self.mock_provider)

    @patch('ai.services.build_context')
    def test_successful_call_writes_audit_log(self, mock_build_context):
        mock_build_context.return_value = AIRequestContext(
            netsuite_connected=True, business_context=BusinessContext(),
        )
        self.mock_provider.generate_response.return_value = 'Answer'

        result = self.service.ask(user=self.user, message='Hello')

        log = AIAuditLog.objects.get(conversation_id=result['conversation_id'])
        self.assertTrue(log.success)
        self.assertEqual(log.user_id, self.user.id)
        self.assertIsNone(log.error_message)
        self.assertIsNotNone(log.latency_ms)
        self.assertEqual(log.prompt_version, PROMPT_VERSION)

    @patch('ai.services.build_context')
    def test_failed_provider_call_writes_audit_log_and_reraises(self, mock_build_context):
        mock_build_context.return_value = AIRequestContext(
            netsuite_connected=True, business_context=BusinessContext(),
        )
        self.mock_provider.generate_response.side_effect = AIProviderRequestException('boom')

        with self.assertRaises(AIProviderRequestException):
            self.service.ask(user=self.user, message='Hello')

        log = AIAuditLog.objects.get(user=self.user)
        self.assertFalse(log.success)
        self.assertIn('boom', log.error_message)

    @patch('ai.services.build_context')
    def test_not_connected_does_not_write_audit_log(self, mock_build_context):
        """
        The NetSuite-not-connected answer is deterministic and never
        reaches the provider (see AIService._generate_answer's early
        return) — so there is nothing provider-related to audit.
        """
        mock_build_context.return_value = AIRequestContext(
            netsuite_connected=False, business_context=None,
        )

        self.service.ask(user=self.user, message='Hello')

        self.assertEqual(AIAuditLog.objects.filter(user=self.user).count(), 0)
        self.mock_provider.generate_response.assert_not_called()

# ===================================================================
# Serializer Tests
# ===================================================================

class AISerializerTests(TestCase):
    def test_chat_request_valid(self):
        serializer = AIChatRequestSerializer(data={'message': 'Hello'})
        self.assertTrue(serializer.is_valid())

    def test_chat_request_blank_message(self):
        serializer = AIChatRequestSerializer(data={'message': '   '})
        self.assertFalse(serializer.is_valid())

    def test_chat_request_missing_message(self):
        serializer = AIChatRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())

    def test_conversation_serializer(self):
        user = _make_user()
        conv = AIConversation.objects.create(user=user, title='Test')
        serializer = AIConversationSerializer(conv)
        self.assertEqual(serializer.data['title'], 'Test')
        self.assertNotIn('messages', serializer.data)

    def test_message_serializer(self):
        user = _make_user()
        conv = AIConversation.objects.create(user=user, title='Test')
        msg = AIMessage.objects.create(conversation=conv, role=AIMessage.Role.USER, content='Hello')
        serializer = AIMessageSerializer(msg)
        self.assertEqual(serializer.data['content'], 'Hello')
        self.assertEqual(serializer.data['role'], 'USER')


# ===================================================================
# View Tests
# ===================================================================

class AIViewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = _make_user()
        self.client = APIClient()

    @patch('ai.views.AIService')
    def test_chat_view(self, MockAIService):
        mock_service = MockAIService.return_value
        mock_service.ask.return_value = {
            'conversation_id': '123',
            'answer': 'Hello!',
        }

        self.client.credentials(**_auth_header(self.user))
        response = self.client.post('/api/v1/ai/chat/', {
            'message': 'Hello',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['answer'], 'Hello!')

    def test_chat_view_requires_auth(self):
        response = self.client.post('/api/v1/ai/chat/', {'message': 'Hello'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('ai.views.AIService')
    def test_conversation_history_view(self, MockAIService):
        self.client.credentials(**_auth_header(self.user))
        AIConversation.objects.create(user=self.user, title='Chat 1')
        AIConversation.objects.create(user=self.user, title='Chat 2')

        response = self.client.get('/api/v1/ai/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)

    @patch('ai.views.AIService')
    def test_conversation_messages_view(self, MockAIService):
        self.client.credentials(**_auth_header(self.user))
        conv = AIConversation.objects.create(user=self.user, title='Chat')
        AIMessage.objects.create(conversation=conv, role=AIMessage.Role.USER, content='Hello')
        AIMessage.objects.create(conversation=conv, role=AIMessage.Role.ASSISTANT, content='Hi')

        response = self.client.get(f'/api/v1/ai/history/{conv.id}/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)

    def test_conversation_messages_not_found(self):
        self.client.credentials(**_auth_header(self.user))
        response = self.client.get('/api/v1/ai/history/00000000-0000-0000-0000-000000000000/messages/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ===================================================================
# Throttle Tests
# ===================================================================

class AIThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = _make_user()
        self.client = APIClient()

    @patch('ai.views.AIService')
    def test_ai_chat_throttle(self, MockAIService):
        mock_service = MockAIService.return_value
        mock_service.ask.return_value = {'conversation_id': '123', 'answer': 'Hi'}
        self.client.credentials(**_auth_header(self.user))

        for _ in range(20):
            response = self.client.post('/api/v1/ai/chat/', {'message': 'Hello'})
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post('/api/v1/ai/chat/', {'message': 'Hello'})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ===================================================================
# Model Tests
# ===================================================================

class AIModelTests(TestCase):
    def test_conversation_str(self):
        user = _make_user()
        conv = AIConversation.objects.create(user=user, title='Test Chat')
        self.assertIn('Test Chat', str(conv))
        self.assertIn(user.email, str(conv))

    def test_message_str(self):
        user = _make_user()
        conv = AIConversation.objects.create(user=user, title='Test')
        msg = AIMessage.objects.create(conversation=conv, role=AIMessage.Role.USER, content='Hello world')
        self.assertIn('Hello world', str(msg))