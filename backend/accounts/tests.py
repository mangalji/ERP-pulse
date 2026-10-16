from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from common.throttles import (
    LoginPasswordEmailThrottle,
    LoginPasswordIPThrottle,
)
from accounts.models import User

class AuthenticationSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)

        csrf_response = self.client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.json()["data"]["csrf_token"]
        self.client.credentials(HTTP_X_CSRFTOKEN=csrf_token)

        self.user = User.objects.create_user(
            email="security-test@example.com",
            password="StrongPassword@123",
            first_name="Security",
            last_name="Test",
            is_active=True,
            is_email_verified=True,
        )

    @patch("accounts.views.audit_service.log")
    @patch("accounts.views.authentication_service.verify_login_otp")
    def test_login_otp_response_does_not_expose_refresh_token(
        self,
        verify_login_otp,
        audit_log,
    ):
        verify_login_otp.return_value = self.user

        response = self.client.post(
            "/api/v1/auth/login/verify-otp/",
            {
                "email": self.user.email,
                "otp_code": "123456",
                "challenge": "test-challenge",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()["data"]
        self.assertIn("access", payload)
        self.assertIn("user", payload)
        self.assertNotIn("refresh", payload)

        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    @patch(
        "accounts.views.password_verified_login_challenge.issue",
        return_value="test-challenge",
    )
    @patch("accounts.views.authentication_service.login")
    def test_password_login_is_throttled_by_email_and_ip(
        self,
        login,
        issue_challenge,
    ):
        login.return_value = self.user

        request_data = {
            "email": self.user.email,
            "password": "StrongPassword@123",
        }

        one_attempt_rates = {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "login_password_ip": "1/min",
            "login_password_email": "1/min",
        }

        with (
            patch.object(
                LoginPasswordIPThrottle,
                "THROTTLE_RATES",
                one_attempt_rates,
            ),
            patch.object(
                LoginPasswordEmailThrottle,
                "THROTTLE_RATES",
                one_attempt_rates,
            ),
        ):
            first_response = self.client.post(
                "/api/v1/auth/login/",
                request_data,
                format="json",
            )
            second_response = self.client.post(
                "/api/v1/auth/login/",
                request_data,
                format="json",
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)

    def test_refresh_cookie_request_requires_csrf_token(self):
        client_without_csrf = APIClient(enforce_csrf_checks=True)
        client_without_csrf.cookies["refresh_token"] = "invalid-token"

        response = client_without_csrf.post(
            "/api/v1/auth/token/refresh/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403)