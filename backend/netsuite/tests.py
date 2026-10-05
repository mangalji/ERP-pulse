"""Tests for the NetSuite re-authorization flow:

- Reconnect endpoint (admin only, reuses existing connection)
- OAuth callback stores the 30-day re-auth deadline and clears error state
- Dead connections (invalid_grant -> tokens cleared) surface ONE consistent
  NETSUITE_REAUTH_REQUIRED error, never 401 (frontend treats 401 as an
  expired AGSuite login) and never a silent 200
- Catalogue: a failed forced refresh is flagged (refresh_failed)
- Serializer exposes needs_reauth / reauth_required_by

External HTTP is mocked. Company + Company Admin role are created here
explicitly so these tests don't depend on migration-seeded data.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from netsuite.client import NetSuiteTokenSet
from netsuite.constants import NETSUITE_MAX_TOKEN_ROTATION_HOURS
from netsuite.exceptions import NetSuiteTokenExchangeException
from netsuite.models import NetSuiteConnection, NetSuiteFieldCatalogue
from netsuite.oauth import resolve_user_id_from_state
from netsuite.repositories import NetSuiteConnectionRepository
from netsuite.serializers import NetSuiteConnectionListSerializer
from netsuite.services import (
    NetSuiteConnectionService,
    raise_if_reauth_required,
)
from rbac.models import Role
from superadmin.models import Plan
from tenancy.models import Company

BASE = "/api/v1/netsuite"


def _auth(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class ReauthFixtureMixin:
    def build_world(self):
        plan = Plan.objects.create(name="Test Plan", validity_days=30)
        today = timezone.now().date()
        self.company = Company.objects.create(
            name="Test Co", code="TC", status=Company.Status.ACTIVE,
            plan=plan,
            plan_start_date=today - timedelta(days=1),
            plan_end_date=today + timedelta(days=29),
        )
        self.admin_role = Role.objects.create(
            name="Company Admin", company=self.company
        )
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="pass12345",
            company=self.company,
            role=self.admin_role,
            is_active=True,
            is_email_verified=True,
        )
        self.employee = User.objects.create_user(
            email="emp@test.com",
            password="pass12345",
            company=self.company,
            is_active=True,
            is_email_verified=True,
        )
        self.healthy = self.make_connection(account="1111111")
        self.dead = self.make_connection(
            account="2222222",
            status="error",
            access_token=None,
            refresh_token=None,
            access_token_expires_at=None,
            last_error="Token refresh failed",
            consecutive_failures=5,
        )

    def make_connection(self, account, **overrides):
        defaults = dict(
            user=self.admin,
            company=self.company,
            client_name=f"Conn {account}",
            environment="sandbox",
            client_id="client-id",
            client_secret="client-secret",
            netsuite_account_id=account,
            status="connected",
            is_active=True,
            access_token="access",
            refresh_token="refresh",
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
        defaults.update(overrides)
        return NetSuiteConnection.objects.create(**defaults)


class ReconnectViewTests(ReauthFixtureMixin, APITestCase):
    def setUp(self):
        self.build_world()

    def _url(self, conn):
        return f"{BASE}/company/connections/{conn.id}/reconnect/"

    def test_admin_gets_authorize_url_for_dead_connection(self):
        response = self.client.post(self._url(self.dead), **_auth(self.admin))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        url = response.data["data"]["authorization_url"]
        self.assertIn("2222222.app.netsuite.com/app/login/oauth2/authorize.nl", url)

        state = url.split("state=")[1].split("&")[0]
        from urllib.parse import unquote

        user_id, connection_id = resolve_user_id_from_state(unquote(state))
        self.assertEqual(user_id, str(self.admin.id))
        self.assertEqual(connection_id, str(self.dead.id))

    def test_employee_cannot_reconnect(self):
        response = self.client.post(self._url(self.dead), **_auth(self.employee))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_company_connection_is_404(self):
        other = Company.objects.create(
            name="Other", code="OT", status=Company.Status.ACTIVE
        )
        other_user = User.objects.create_user(
            email="o@test.com", password="pass12345", company=other,
            is_active=True, is_email_verified=True,
        )
        foreign = NetSuiteConnection.objects.create(
            user=other_user, company=other, client_name="F", environment="sandbox",
            client_id="c", client_secret="s", netsuite_account_id="9999999",
            status="error", is_active=True,
        )
        response = self.client.post(self._url(foreign), **_auth(self.admin))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CallbackDeadlineTests(ReauthFixtureMixin, TestCase):
    def setUp(self):
        self.build_world()

    @patch("netsuite.services.NetSuiteAuthClient")
    def test_callback_restores_connection_and_sets_deadline(self, MockClient):
        MockClient.return_value.exchange_code_for_tokens.return_value = NetSuiteTokenSet(
            access_token="new-access",
            refresh_token="new-refresh",
            access_token_expires_at=timezone.now() + timedelta(hours=1),
        )
        from netsuite.oauth import _state_signer

        state = _state_signer.sign(f"{self.admin.id}:{self.dead.id}")
        NetSuiteConnectionService().handle_callback(code="abc", state=state)

        self.dead.refresh_from_db()
        self.assertEqual(self.dead.status, "connected")
        self.assertTrue(self.dead.is_active)
        self.assertEqual(self.dead.refresh_token, "new-refresh")
        self.assertIsNone(self.dead.last_error)
        self.assertEqual(self.dead.consecutive_failures, 0)

        expected = timezone.now() + timedelta(hours=NETSUITE_MAX_TOKEN_ROTATION_HOURS)
        self.assertLess(abs((self.dead.refresh_token_expires_at - expected).total_seconds()), 60)


class ReauthGateTests(ReauthFixtureMixin, TestCase):
    def setUp(self):
        self.build_world()

    def test_dead_connection_raises_invalid_grant(self):
        with self.assertRaises(NetSuiteTokenExchangeException) as ctx:
            raise_if_reauth_required(self.dead)
        self.assertTrue(str(ctx.exception).startswith("NETSUITE_INVALID_GRANT:"))

    def test_healthy_connection_passes(self):
        raise_if_reauth_required(self.healthy)

    def test_error_status_with_refresh_token_is_not_reauth(self):
        # transient failures flip status to "error" but tokens are intact
        self.healthy.status = "error"
        self.healthy.save()
        raise_if_reauth_required(self.healthy)

    def test_repository_hides_error_connections_unless_asked(self):
        repo = NetSuiteConnectionRepository()
        self.assertIsNone(
            repo.get_authorized_for_user(user=self.admin, connection_id=self.dead.id)
        )
        found = repo.get_authorized_for_user(
            user=self.admin, connection_id=self.dead.id, include_error=True
        )
        self.assertEqual(found.id, self.dead.id)


class DeadConnectionEndpointTests(ReauthFixtureMixin, APITestCase):
    """Every endpoint must give the SAME code, and never 401 / never 200."""

    def setUp(self):
        self.build_world()
        self.client.credentials(**_auth(self.admin))

    def assert_reauth(self, response):
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "NETSUITE_REAUTH_REQUIRED")
        # plain-language, tells the reader WHO acts, and leaks no internals
        detail = response.data["detail"]
        self.assertIn("Company Admin", detail)
        for jargon in ("invalid_grant", "INVALID_GRANT", "token", "OAuth", "SuiteQL"):
            self.assertNotIn(jargon, detail)

    def test_catalogue_dead_connection(self):
        r = self.client.get(
            f"{BASE}/ocr/field-catalogue/",
            {"connection_id": str(self.dead.id), "force_refresh": "true"},
        )
        self.assert_reauth(r)

    def test_field_mappings_get_is_local_read_and_does_not_need_netsuite(self):
        # Saved mappings live in the AGSuite DB: 200 here proves nothing about
        # NetSuite health, which is exactly why the UI must not rely on it.
        r = self.client.get(
            f"{BASE}/ocr/field-mappings/",
            {"connection_id": str(self.dead.id), "record_type": "vendorBill"},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_suspended_company_reconnect_is_403_not_500(self):
        self.company.plan = None
        self.company.save()
        r = self.client.post(
            f"{BASE}/company/connections/{self.dead.id}/reconnect/"
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    @patch("netsuite.views.NetSuiteValidationService")
    def test_validate_token_error(self, MockSvc):
        MockSvc.return_value.validate_document.side_effect = NetSuiteTokenExchangeException(
            "NETSUITE_INVALID_GRANT: dead"
        )
        r = self.client.post(
            f"{BASE}/ocr/validate/",
            {"document_id": "11111111-1111-1111-1111-111111111111",
             "connection_id": str(self.dead.id)},
            format="json",
        )
        self.assert_reauth(r)

    @patch("netsuite.views.NetSuiteValidationService")
    def test_check_references_token_error(self, MockSvc):
        MockSvc.return_value.check_references.side_effect = NetSuiteTokenExchangeException(
            "NETSUITE_INVALID_GRANT: dead"
        )
        r = self.client.post(
            f"{BASE}/ocr/check-references/",
            {"document_id": "11111111-1111-1111-1111-111111111111",
             "connection_id": str(self.dead.id)},
            format="json",
        )
        self.assert_reauth(r)

    @patch("netsuite.views.NetSuiteVendorBillPostingService")
    def test_post_vendor_bill_token_error(self, MockSvc):
        MockSvc.return_value.post_vendor_bill.side_effect = NetSuiteTokenExchangeException(
            "NETSUITE_INVALID_GRANT: dead"
        )
        r = self.client.post(
            f"{BASE}/ocr/post-vendor-bill/",
            {"document_id": "11111111-1111-1111-1111-111111111111",
             "connection_id": str(self.dead.id)},
            format="json",
        )
        self.assert_reauth(r)


class CatalogueRefreshSignalTests(ReauthFixtureMixin, APITestCase):
    def setUp(self):
        self.build_world()
        self.client.credentials(**_auth(self.admin))
        NetSuiteFieldCatalogue.objects.create(
            connection=self.healthy, record_type="vendorBill",
            body_fields=[], line_fields=[], custom_fields=[],
        )

    def _get(self, **params):
        params.setdefault("connection_id", str(self.healthy.id))
        return self.client.get(f"{BASE}/ocr/field-catalogue/", params)

    def test_failed_forced_refresh_is_flagged_not_reported_as_success(self):
        with patch(
            "netsuite.services.NetSuiteFieldMappingService._fetch_live_metadata",
            side_effect=Exception("NetSuite timeout"),
        ):
            r = self._get(force_refresh="true")

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["data"]["refresh_failed"])
        self.assertNotIn("refreshed successfully", r.data["message"])

    def test_plain_load_from_cache_is_not_a_failure(self):
        r = self._get()
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["data"]["refresh_failed"])

    def test_forced_refresh_token_error_is_reauth(self):
        with patch(
            "netsuite.services.NetSuiteFieldMappingService._fetch_live_metadata",
            side_effect=NetSuiteTokenExchangeException("NETSUITE_INVALID_GRANT: x"),
        ):
            r = self._get(force_refresh="true")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r.data["code"], "NETSUITE_REAUTH_REQUIRED")


class SerializerReauthFieldTests(ReauthFixtureMixin, TestCase):
    def setUp(self):
        self.build_world()

    def test_dead_connection_needs_reauth(self):
        data = NetSuiteConnectionListSerializer(self.dead).data
        self.assertTrue(data["needs_reauth"])

    def test_healthy_connection_with_future_deadline(self):
        self.healthy.refresh_token_expires_at = timezone.now() + timedelta(days=20)
        self.healthy.save()
        data = NetSuiteConnectionListSerializer(self.healthy).data
        self.assertFalse(data["needs_reauth"])
        self.assertIsNotNone(data["reauth_required_by"])

    def test_past_deadline_needs_reauth(self):
        self.healthy.refresh_token_expires_at = timezone.now() - timedelta(hours=1)
        self.healthy.save()
        self.assertTrue(NetSuiteConnectionListSerializer(self.healthy).data["needs_reauth"])


class BatchTaskReauthTests(ReauthFixtureMixin, TestCase):
    def setUp(self):
        self.build_world()

    @patch("netsuite.services.NetSuiteValidationService")
    def test_batch_reports_reconnect_message_and_code(self, MockSvc):
        from netsuite.tasks import _run_netsuite_batch

        MockSvc.return_value.validate_document.side_effect = NetSuiteTokenExchangeException(
            "NETSUITE_INVALID_GRANT: dead"
        )
        task = MagicMock()
        out = _run_netsuite_batch(
            task=task,
            action="validate",
            document_ids=["11111111-1111-1111-1111-111111111111"],
            user_id=str(self.admin.id),
            connection_id=str(self.dead.id),
        )
        item = out["results"][0]
        self.assertEqual(item["code"], "NETSUITE_REAUTH_REQUIRED")
        self.assertIn("reconnect", item["error"].lower())