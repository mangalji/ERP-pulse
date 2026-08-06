"""Integration tests for the Demo Request sprint."""

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import DemoRequest
from .serializers import DemoRequestSerializer
from .services import demo_request_service

User = get_user_model()

_counter = 0


def _next_id():
    global _counter
    _counter += 1
    return _counter


def _make_user(**overrides):
    n = _next_id()
    defaults = {
        "email": f"agsuite{n}@example.com",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_email_verified": True,
        "is_staff": True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("testpass123")
    user.save()
    return user


def _make_superadmin():
    n = _next_id()
    return User.objects.create_superuser(
        email=f"superadmin{n}@example.com",
        password="testpass123",
        is_email_verified=True,
    )


def _auth_header(user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


def _valid_payload(**overrides):
    n = _next_id()
    payload = {
        "company_name": "Acme Corp",
        "contact_person": "Jane Doe",
        "business_email": f"acme{n}@example.com",
        "phone": "+15550001000",
        "industry": "TECHNOLOGY",
        "company_size": "11-50",
        "city": "Bengaluru",
        "country": "India",
        "message": "Interested in a demo.",
    }
    payload.update(overrides)
    return payload


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "common.authentication.CookieJWTAuthentication",
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "EXCEPTION_HANDLER": "common.exception_handler.standard_exception_handler",
        "DEFAULT_THROTTLE_CLASSES": (
            "rest_framework.throttling.AnonRateThrottle",
            "rest_framework.throttling.UserRateThrottle",
        ),
        "DEFAULT_THROTTLE_RATES": {
            "anon": "1000/min",
            "user": "1000/min",
            "login_otp": "1000/min",
            "register_otp": "1000/min",
            "ai_chat": "1000/min",
            "dashboard": "1000/min",
            "netsuite_sync": "1000/min",
            "health_check": "1000/min",
        },
    }
)
class DemoRequestTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.agsuite_user = _make_user()
        self.superadmin = _make_superadmin()

    def test_public_demo_request_creation(self):
        response = self.client.post("/api/v1/demo/submit/", _valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("demo_request_number", response.data["data"])
        self.assertEqual(response.data["data"]["status"], DemoRequest.Status.NEW)

    def test_invalid_email_is_rejected(self):
        payload = _valid_payload(business_email="not-an-email")
        response = self.client.post("/api/v1/demo/submit/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_phone_is_rejected(self):
        payload = _valid_payload(phone="abc")
        response = self.client.post("/api/v1/demo/submit/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_active_request_prevention(self):
        payload = _valid_payload()
        self.client.post("/api/v1/demo/submit/", payload, format="json")
        response = self.client.post("/api/v1/demo/submit/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("business_email", response.data.get("errors", {}))

    def test_serializer_validation(self):
        serializer = DemoRequestSerializer(data=_valid_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

        duplicate_payload = _valid_payload(business_email="dup@example.com")
        demo_request_service.create_request(data=duplicate_payload)
        duplicate_serializer = DemoRequestSerializer(data=duplicate_payload)
        self.assertFalse(duplicate_serializer.is_valid())
        self.assertIn("business_email", duplicate_serializer.errors)

    def test_anonymous_access_allowed_only_for_public_submit(self):
        response = self.client.post("/api/v1/demo/submit/", _valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        forbidden = self.client.get("/api/v1/demo/list/")
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_super_admin_permissions(self):
        demo_request_service.create_request(data=_valid_payload())

        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.get("/api/v1/demo/list/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)

        self.client.credentials(**_auth_header(self.agsuite_user))
        forbidden = self.client.get("/api/v1/demo/list/")
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_sales(self):
        request = demo_request_service.create_request(data=_valid_payload())
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.post(
            f"/api/v1/demo/{request.id}/assign/",
            {"user_id": str(self.agsuite_user.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.assigned_to_id, self.agsuite_user.id)

    def test_approve(self):
        request = demo_request_service.create_request(data=_valid_payload())
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.post(f"/api/v1/demo/{request.id}/approve/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, DemoRequest.Status.APPROVED)

    def test_reject(self):
        request = demo_request_service.create_request(data=_valid_payload())
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.post(f"/api/v1/demo/{request.id}/reject/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, DemoRequest.Status.REJECTED)

    def test_retrieve_request(self):
        request = demo_request_service.create_request(data=_valid_payload())
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.get(f"/api/v1/demo/{request.id}/detail/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["company_name"], request.company_name)

    def test_list_requests(self):
        demo_request_service.create_request(data=_valid_payload())
        demo_request_service.create_request(data=_valid_payload())
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.get("/api/v1/demo/list/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 2)

    def test_forbidden_for_normal_users(self):
        demo_request_service.create_request(data=_valid_payload())
        self.client.credentials(**_auth_header(self.agsuite_user))
        response = self.client.get("/api/v1/demo/list/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_convert_to_company_is_placeholder(self):
        request = demo_request_service.create_request(data=_valid_payload())
        request.status = DemoRequest.Status.APPROVED
        request.save(update_fields=['status'])
        self.client.credentials(**_auth_header(self.superadmin))
        response = self.client.post(f"/api/v1/demo/{request.id}/convert/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('company_id', response.data["data"])
