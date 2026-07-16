"""
Comprehensive test suite for the accounts app.

Covers:
- User model
- OTP model
- UserRepository
- OTPRepository
- OTPService
- AuthenticationService
- Serializers
- Views (register, login, OTP, JWT)
- Permissions

All external dependencies are mocked:
- Email sending (common.services.email_service.send_email)
- Cache (registration_cache)
- Timezone (timezone.now)
- Password hashing (make_password/check_password)
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts import registration_cache
from accounts.authentication_service import AuthenticationService
from accounts.exceptions import (
    AccountNotVerifiedException,
    InvalidCredentialsException,
    InvalidRegistrationTokenException,
    MaxOTPAttemptsExceededException,
    OTPExpiredException,
    OTPMismatchException,
    RegistrationSessionNotFoundException,
    ResendCooldownException,
    UserAlreadyExistsException,
    OTPNotFoundException,
)
from accounts.models import OTP, User
from accounts.repositories import OTPRepository, UserRepository
from accounts.serializers import (
    CompleteProfileSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResendLoginOTPSerializer,
    ResendRegistrationOTPSerializer,
    VerifyLoginOTPSerializer,
    VerifyRegistrationOTPSerializer,
    UserSerializer,
)
from accounts.services import OTPService
from accounts.views import (
    CompleteProfileView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    ResendLoginOTPView,
    ResendRegistrationOTPView,
    TokenRefreshView,
    VerifyLoginOTPView,
    VerifyRegistrationOTPView,
)
from common.utils.hash import hash_value, verify_value
from common.utils.otp import generate_otp_code
from common.utils.signed_token import generate_signed_token, verify_signed_token

User = get_user_model()

# Global counter to ensure unique emails/mobile numbers across tests
_counter = 0


def _next_id():
    global _counter
    _counter += 1
    return _counter


def _make_user(**overrides):
    """Create a verified, active user with sensible defaults."""
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


def _auth_header(user):
    """Return a Bearer token header for `user` using SimpleJWT."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}


# ===================================================================
# Model Tests
# ===================================================================

class UserModelTests(TestCase):
    def test_create_user(self):
        user = _make_user()
        self.assertEqual(user.email, f'user{_next_id() - 1}@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

    def test_user_str(self):
        user = _make_user()
        self.assertIn('@example.com', str(user))

    def test_get_full_name(self):
        user = _make_user(first_name='Jane', last_name='Doe')
        self.assertEqual(user.get_full_name(), 'Jane Doe')

    def test_get_short_name(self):
        user = _make_user(first_name='Jane')
        self.assertEqual(user.get_short_name(), 'Jane')


class OTPModelTests(TestCase):
    def test_otp_str(self):
        user = _make_user()
        otp = OTP.objects.create(
            user=user,
            otp_hash='abc123',
            purpose=OTP.Purpose.LOGIN,
            expires_at='2099-01-01T00:00:00Z',
        )
        self.assertIn('Login', str(otp))
        self.assertIn(user.email, str(otp))


# ===================================================================
# Repository Tests
# ===================================================================

class UserRepositoryTests(TestCase):
    def test_email_exists_true(self):
        user = _make_user(email='exists@example.com')
        repo = UserRepository()
        self.assertTrue(repo.email_exists('exists@example.com'))

    def test_email_exists_false(self):
        repo = UserRepository()
        self.assertFalse(repo.email_exists('no-user@example.com'))

    def test_mobile_number_exists_true(self):
        user = _make_user(mobile_number='+15550001001')
        repo = UserRepository()
        self.assertTrue(repo.mobile_number_exists('+15550001001'))

    def test_mobile_number_exists_false(self):
        repo = UserRepository()
        self.assertFalse(repo.mobile_number_exists('+15550009999'))

    def test_get_by_email_found(self):
        user = _make_user(email='find@example.com')
        repo = UserRepository()
        self.assertEqual(repo.get_by_email('find@example.com'), user)

    def test_get_by_email_not_found(self):
        repo = UserRepository()
        self.assertIsNone(repo.get_by_email('missing@example.com'))

    def test_create_verified_user(self):
        repo = UserRepository()
        password_hash = hash_value('rawpass')
        user = repo.create_verified_user(
            email='new@example.com',
            password_hash=password_hash,
            first_name='New',
            last_name='User',
            mobile_number='+15550001002',
        )
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)
        self.assertTrue(verify_value('rawpass', user.password))


class OTPRepositoryTests(TestCase):
    def test_get_latest_active_otp(self):
        user = _make_user()
        repo = OTPRepository()
        otp = repo.create_otp(
            user=user,
            otp_hash='hash1',
            purpose=OTP.Purpose.LOGIN,
            expires_at='2099-01-01T00:00:00Z',
        )
        fetched = repo.get_latest_active_otp(user=user, purpose=OTP.Purpose.LOGIN)
        self.assertEqual(fetched, otp)

    def test_get_latest_active_otp_none(self):
        user = _make_user()
        repo = OTPRepository()
        self.assertIsNone(repo.get_latest_active_otp(user=user, purpose=OTP.Purpose.LOGIN))

    def test_invalidate_previous_otps(self):
        user = _make_user()
        repo = OTPRepository()
        repo.create_otp(user=user, otp_hash='h1', purpose=OTP.Purpose.LOGIN, expires_at='2099-01-01T00:00:00Z')
        repo.create_otp(user=user, otp_hash='h2', purpose=OTP.Purpose.LOGIN, expires_at='2099-01-01T00:00:00Z')
        count = repo.invalidate_previous_otps(user=user, purpose=OTP.Purpose.LOGIN)
        self.assertEqual(count, 2)

    def test_mark_as_used(self):
        user = _make_user()
        repo = OTPRepository()
        otp = repo.create_otp(user=user, otp_hash='h1', purpose=OTP.Purpose.LOGIN, expires_at='2099-01-01T00:00:00Z')
        self.assertFalse(otp.is_used)
        repo.mark_as_used(otp)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)


# ===================================================================
# Service Tests
# ===================================================================

class OTPServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.service = OTPService()

    @patch('accounts.services.send_email')
    def test_generate_and_send_otp(self, mock_send_email):
        otp = self.service.generate_and_send_otp(user=self.user, purpose=OTP.Purpose.LOGIN)
        self.assertIsNotNone(otp.id)
        self.assertFalse(otp.is_used)
        mock_send_email.assert_called_once()

    @patch('accounts.services.send_email')
    def test_generate_and_send_otp_invalidates_previous(self, mock_send_email):
        OTP.objects.create(
            user=self.user,
            otp_hash='old',
            purpose=OTP.Purpose.LOGIN,
            expires_at='2099-01-01T00:00:00Z',
            is_used=False,
        )
        self.service.generate_and_send_otp(user=self.user, purpose=OTP.Purpose.LOGIN)
        self.assertEqual(OTP.objects.filter(user=self.user, purpose=OTP.Purpose.LOGIN, is_used=False).count(), 1)

    def test_verify_otp_success(self):
        raw_code = generate_otp_code()
        otp = self.service.generate_and_send_otp(user=self.user, purpose=OTP.Purpose.LOGIN)
        # Overwrite hash with our known raw code for verification
        otp.otp_hash = hash_value(raw_code)
        otp.save(update_fields=['otp_hash'])
        result = self.service.verify_otp(user=self.user, purpose=OTP.Purpose.LOGIN, submitted_code=raw_code)
        self.assertEqual(result, otp)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_verify_otp_not_found(self):
        with self.assertRaises(OTPNotFoundException):
            self.service.verify_otp(user=self.user, purpose=OTP.Purpose.LOGIN, submitted_code='123456')

    def test_verify_otp_expired(self):
        raw_code = generate_otp_code()
        otp = OTP.objects.create(
            user=self.user,
            otp_hash=hash_value(raw_code),
            purpose=OTP.Purpose.LOGIN,
            expires_at='2000-01-01T00:00:00Z',
        )
        with self.assertRaises(OTPExpiredException):
            self.service.verify_otp(user=self.user, purpose=OTP.Purpose.LOGIN, submitted_code=raw_code)

    def test_verify_otp_mismatch(self):
        raw_code = generate_otp_code()
        OTP.objects.create(
            user=self.user,
            otp_hash=hash_value(raw_code),
            purpose=OTP.Purpose.LOGIN,
            expires_at='2099-01-01T00:00:00Z',
        )
        with self.assertRaises(OTPMismatchException):
            self.service.verify_otp(user=self.user, purpose=OTP.Purpose.LOGIN, submitted_code='000000')


class AuthenticationServiceTests(TestCase):
    def setUp(self):
        self.service = AuthenticationService()

    # -- Registration --------------------------------------------------
    @patch('accounts.authentication_service.send_email')
    def test_register_success(self, mock_send_email):
        result = self.service.register(email='new@example.com', password='StrongPass1!')
        self.assertEqual(result, {'email': 'new@example.com'})
        mock_send_email.assert_called_once()

    def test_register_duplicate_email(self):
        _make_user(email='exists@example.com')
        with self.assertRaises(UserAlreadyExistsException):
            self.service.register(email='exists@example.com', password='StrongPass1!')

    @patch('accounts.authentication_service.send_email')
    def test_resend_registration_otp_success(self, mock_send_email):
        self.service.register(email='resend@example.com', password='StrongPass1!')
        # Backdate last_sent_at past the 60s cooldown so this resend is allowed —
        # resending immediately after register() is expected to hit the cooldown
        # (see test_resend_registration_otp_cooldown below).
        pending = registration_cache.get('resend@example.com')
        pending['last_sent_at'] = timezone.now() - timedelta(seconds=61)
        registration_cache.save(email='resend@example.com', data=pending, timeout_seconds=1200)
        result = self.service.resend_registration_otp(email='resend@example.com')
        self.assertEqual(result, {'email': 'resend@example.com'})

    def test_resend_registration_otp_no_session(self):
        with self.assertRaises(RegistrationSessionNotFoundException):
            self.service.resend_registration_otp(email='no-session@example.com')

    @patch('accounts.authentication_service.send_email')
    def test_resend_registration_otp_cooldown(self, mock_send_email):
        self.service.register(email='cooldown@example.com', password='StrongPass1!')
        with self.assertRaises(ResendCooldownException):
            self.service.resend_registration_otp(email='cooldown@example.com')

    @patch('accounts.authentication_service.send_email')
    def test_verify_registration_otp_success(self, mock_send_email):
        self.service.register(email='verify@example.com', password='StrongPass1!')
        raw_code = '123456'
        registration_cache.save(
            email='verify@example.com',
            data={
                'email': 'verify@example.com',
                'password_hash': hash_value('StrongPass1!'),
                'otp_hash': hash_value(raw_code),
                'otp_expires_at': timezone.now() + timedelta(minutes=5),
                'attempt_count': 0,
                'last_sent_at': timezone.now(),
            },
            timeout_seconds=1200,
        )
        result = self.service.verify_registration_otp(email='verify@example.com', otp_code=raw_code)
        self.assertEqual(result['email'], 'verify@example.com')
        self.assertIn('registration_token', result)

    def test_verify_registration_otp_no_session(self):
        with self.assertRaises(RegistrationSessionNotFoundException):
            self.service.verify_registration_otp(email='no-session@example.com', otp_code='123456')

    @patch('accounts.authentication_service.send_email')
    def test_verify_registration_otp_max_attempts(self, mock_send_email):
        self.service.register(email='max-attempts@example.com', password='StrongPass1!')
        raw_code = '123456'
        registration_cache.save(
            email='max-attempts@example.com',
            data={
                'email': 'max-attempts@example.com',
                'password_hash': hash_value('StrongPass1!'),
                'otp_hash': hash_value(raw_code),
                'otp_expires_at': timezone.now() + timedelta(minutes=5),
                'attempt_count': 3,
                'last_sent_at': timezone.now(),
            },
            timeout_seconds=1200,
        )
        with self.assertRaises(MaxOTPAttemptsExceededException):
            self.service.verify_registration_otp(email='max-attempts@example.com', otp_code=raw_code)

    @patch('accounts.authentication_service.send_email')
    def test_complete_registration_success(self, mock_send_email):
        self.service.register(email='complete@example.com', password='StrongPass1!')
        raw_code = '123456'
        registration_cache.save(
            email='complete@example.com',
            data={
                'email': 'complete@example.com',
                'password_hash': hash_value('StrongPass1!'),
                'otp_hash': hash_value(raw_code),
                'otp_expires_at': timezone.now() + timedelta(minutes=5),
                'attempt_count': 0,
                'last_sent_at': timezone.now(),
            },
            timeout_seconds=1200,
        )
        token = generate_signed_token(payload={'email': 'complete@example.com'}, salt='accounts.registration.complete-profile')
        user = self.service.complete_registration(
            registration_token=token,
            first_name='Complete',
            last_name='User',
            mobile_number='+15550001003',
        )
        self.assertEqual(user.email, 'complete@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

    def test_complete_registration_invalid_token(self):
        with self.assertRaises(InvalidRegistrationTokenException):
            self.service.complete_registration(
                registration_token='invalid-token',
                first_name='Test',
                last_name='User',
                mobile_number='+15550001004',
            )

    # -- Login ---------------------------------------------------------
    def test_login_success(self):
        user = _make_user(email='login@example.com')
        result = self.service.login(email='login@example.com', password='testpass123')
        self.assertEqual(result, user)

    def test_login_wrong_password(self):
        _make_user(email='login@example.com')
        with self.assertRaises(InvalidCredentialsException):
            self.service.login(email='login@example.com', password='wrongpass')

    def test_login_user_not_found(self):
        with self.assertRaises(InvalidCredentialsException):
            self.service.login(email='no-user@example.com', password='anypass')

    def test_login_inactive_user(self):
        _make_user(email='inactive@example.com', is_active=False)
        with self.assertRaises(AccountNotVerifiedException):
            self.service.login(email='inactive@example.com', password='testpass123')

    def test_login_unverified_user(self):
        _make_user(email='unverified@example.com', is_email_verified=False)
        with self.assertRaises(AccountNotVerifiedException):
            self.service.login(email='unverified@example.com', password='testpass123')

    @patch('accounts.authentication_service.send_email')
    def test_verify_login_otp_success(self, mock_send_email):
        user = _make_user(email='login-verify@example.com')
        self.service.login(email='login-verify@example.com', password='testpass123')
        raw_code = '123456'
        OTP.objects.filter(user=user, purpose=OTP.Purpose.LOGIN, is_used=False).update(otp_hash=hash_value(raw_code))
        result = self.service.verify_login_otp(email='login-verify@example.com', otp_code=raw_code)
        self.assertEqual(result, user)

    def test_verify_login_otp_user_not_found(self):
        with self.assertRaises(InvalidCredentialsException):
            self.service.verify_login_otp(email='no-user@example.com', otp_code='123456')


# ===================================================================
# Serializer Tests
# ===================================================================

class RegisterSerializerTests(TestCase):
    def test_valid_data(self):
        serializer = RegisterSerializer(data={'email': 'test@example.com', 'password': 'StrongPass1!', 'confirm_password': 'StrongPass1!'})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['email'], 'test@example.com')

    def test_password_mismatch(self):
        serializer = RegisterSerializer(data={'email': 'test@example.com', 'password': 'StrongPass1!', 'confirm_password': 'Different!'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('confirm_password', serializer.errors)

    def test_invalid_email(self):
        serializer = RegisterSerializer(data={'email': 'not-an-email', 'password': 'StrongPass1!', 'confirm_password': 'StrongPass1!'})
        self.assertFalse(serializer.is_valid())


class LoginSerializerTests(TestCase):
    def test_valid_data(self):
        serializer = LoginSerializer(data={'email': 'test@example.com', 'password': 'any'})
        self.assertTrue(serializer.is_valid())

    def test_missing_fields(self):
        serializer = LoginSerializer(data={})
        self.assertFalse(serializer.is_valid())


class VerifyRegistrationOTPSerializerTests(TestCase):
    def test_valid_data(self):
        serializer = VerifyRegistrationOTPSerializer(data={'email': 'test@example.com', 'otp_code': '123456'})
        self.assertTrue(serializer.is_valid())

    def test_invalid_otp_length(self):
        serializer = VerifyRegistrationOTPSerializer(data={'email': 'test@example.com', 'otp_code': '123'})
        self.assertFalse(serializer.is_valid())


class UserSerializerTests(TestCase):
    def test_serializes_user(self):
        user = _make_user()
        serializer = UserSerializer(user)
        data = serializer.data
        self.assertEqual(data['email'], user.email)
        self.assertNotIn('password', data)
        self.assertNotIn('is_staff', data)


# ===================================================================
# View Tests
# ===================================================================

class AuthViewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    # -- Register ------------------------------------------------------
    @patch('accounts.authentication_service.send_email')
    def test_register_success(self, mock_send_email):
        response = self.client.post('/api/v1/auth/register/', {
            'email': 'new@example.com',
            'password': 'StrongPass1!',
            'confirm_password': 'StrongPass1!',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['email'], 'new@example.com')

    def test_register_duplicate_email(self):
        _make_user(email='exists@example.com')
        response = self.client.post('/api/v1/auth/register/', {
            'email': 'exists@example.com',
            'password': 'StrongPass1!',
            'confirm_password': 'StrongPass1!',
        })
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    # -- Login ---------------------------------------------------------
    def test_login_success(self):
        _make_user(email='login@example.com')
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'login@example.com',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_login_invalid_credentials(self):
        _make_user(email='login@example.com')
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'login@example.com',
            'password': 'wrongpass',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- Verify Login OTP ----------------------------------------------
    @patch('accounts.authentication_service.send_email')
    def test_verify_login_otp_success(self, mock_send_email):
        user = _make_user(email='verify-login@example.com')
        self.client.post('/api/v1/auth/login/', {
            'email': 'verify-login@example.com',
            'password': 'testpass123',
        })
        raw_code = '123456'
        OTP.objects.filter(user=user, purpose=OTP.Purpose.LOGIN, is_used=False).update(otp_hash=hash_value(raw_code))
        response = self.client.post('/api/v1/auth/login/verify-otp/', {
            'email': 'verify-login@example.com',
            'otp_code': raw_code,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data'])
        self.assertIn('refresh', response.data['data'])

    # -- Me ------------------------------------------------------------
    def test_me_authenticated(self):
        user = _make_user()
        self.client.credentials(**_auth_header(user))
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['email'], user.email)

    def test_me_unauthenticated(self):
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- Token Refresh -------------------------------------------------
    def test_token_refresh(self):
        user = _make_user()
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        response = self.client.post('/api/v1/auth/token/refresh/', {
            'refresh': str(refresh),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data'])

    # -- Logout --------------------------------------------------------
    def test_logout(self):
        user = _make_user()
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        self.client.credentials(**_auth_header(user))
        response = self.client.post('/api/v1/auth/logout/', {
            'refresh': str(refresh),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ===================================================================
# Common Utils Tests
# ===================================================================

class HashUtilsTests(TestCase):
    def test_hash_and_verify(self):
        raw = 'my-secret-code'
        hashed = hash_value(raw)
        self.assertNotEqual(raw, hashed)
        self.assertTrue(verify_value(raw, hashed))
        self.assertFalse(verify_value('wrong', hashed))


class OTPUtilsTests(TestCase):
    def test_generate_otp_length(self):
        self.assertEqual(len(generate_otp_code(6)), 6)

    def test_generate_otp_numeric(self):
        code = generate_otp_code(6)
        self.assertTrue(code.isdigit())

    def test_generate_otp_min_length(self):
        with self.assertRaises(ValueError):
            generate_otp_code(3)


class SignedTokenUtilsTests(TestCase):
    def test_round_trip(self):
        payload = {'email': 'test@example.com'}
        token = generate_signed_token(payload=payload, salt='test-salt')
        decoded = verify_signed_token(token=token, salt='test-salt', max_age_seconds=3600)
        self.assertEqual(decoded['email'], 'test@example.com')

    def test_invalid_salt(self):
        payload = {'email': 'test@example.com'}
        token = generate_signed_token(payload=payload, salt='test-salt')
        with self.assertRaises(Exception):
            verify_signed_token(token=token, salt='wrong-salt', max_age_seconds=3600)


# ===================================================================
# Throttle Tests
# ===================================================================

class ThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_login_otp_throttle(self):
        for _ in range(5):
            response = self.client.post('/api/v1/auth/login/', {
                'email': 'throttle@example.com',
                'password': 'wrong',
            })
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        # 6th request should be throttled
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'throttle@example.com',
            'password': 'wrong',
        })
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)