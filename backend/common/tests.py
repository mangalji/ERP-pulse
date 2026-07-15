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
from rest_framework.test import APICestCase, APIClient

from common.exception_handler import standard_exception_handler, _extract_message
from common.services.email_service import send_email
from common.throttles import (
    AIChatThrottle,
    DashboardThrottle,
    LoginOTPThrottle,
    NetSuiteSyncThrottle,
    RegisterOTPThrottle,
    _SettingsRateThrottleMixin,
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
    @patch('common.services.email_service.send_mail')
    def test_send_email_success(self, mock_send_mail):
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


# ===================================================================
# Throttle Tests
# ===================================================================

class ThrottleTests(TestCase):
    def test_settings_rate_throttle_mixin_default(self):
        throttle = _SettingsRateThrottleMixin()
        throttle.setting_name = None
        # Should fall back to parent rate
        self.assertIsNotNone(throttle.rate)

    @override_settings(THROTTLE_LOGIN_OTP='10/min')
    def test_login_otp_throttle_rate(self):
        throttle = LoginOTPThrottle()
        self.assertEqual(throttle.rate, '10/min')

    @override_settings(THROTTLE_REGISTER_OTP='5/min')
    def test_register_otp_throttle_rate(self):
        throttle = RegisterOTPThrottle()
        self.assertEqual(throttle.rate, '5/min')

    @override_settings(THROTTLE_AI_CHAT='20/min')
    def test_ai_chat_throttle_rate(self):
        throttle = AIChatThrottle()
        self.assertEqual(throttle.rate, '20/min')

    @override_settings(THROTTLE_DASHBOARD='120/min')
    def test_dashboard_throttle_rate(self):
        throttle = DashboardThrottle()
        self.assertEqual(throttle.rate, '120/min')

    @override_settings(THROTTLE_NETSUITE_SYNC='30/min')
    def test_netsuite_sync_throttle_rate(self):
        throttle = NetSuiteSyncThrottle()
        self.assertEqual(throttle.rate, '30/min')


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
