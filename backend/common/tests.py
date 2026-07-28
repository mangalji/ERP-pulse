"""
Comprehensive test suite for the common app.

Covers:
- Exception handler
- Response builder
- Email service
- Throttle classes
- Hash utilities
- OTP utilities
- Signed token utilities
- Datetime utilities
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from common.exception_handler import standard_exception_handler, _extract_message
from common.services.email_service import send_email
from common.throttles import (
    AIChatThrottle,
    DashboardThrottle,
    LoginOTPThrottle,
    NetSuiteSyncThrottle,
    RegisterOTPThrottle,
)
from common.utils.datetime import calculate_expiry, is_expired
from common.utils.hash import hash_value, verify_value
from common.utils.otp import generate_otp_code
from common.utils.response import success_response
from common.utils.signed_token import generate_signed_token, verify_signed_token


# ===================================================================
# Response Builder Tests
# ===================================================================

class ResponseBuilderTests(TestCase):
    def test_success_response_default(self):
        response = success_response(message='OK', data={'key': 'value'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['success'], True)
        self.assertEqual(response.data['message'], 'OK')
        self.assertEqual(response.data['data'], {'key': 'value'})

    def test_success_response_custom_status(self):
        response = success_response(message='Created', data={'id': 1}, status_code=status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_success_response_no_data(self):
        response = success_response(message='Done')
        self.assertEqual(response.data['data'], {})


# ===================================================================
# Exception Handler Tests
# ===================================================================

class ExceptionHandlerTests(TestCase):
    def test_drf_validation_error(self):
        from rest_framework.exceptions import ValidationError
        exc = ValidationError({'field': ['This field is required.']})
        context = {'view': MagicMock()}

        response = standard_exception_handler(exc, context)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('errors', response.data)

    def test_domain_exception_with_status_code(self):
        class TestException(Exception):
            status_code = status.HTTP_418_IM_A_TEAPOT

        exc = TestException('I am a teapot')
        context = {'view': MagicMock()}

        response = standard_exception_handler(exc, context)
        self.assertEqual(response.status_code, status.HTTP_418_IM_A_TEAPOT)
        self.assertEqual(response.data['message'], 'I am a teapot')

    def test_unhandled_exception(self):
        exc = Exception('Something broke')
        context = {'view': MagicMock()}

        response = standard_exception_handler(exc, context)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['message'], 'An unexpected error occurred.')

    def test_extract_message_from_dict(self):
        self.assertEqual(_extract_message({'field': 'error'}), 'error')

    def test_extract_message_from_list(self):
        self.assertEqual(_extract_message(['first error']), 'first error')

    def test_extract_message_from_string(self):
        self.assertEqual(_extract_message('simple error'), 'simple error')


# ===================================================================
# Email Service Tests
# ===================================================================

class EmailServiceTests(TestCase):
    @override_settings(BREVO_API_KEY='')
    @patch('common.services.email_service.send_mail')
    def test_send_email_success_smtp_path(self, mock_send_mail):
        """BREVO_API_KEY unset -> falls back to Django's send_mail (SMTP/console)."""
        mock_send_mail.return_value = 1
        result = send_email(
            subject='Test',
            message='Hello',
            recipient_list=['test@example.com'],
        )
        self.assertEqual(result, 1)
        mock_send_mail.assert_called_once()

    def test_send_email_empty_recipient_list(self):
        with self.assertRaises(ValueError):
            send_email(
                subject='Test',
                message='Hello',
                recipient_list=[],
            )

    @override_settings(BREVO_API_KEY='test-brevo-key', DEFAULT_FROM_NAME='ERP Pulse')
    @patch('common.services.email_service.requests.post')
    def test_send_email_success_brevo_path(self, mock_post):
        """
        BREVO_API_KEY set -> sends via Brevo's HTTP API instead of
        Django's send_mail, so it goes out over HTTPS (port 443)
        rather than an SMTP port that hosts like Render's free tier
        block.
        """
        mock_post.return_value = MagicMock(status_code=201, text='{"messageId": "abc"}')

        result = send_email(
            subject='Your OTP',
            message='Code: 123456',
            recipient_list=['user@example.com'],
        )

        self.assertEqual(result, 1)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs['headers']['api-key'], 'test-brevo-key')
        self.assertEqual(call_kwargs['json']['to'], [{'email': 'user@example.com'}])
        self.assertEqual(call_kwargs['json']['subject'], 'Your OTP')
        self.assertEqual(call_kwargs['json']['sender']['name'], 'ERP Pulse')

    @override_settings(BREVO_API_KEY='test-brevo-key')
    @patch('common.services.email_service.requests.post')
    def test_send_email_brevo_error_response_raises(self, mock_post):
        """A non-2xx from Brevo must propagate as a failure, not be treated as success."""
        mock_post.return_value = MagicMock(status_code=401, text='{"message": "invalid api key"}')

        with self.assertRaises(Exception):
            send_email(
                subject='Test',
                message='Hello',
                recipient_list=['test@example.com'],
            )

    @override_settings(BREVO_API_KEY='test-brevo-key')
    @patch('common.services.email_service.requests.post')
    def test_send_email_brevo_error_fail_silently(self, mock_post):
        """fail_silently=True must swallow a Brevo failure and return 0, not raise."""
        mock_post.side_effect = ConnectionError('network unreachable')

        result = send_email(
            subject='Test',
            message='Hello',
            recipient_list=['test@example.com'],
            fail_silently=True,
        )
        self.assertEqual(result, 0)


# ===================================================================
# Throttle Tests
# ===================================================================

class ThrottleTests(TestCase):
    """
    Rates are driven by REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] per scope
    (each entry itself sourced from settings.py via python-decouple config()
    calls), which is DRF's own supported mechanism for exactly this. Each
    throttle class just needs the correct `scope` wired up.
    """

    def test_login_otp_throttle_scope(self):
        throttle = LoginOTPThrottle()
        self.assertEqual(throttle.scope, 'login_otp')
        self.assertIsNotNone(throttle.rate)

    def test_register_otp_throttle_scope(self):
        throttle = RegisterOTPThrottle()
        self.assertEqual(throttle.scope, 'register_otp')
        self.assertIsNotNone(throttle.rate)

    def test_ai_chat_throttle_scope(self):
        throttle = AIChatThrottle()
        self.assertEqual(throttle.scope, 'ai_chat')
        self.assertIsNotNone(throttle.rate)

    def test_dashboard_throttle_scope(self):
        throttle = DashboardThrottle()
        self.assertEqual(throttle.scope, 'dashboard')
        self.assertIsNotNone(throttle.rate)

    def test_netsuite_sync_throttle_scope(self):
        throttle = NetSuiteSyncThrottle()
        self.assertEqual(throttle.scope, 'netsuite_sync')
        self.assertIsNotNone(throttle.rate)

    def test_login_otp_throttle_rate_configurable(self):
        # NOTE: DRF binds `SimpleRateThrottle.THROTTLE_RATES` to
        # api_settings.DEFAULT_THROTTLE_RATES as a class attribute at import
        # time (see rest_framework/throttling.py), so override_settings on
        # REST_FRAMEWORK alone does not refresh it for already-imported
        # throttle classes. Patch the class attribute directly to prove the
        # scope-based lookup honors whatever settings.py provides.
        from rest_framework.throttling import SimpleRateThrottle

        original_rates = SimpleRateThrottle.THROTTLE_RATES
        patched_rates = dict(original_rates)
        patched_rates['login_otp'] = '10/min'
        SimpleRateThrottle.THROTTLE_RATES = patched_rates
        try:
            throttle = LoginOTPThrottle()
            self.assertEqual(throttle.rate, '10/min')
        finally:
            SimpleRateThrottle.THROTTLE_RATES = original_rates


class ThrottleBehaviorTests(APITestCase):
    """
    Drives real requests through a live, throttled endpoint end-to-end
    (URL -> View -> throttle check) instead of only inspecting throttle
    class attributes, to prove throttling actually engages and returns
    the standard error envelope — not just that the scope/rate are wired.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def _patch_rate(self, scope: str, rate: str):
        from rest_framework.throttling import SimpleRateThrottle

        original_rates = SimpleRateThrottle.THROTTLE_RATES
        patched_rates = dict(original_rates)
        patched_rates[scope] = rate
        SimpleRateThrottle.THROTTLE_RATES = patched_rates
        self.addCleanup(setattr, SimpleRateThrottle, 'THROTTLE_RATES', original_rates)

    def test_register_endpoint_returns_429_once_limit_exceeded(self):
        from django.urls import reverse

        self._patch_rate('register_otp', '2/min')
        url = reverse('register')
        payload = {
            'email': 'throttle-test@example.com',
            'password': 'StrongPass123!',
            'confirm_password': 'StrongPass123!',
        }

        # Throttling is checked before the view body runs, so the first two
        # requests count toward the limit regardless of what they return.
        self.client.post(url, payload)
        self.client.post(url, payload)
        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertFalse(response.data['success'])
        self.assertIn('message', response.data)

    def test_register_endpoint_allows_requests_within_limit(self):
        from django.urls import reverse

        self._patch_rate('register_otp', '5/min')
        url = reverse('register')
        payload = {
            'email': 'within-limit@example.com',
            'password': 'StrongPass123!',
            'confirm_password': 'StrongPass123!',
        }

        response = self.client.post(url, payload)
        self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ===================================================================
# Hash Utils Tests
# ===================================================================

class HashUtilsTests(TestCase):
    def test_hash_value(self):
        hashed = hash_value('secret')
        self.assertNotEqual(hashed, 'secret')
        self.assertTrue(verify_value('secret', hashed))

    def test_verify_value_correct(self):
        hashed = hash_value('password123')
        self.assertTrue(verify_value('password123', hashed))

    def test_verify_value_incorrect(self):
        hashed = hash_value('password123')
        self.assertFalse(verify_value('wrong', hashed))


# ===================================================================
# OTP Utils Tests
# ===================================================================

class OTPUtilsTests(TestCase):
    def test_generate_otp_code_length(self):
        self.assertEqual(len(generate_otp_code(6)), 6)

    def test_generate_otp_code_numeric(self):
        code = generate_otp_code(6)
        self.assertTrue(code.isdigit())

    def test_generate_otp_code_min_length(self):
        with self.assertRaises(ValueError):
            generate_otp_code(3)

    def test_generate_otp_code_default_length(self):
        code = generate_otp_code()
        self.assertEqual(len(code), 6)


# ===================================================================
# Signed Token Utils Tests
# ===================================================================

class SignedTokenUtilsTests(TestCase):
    def test_round_trip(self):
        payload = {'user_id': '123'}
        token = generate_signed_token(payload=payload, salt='test-salt')
        decoded = verify_signed_token(token=token, salt='test-salt', max_age_seconds=3600)
        self.assertEqual(decoded['user_id'], '123')

    def test_invalid_salt(self):
        payload = {'user_id': '123'}
        token = generate_signed_token(payload=payload, salt='test-salt')
        with self.assertRaises(Exception):
            verify_signed_token(token=token, salt='wrong-salt', max_age_seconds=3600)


# ===================================================================
# Datetime Utils Tests
# ===================================================================

class DatetimeUtilsTests(TestCase):
    @patch('common.utils.datetime.timezone')
    def test_calculate_expiry(self, mock_timezone):
        from django.utils import timezone as dj_tz
        now = dj_tz.now()
        mock_timezone.now.return_value = now
        expiry = calculate_expiry(minutes=5)
        self.assertGreater(expiry, now)
        self.assertLess(expiry, now + timedelta(minutes=10))

    @patch('common.utils.datetime.timezone')
    def test_is_expired_true(self, mock_timezone):
        from django.utils import timezone as dj_tz
        past = dj_tz.now() - timedelta(hours=1)
        mock_timezone.now.return_value = dj_tz.now()
        self.assertTrue(is_expired(past))

    @patch('common.utils.datetime.timezone')
    def test_is_expired_false(self, mock_timezone):
        from django.utils import timezone as dj_tz
        future = dj_tz.now() + timedelta(hours=1)
        mock_timezone.now.return_value = dj_tz.now()
        self.assertFalse(is_expired(future))