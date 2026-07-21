from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from monitoring.models import ErrorLog, RequestLog


class HealthCheckViewTests(APITestCase):
    def test_health_check_is_public_and_returns_200(self):
        response = self.client.get(reverse('monitoring-health'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(response.data['data']['status'], ('healthy', 'degraded', 'down'))
        self.assertIn('database', response.data['data']['checks'])

    def test_health_check_reports_database_ok(self):
        response = self.client.get(reverse('monitoring-health'))
        self.assertTrue(response.data['data']['checks']['database']['ok'])


class MonitoringPermissionTests(APITestCase):
    """Errors and API usage are operational data — staff only."""

    def setUp(self):
        self.regular_user = User.objects.create_user(
            email='member@example.com', password='StrongPass123!',
            first_name='Regular', last_name='User', mobile_number='+15550000001',
            is_active=True,
        )
        self.staff_user = User.objects.create_user(
            email='admin@example.com', password='StrongPass123!',
            first_name='Admin', last_name='User', mobile_number='15550000002',
            is_active=True, is_staff=True,
        )

    def test_errors_endpoint_rejects_non_staff(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(reverse('monitoring-errors'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_errors_endpoint_rejects_anonymous(self):
        response = self.client.get(reverse('monitoring-errors'))
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_errors_endpoint_allows_staff(self):
        ErrorLog.objects.create(message='boom', method='GET', path='/api/v1/customers/', status_code=500)
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(reverse('monitoring-errors'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)

    def test_api_usage_endpoint_rejects_non_staff(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(reverse('monitoring-api-usage'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_usage_endpoint_returns_aggregates_for_staff(self):
        RequestLog.objects.create(method='GET', path='/api/v1/customers/', status_code=200, response_time_ms=120)
        RequestLog.objects.create(method='GET', path='/api/v1/customers/', status_code=500, response_time_ms=340)
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(reverse('monitoring-api-usage'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        self.assertEqual(data['total_requests'], 2)
        self.assertEqual(data['error_count'], 1)
        self.assertEqual(data['error_rate'], 0.5)


class RequestMonitoringMiddlewareTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='pulse@example.com', password='StrongPass123!',
            first_name='Pulse', last_name='User', mobile_number='15550000003',
            is_active=True,
        )

    def test_api_request_is_logged(self):
        """Any /api/v1/ request outside /monitoring/ itself gets a RequestLog row."""
        RequestLog.objects.all().delete()
        self.client.get('/api/v1/accounts/does-not-exist/')
        self.assertTrue(RequestLog.objects.filter(path='/api/v1/accounts/does-not-exist/').exists())

    def test_monitoring_endpoints_are_not_self_logged(self):
        """Viewing /monitoring/health/ shouldn't inflate the dashboard's own numbers."""
        RequestLog.objects.all().delete()
        self.client.force_authenticate(user=self.user)
        self.client.get(reverse('monitoring-health'))
        self.assertFalse(RequestLog.objects.filter(path__startswith='/api/v1/monitoring/').exists())