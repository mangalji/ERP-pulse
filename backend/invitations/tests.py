"""Integration tests for the Invitations sprint."""

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Invitation
from .serializers import InvitationSerializer
from .services import invitation_service
from tenancy.models import Company
from rbac.models import Role

User = get_user_model()


def _next_id(counter=[0]):
    counter[0] += 1
    return counter[0]


def _make_user(**overrides):
    n = _next_id()
    defaults = {
        'email': f'agsuite{n}@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'is_active': True,
        'is_email_verified': True,
        'is_staff': True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password('testpass123')
    user.save()
    return user


def _make_superadmin():
    n = _next_id()
    return User.objects.create_superuser(
        email=f'superadmin{n}@example.com',
        password='testpass123',
        is_email_verified=True,
    )


def _auth_header(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    token = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}


def _make_company(**overrides):
    n = _next_id()
    defaults = {
        'name': f'Test Company {n}',
        'code': f'TC{n}',
        'status': Company.Status.TRIAL,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _make_role(**overrides):
    n = _next_id()
    defaults = {
        'name': f'Test Role {n}',
        'is_system': False,
    }
    defaults.update(overrides)
    return Role.objects.create(**defaults)


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': (
            'common.authentication.CookieJWTAuthentication',
            'rest_framework_simplejwt.authentication.JWTAuthentication',
        ),
        'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
        'EXCEPTION_HANDLER': 'common.exception_handler.standard_exception_handler',
        'DEFAULT_THROTTLE_CLASSES': (
            'rest_framework.throttling.AnonRateThrottle',
            'rest_framework.throttling.UserRateThrottle',
        ),
        'DEFAULT_THROTTLE_RATES': {
            'anon': '1000/min',
            'user': '1000/min',
            'login_otp': '1000/min',
            'register_otp': '1000/min',
            'ai_chat': '1000/min',
            'dashboard': '1000/min',
            'netsuite_sync': '1000/min',
            'health_check': '1000/min',
        },
    }
)
class InvitationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.superadmin = _make_superadmin()
        self.company = _make_company()
        self.role = _make_role()

    def test_create_invitation(self):
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.post('/api/v1/invitations/create/', {
            'email': 'newuser@example.com',
            'company_id': str(self.company.id),
            'role_id': str(self.role.id),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('token', response.data['data'])

    def test_list_invitations(self):
        invitation_service.create_invitation(
            email='user1@example.com',
            company_id=self.company.id,
            created_by=self.superadmin,
        )
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.get('/api/v1/invitations/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['count'], 1)

    def test_validate_token(self):
        invitation = invitation_service.create_invitation(
            email='validate@example.com',
            company_id=self.company.id,
            created_by=self.superadmin,
        )
        response = self.client.get('/api/v1/invitations/validate/', {'token': str(invitation.token)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_accept_invitation(self):
        invitation = invitation_service.create_invitation(
            email='accept@example.com',
            company_id=self.company.id,
            created_by=self.superadmin,
        )
        response = self.client.post('/api/v1/invitations/accept/', {
            'token': str(invitation.token),
            'password': 'newpass123',
            'confirm_password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertTrue(User.objects.filter(email='accept@example.com').exists())

    def test_resend_invitation(self):
        invitation = invitation_service.create_invitation(
            email='resend@example.com',
            company_id=self.company.id,
            created_by=self.superadmin,
        )
        original_expires = invitation.expires_at
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.post(f'/api/v1/invitations/{invitation.id}/resend/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertNotEqual(invitation.expires_at, original_expires)

    def test_expire_old_tokens(self):
        invitation = invitation_service.create_invitation(
            email='expire@example.com',
            company_id=self.company.id,
            created_by=self.superadmin,
        )
        from django.utils import timezone
        from datetime import timedelta
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save(update_fields=['expires_at'])
        
        count = invitation_service.expire_old_tokens()
        self.assertEqual(count, 1)

    def test_duplicate_active_invitation_prevention(self):
        invitation_service.create_invitation(
            email='dup@example.com',
            company_id=self.company.id,
            created_by=self.superadmin,
        )
        with self.assertRaises(ValueError):
            invitation_service.create_invitation(
                email='dup@example.com',
                company_id=self.company.id,
                created_by=self.superadmin,
            )

    def test_forbidden_for_normal_users(self):
        normal_user = _make_user()
        self.client.credentials(**_auth_header(normal_user))
        response = self.client.get('/api/v1/invitations/list/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_accept_invalid_token(self):
        response = self.client.post('/api/v1/invitations/accept/', {
            'token': '00000000-0000-0000-0000-000000000000',
            'password': 'newpass123',
            'confirm_password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
