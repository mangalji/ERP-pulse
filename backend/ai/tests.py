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

from django.test import TestCase, override_settings, RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from ai.context_builder import build_context
from ai.exceptions import AIConversationNotFoundException, AIProviderNotConfiguredException, AIProviderRequestException
from ai.models import AIConversation, AIMessage
from ai.prompts import build_system_prompt, build_user_prompt
from ai.repositories import ConversationRepository, MessageRepository
from ai.serializers import AIChatRequestSerializer, AIConversationSerializer, AIMessageSerializer
from ai.services import AIService, NETSUITE_NOT_CONNECTED_ANSWER
from ai.views import ChatView, ConversationHistoryView, ConversationMessagesView


def _make_user(**overrides):
    defaults = {
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'mobile_number': '+1234567890',
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
        context = {
            'netsuite_connected': True,
            'business_context': {'summary': {'total_customers': 10}},
        }
        prompt = build_user_prompt(context=context, message='How many customers?')
        self.assertIn('How many customers?', prompt)
        self.assertIn('Business context:', prompt)

    def test_build_user_prompt_without_context(self):
        context = {'netsuite_connected': False, 'business_context': None}
        prompt = build_user_prompt(context=context, message='How many customers?')
        self.assertIn('How many customers?', prompt)
        self.assertIn('NetSuite is not connected', prompt)


# ===================================================================
# Context Builder Tests
# ===================================================================

class ContextBuilderTests(TestCase):
    def setUp(self):
        self.user = _make_user()

    @patch('ai.context_builder.DashboardService')
    @patch('ai.context_builder.NetSuiteConnectionRepository')
    def test_build_context_connected(self, MockRepo, MockDashboardService):
        mock_repo = MockRepo.return_value
        mock_repo.get_by_user.return_value = MagicMock(is_active=True)

        mock_dashboard = MockDashboardService.return_value
        mock_dashboard.get_summary.return_value = {'total_customers': 10}
        mock_dashboard.get_recent_customers.return_value = []
        mock_dashboard.get_recent_invoices.return_value = []
        mock_dashboard.get_recent_sales_orders.return_value = []

        context = build_context(self.user)
        self.assertTrue(context['netsuite_connected'])
        self.assertIsNotNone(context['business_context'])
        self.assertEqual(context['business_context']['summary']['total_customers'], 10)

    @patch('ai.context_builder.NetSuiteConnectionRepository')
    def test_build_context_not_connected(self, MockRepo):
        mock_repo = MockRepo.return_value
        mock_repo.get_by_user.return_value = None

        context = build_context(self.user)
        self.assertFalse(context['netsuite_connected'])
        self.assertIsNone(context['business_context'])


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
        from ai.providers import OpenAIProvider
        with self.assertRaises(AIProviderNotConfiguredException):
            OpenAIProvider()

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
        from ai.providers import GeminiProvider
        with self.assertRaises(AIProviderNotConfiguredException):
            GeminiProvider()

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
        self.service = AIService()

    @patch('ai.services.AIProviderFactory.create')
    @patch('ai.services.build_context')
    def test_ask_returns_answer(self, mock_build_context, mock_factory):
        mock_build_context.return_value = {
            'netsuite_connected': True,
            'business_context': {},
        }
        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = 'Test answer'
        mock_factory.return_value = mock_provider

        result = self.service.ask(user=self.user, message='Hello')
        self.assertEqual(result['answer'], 'Test answer')
        self.assertIsNotNone(result['conversation_id'])

    @patch('ai.services.build_context')
    def test_ask_returns_disconnected_answer(self, mock_build_context):
        mock_build_context.return_value = {
            'netsuite_connected': False,
            'business_context': None,
        }

        result = self.service.ask(user=self.user, message='Hello')
        self.assertEqual(result['answer'], NETSUITE_NOT_CONNECTED_ANSWER)

    @patch('ai.services.AIProviderFactory.create')
    @patch('ai.services.build_context')
    def test_ask_with_existing_conversation(self, mock_build_context, mock_factory):
        mock_build_context.return_value = {
            'netsuite_connected': True,
            'business_context': {},
        }
        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = 'Follow-up answer'
        mock_factory.return_value = mock_provider

        conversation = AIConversation.objects.create(user=self.user, title='Existing')
        result = self.service.ask(user=self.user, message='Follow-up', conversation_id=str(conversation.id))
        self.assertEqual(result['answer'], 'Follow-up answer')

    def test_ask_invalid_conversation(self):
        with self.assertRaises(AIConversationNotFoundException):
            self.service.ask(user=self.user, message='Hello', conversation_id='00000000-0000-0000-0000-000000000000')

    @patch('ai.services.AIProviderFactory.create')
    @patch('ai.services.build_context')
    def test_ask_saves_messages(self, mock_build_context, mock_factory):
        mock_build_context.return_value = {
            'netsuite_connected': True,
            'business_context': {},
        }
        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = 'Answer'
        mock_factory.return_value = mock_provider

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
