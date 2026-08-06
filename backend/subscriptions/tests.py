"""Tests for subscriptions app."""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from tenancy.models import Company, CompanyModule, Module
from superadmin.models import Plan, CompanyPlan, CompanyPlanStatus
from accounts.models import User
from subscriptions.services import license_service, subscription_service
from subscriptions.utils import LicenseError


def _auth_header(user):
    token = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'}


class SubscriptionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_superuser(
            email='super@test.com',
            password='testpass123',
        )
        self.company = Company.objects.create(
            name='Test Co',
            code='TC',
            status=Company.Status.TRIAL,
        )
        self.plan = Plan.objects.create(
            name='Basic',
            monthly_price=10,
            yearly_price=100,
            max_employees=5,
            max_ocr_documents=10,
            max_storage_gb=5,
        )
        self.module = Module.objects.create(
            name='OCR',
            code='ocr',
            display_name='OCR Module',
        )

    def test_assign_plan(self):
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.post('/api/v1/subscriptions/assign/', {
            'company_id': str(self.company.id),
            'plan_id': str(self.plan.id),
            'status': 'TRIAL',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_my_subscription(self):
        CompanyPlan.objects.create(
            company=self.company,
            plan=self.plan,
            start_date='2024-01-01',
            status=CompanyPlanStatus.ACTIVE,
        )
        user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            company=self.company,
            is_active=True,
            is_email_verified=True,
        )
        self.client.credentials(**_auth_header(user))
        response = self.client.get('/api/v1/subscriptions/my/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])


class LicenseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Co',
            code='TC',
            status=Company.Status.ACTIVE,
        )
        self.module = Module.objects.create(
            name='OCR',
            code='ocr',
            display_name='OCR',
        )
        self.company_module = CompanyModule.objects.create(
            company=self.company,
            module=self.module,
            enabled=True,
            usage_limit=10,
            usage_count=5,
        )

    def test_can_use_module(self):
        self.assertTrue(license_service.can_use_module(self.company, 'ocr'))

    def test_limit_exceeded(self):
        self.company_module.usage_count = 10
        self.company_module.save()
        with self.assertRaises(LicenseError):
            license_service.check_limit(self.company, 'ocr')

    def test_increment_usage(self):
        result = license_service.increment_usage(self.company, 'ocr')
        self.assertEqual(result.usage_count, 6)

