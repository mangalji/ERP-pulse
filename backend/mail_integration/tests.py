from urllib.parse import parse_qs, urlparse
from unittest.mock import ANY, Mock, PropertyMock, patch
from datetime import timedelta

import requests

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from mail_integration.client import EmailOAuthClient
from mail_integration.exceptions import EmailIntegrationConfigurationError, EmailIntegrationOAuthError, EmailRefreshTokenMissingError
from mail_integration.mailbox import GmailMailboxClient, normalize_email_body
from mail_integration.models import EmailIntegration
from mail_integration.oauth import build_authorization_url, resolve_state, oauth_config_for
from mail_integration.serializers import EmailIntegrationCreateSerializer, EmailIntegrationSerializer
from mail_integration.sync import EmailSyncService, dedupe_syncs_to_retain, sync_lookback_for
from mail_integration.health import ensure_email_processing_available
from mail_integration.exceptions import EmailIntegrationStateError
from mail_integration.services import EmailIntegrationService
from mail_integration.pipeline import EmailBillPipeline
from netsuite.services import NetSuiteValidationService


class EmailValidationFlowTests(SimpleTestCase):
    @patch('mail_integration.sync.EmailIntegration.objects.filter')
    @patch('mail_integration.sync.EmailOAuthClient')
    def test_refresh_saves_tokens_without_running_failure_notification(self, client, filtered):
        integration = Mock(access_token_expires_at=None, refresh_token='old')
        client.return_value.refresh_access_token.return_value = Mock(
            access_token='new', refresh_token=None,
            access_token_expires_at=timezone.now(), provider_metadata={},
        )
        EmailSyncService()._refresh_access_token_if_needed(integration)
        self.assertEqual(integration.access_token, 'new')
        self.assertEqual(integration.refresh_token, 'old')
        filtered.return_value.update.assert_called_once()

    @patch("mail_integration.pipeline.net_suite_diagnostics_service")
    @patch("mail_integration.pipeline.NetSuiteVendorBillPostingService")
    @patch("mail_integration.pipeline.NetSuiteValidationService")
    def test_validation_errors_generate_guidance_without_posting(self, validation_service, posting_service, diagnostics):
        validation_service.return_value.validate_document.return_value = {
            "status": "VALIDATION_FAILED", "validation_id": "validation-1",
            "errors": [{"type": "TEMPLATE_MAPPING_ERROR", "message": "Select a sublist"}],
        }
        user = Mock()
        EmailBillPipeline()._validate_and_post(document_id="doc", user=user, connection_id="connection")
        diagnostics.diagnose_and_persist.assert_called_once_with(
            company=user.company, connection_id="connection", validation_ids=["validation-1"],
        )
        posting_service.assert_not_called()

    @patch("mail_integration.pipeline.net_suite_diagnostics_service")
    @patch("mail_integration.pipeline.NetSuiteVendorBillPostingService")
    @patch("mail_integration.pipeline.NetSuiteValidationService")
    def test_successful_validation_posts_without_diagnostics(self, validation_service, posting_service, diagnostics):
        validation_service.return_value.validate_document.return_value = {"status": "VALIDATED", "errors": []}
        user = Mock()
        EmailBillPipeline()._validate_and_post(document_id="doc", user=user, connection_id="connection")
        posting_service.return_value.post_vendor_bill.assert_called_once_with(
            document_id="doc", connection_id="connection", user=user,
        )
        diagnostics.diagnose_and_persist.assert_not_called()


class SenderEmailVendorResolutionTests(SimpleTestCase):
    @patch("netsuite.services._build_template_netsuite_mappings")
    def test_sender_email_uses_latest_active_vendor_and_overrides_extraction(self, mappings):
        mappings.return_value = [{
            "source_scope": "header",
            "target_field_id": "entity",
            "source_field_key": "vendor_name",
        }]
        connection = Mock(status="connected", is_active=True)
        service = NetSuiteValidationService()
        data = {"vendor_name": "Name incorrectly extracted from email"}
        with patch.object(service, "_execute_live_suiteql", return_value={"items": [
            {"id": "103", "email": "vendor@example.com", "companyname": "Inactive Newest", "isinactive": "T"},
            {"id": "102", "email": "VENDOR@example.com", "companyname": "Latest Active Vendor", "isinactive": "F"},
            {"id": "101", "email": "vendor@example.com", "companyname": "Older Active Vendor", "isinactive": "F"},
        ]}) as suiteql:
            result = service.resolve_vendor_from_sender_email(
                data=data,
                requested_fields=[],
                user=Mock(),
                sender_email="vendor@example.com",
                connection=connection,
            )

        self.assertTrue(result["matched"])
        self.assertEqual(result["vendor_id"], "102")
        self.assertEqual(data["vendor_name"], "Latest Active Vendor")
        self.assertIn("ORDER BY id DESC", suiteql.call_args.kwargs["query"])

    @patch("netsuite.services._build_template_netsuite_mappings")
    def test_sender_email_without_vendor_keeps_record_for_manual_review(self, mappings):
        mappings.return_value = [{
            "source_scope": "header",
            "target_field_id": "entity",
            "source_field_key": "vendor_name",
        }]
        service = NetSuiteValidationService()
        with patch.object(service, "_execute_live_suiteql", return_value={"items": []}):
            result = service.resolve_vendor_from_sender_email(
                data={},
                requested_fields=[],
                user=Mock(),
                sender_email="unknown@example.com",
                connection=Mock(status="connected", is_active=True),
            )
        self.assertFalse(result["matched"])
        self.assertEqual(result["reason"], "vendor_email_not_found")


class EmailSchedulerHealthTests(SimpleTestCase):
    @patch("mail_integration.health._broker_redis")
    @patch("config.celery.app.control.inspect")
    def test_worker_and_recent_scheduler_heartbeat_are_required(self, inspect, broker_factory):
        broker = broker_factory.return_value
        inspect.return_value.ping.return_value = {"worker": {"ok": "pong"}}
        broker.exists.return_value = 1
        ensure_email_processing_available()
        broker.exists.return_value = 0
        with self.assertRaisesRegex(EmailIntegrationStateError, "scheduler"):
            ensure_email_processing_available()
        inspect.return_value.ping.return_value = None
        with self.assertRaisesRegex(EmailIntegrationStateError, "worker"):
            ensure_email_processing_available()


class EmailPauseTests(SimpleTestCase):
    @patch("mail_integration.health.ensure_email_processing_available")
    @patch("mail_integration.services.is_company_admin", return_value=True)
    def test_pause_and_resume_preserve_sync_position(self, is_admin, health):
        service = EmailIntegrationService()
        integration = EmailIntegration(status="CONNECTED", is_active=True, initial_sync_from_at=timezone.now(), last_successful_sync_at=timezone.now())
        integration.save = Mock()
        user = Mock()
        before = integration.last_successful_sync_at
        with patch.object(service, "_ensure_operational"), patch.object(service, "_get_for_user", return_value=integration):
            service.set_paused(user=user, integration_id=integration.id, paused=True)
            self.assertTrue(integration.is_paused)
            health.assert_not_called()
            service.set_paused(user=user, integration_id=integration.id, paused=False)
        self.assertFalse(integration.is_paused)
        self.assertEqual(integration.last_successful_sync_at, before)
        health.assert_called_once()

    @patch("mail_integration.health._broker_redis", side_effect=ConnectionError("offline"))
    def test_unavailable_broker_is_reported(self, broker_factory):
        with self.assertRaisesRegex(EmailIntegrationStateError, "Redis broker"):
            ensure_email_processing_available()


@override_settings(EMAIL_OAUTH_REDIRECT_URI="http://localhost/callback/", GOOGLE_MAIL_CLIENT_ID="id", GOOGLE_MAIL_CLIENT_SECRET="secret")
class EmailRefreshFailureTests(SimpleTestCase):
    @override_settings(ZOHO_MAIL_CLIENT_ID="id", ZOHO_MAIL_CLIENT_SECRET="secret")
    def test_zoho_invalid_refresh_code_requires_reconnect(self):
        client = EmailOAuthClient(integration=EmailIntegration(provider="ZOHO", refresh_token="token"))
        with patch("mail_integration.client.requests.post") as post:
            post.return_value = Mock(status_code=400, json=Mock(return_value={"error": "invalid_code"}))
            with self.assertRaises(EmailIntegrationOAuthError) as raised:
                client.refresh_access_token()
        self.assertTrue(raised.exception.authorization_required)

    def test_invalid_grant_requires_reconnect_but_provider_failure_does_not(self):
        client = EmailOAuthClient(integration=EmailIntegration(provider="GOOGLE", refresh_token="token"))
        for status, response, expected in [(400, {"error": "invalid_grant"}, True), (503, {"error": "server_error"}, False)]:
            with self.subTest(response=response), patch("mail_integration.client.requests.post") as post:
                post.return_value = Mock(status_code=status, json=Mock(return_value=response))
                with self.assertRaises(EmailIntegrationOAuthError) as raised:
                    client.refresh_access_token()
                self.assertEqual(raised.exception.authorization_required, expected)

    def test_dns_failure_is_logged_as_dns_resolution(self):
        client = EmailOAuthClient(integration=EmailIntegration(provider="GOOGLE", refresh_token="token"))
        dns_error = requests.ConnectionError(
            "Failed to resolve 'accounts.google.com' ([Errno 11001] getaddrinfo failed)"
        )
        with patch("mail_integration.client.requests.post", side_effect=dns_error), \
             self.assertLogs("mail_integration.client", level="WARNING") as logs:
            with self.assertRaisesRegex(EmailIntegrationOAuthError, "Could not reach"):
                client.refresh_access_token()
        self.assertTrue(any("category=dns_resolution" in line for line in logs.output))

    def test_refresh_failure_pauses_only_invalid_authorization(self):
        for requires_auth in (True, False):
            integration = EmailIntegration(status="CONNECTED", is_active=True, initial_sync_from_at=timezone.now())
            integration.save = Mock()
            failure = EmailIntegrationOAuthError("failed", authorization_required=requires_auth)
            with self.subTest(requires_auth=requires_auth), \
                 patch.object(EmailIntegration.objects, "get", return_value=integration), \
                 patch.object(EmailIntegration.objects, "filter"), \
                 patch("mail_integration.sync.audit_service.log"), \
                 patch.object(EmailIntegration, "company", new_callable=PropertyMock, return_value=Mock()), \
                 patch.object(EmailSyncService, "_refresh_access_token_if_needed", side_effect=failure):
                with self.assertRaises(EmailIntegrationOAuthError):
                    EmailSyncService().sync_integration(integration_id=integration.id)
            self.assertEqual(integration.status, "ERROR" if requires_auth else "CONNECTED")
            self.assertTrue(integration.is_active)
            self.assertIsNone(integration.last_successful_sync_at)

    def test_refresh_success_fetches_from_last_success_with_overlap(self):
        last_sync = timezone.now() - timedelta(hours=1)
        integration = EmailIntegration(provider="GOOGLE", status="CONNECTED", is_active=True,
            initial_sync_from_at=last_sync - timedelta(days=1), last_successful_sync_at=last_sync,
            provider_metadata={"authorized_mailbox_email": "bills@example.com"},
            mailbox_email="bills@example.com", refresh_token="old")
        integration.save = Mock()
        tokens = Mock(access_token="new", refresh_token=None,
            access_token_expires_at=timezone.now() + timedelta(hours=1), provider_metadata=integration.provider_metadata)
        mailbox = Mock()
        mailbox.iter_messages_since.return_value = []
        with patch.object(EmailIntegration.objects, "get", return_value=integration), \
             patch.object(EmailIntegration.objects, "filter"), \
             patch("mail_integration.sync.audit_service.log"), \
             patch.object(EmailIntegration, "company", new_callable=PropertyMock, return_value=Mock()), \
             patch("mail_integration.sync.EmailOAuthClient") as client, \
             patch("mail_integration.sync.mailbox_client_for", return_value=mailbox), \
             patch.object(EmailSyncService, "_advance_terminal_dedupe"):
            client.return_value.refresh_access_token.return_value = tokens
            self.assertEqual(EmailSyncService().sync_integration(integration_id=integration.id), 0)
        mailbox.iter_messages_since.assert_called_once_with(
            last_sync - timedelta(minutes=65),
            until=ANY,
            cursor="",
            on_page_completed=ANY,
        )
        self.assertEqual(integration.access_token, "new")
        self.assertEqual(integration.refresh_token, "old")
        self.assertGreater(integration.last_successful_sync_at, last_sync)

    def test_five_minute_sync_uses_safe_overlap_and_retention(self):
        integration = EmailIntegration(sync_interval_minutes=5)

        self.assertEqual(sync_lookback_for(integration), timedelta(minutes=65))
        self.assertEqual(dedupe_syncs_to_retain(integration), 13)

    def test_error_connection_never_fetches(self):
        integration = EmailIntegration(status="ERROR", is_active=True)
        with patch.object(EmailIntegration.objects, "get", return_value=integration), \
             patch("mail_integration.sync.mailbox_client_for") as mailbox:
            self.assertEqual(EmailSyncService().sync_integration(integration_id=integration.id), 0)
        mailbox.assert_not_called()


@override_settings(
    EMAIL_OAUTH_REDIRECT_URI="http://localhost:8000/api/v1/email/callback/",
    GOOGLE_MAIL_CLIENT_ID="google-client-id",
    GOOGLE_MAIL_CLIENT_SECRET="google-client-secret",
    ZOHO_MAIL_CLIENT_ID="zoho-client-id",
    ZOHO_MAIL_CLIENT_SECRET="zoho-client-secret",
)
class EmailOAuthUrlTests(SimpleTestCase):
    def test_mailbox_credentials_override_environment_and_secret_is_not_serialized(self):
        integration = EmailIntegration(provider="ZOHO", mailbox_email="bills@example.com", oauth_client_id="own-id", oauth_client_secret="own-secret")
        config = oauth_config_for(integration)
        self.assertEqual((config.client_id, config.client_secret), ("own-id", "own-secret"))
        self.assertNotIn("oauth_client_secret", EmailIntegrationSerializer(integration).data)
        self.assertNotIn("own-secret", build_authorization_url(integration=integration, user_id="user"))

    def test_credentials_must_be_provided_together(self):
        serializer = EmailIntegrationCreateSerializer(data={"provider": "ZOHO", "mailbox_email": "bills@example.com", "client_id": "id"})
        self.assertFalse(serializer.is_valid())

    def test_google_authorization_url_requests_offline_read_only_access(self):
        integration = EmailIntegration(provider=EmailIntegration.Provider.GOOGLE)

        authorization_url = build_authorization_url(
            integration=integration,
            user_id="user-123",
        )

        parsed = urlparse(authorization_url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "accounts.google.com")
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertIn(
            "https://www.googleapis.com/auth/gmail.readonly",
            query["scope"][0],
        )
        self.assertEqual(resolve_state(query["state"][0])["user_id"], "user-123")

    def test_zoho_authorization_url_uses_selected_data_center(self):
        integration = EmailIntegration(
            provider=EmailIntegration.Provider.ZOHO,
            provider_metadata={"zoho_data_center": "EU"},
        )

        authorization_url = build_authorization_url(
            integration=integration,
            user_id="user-456",
        )

        parsed = urlparse(authorization_url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "accounts.zoho.eu")
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertIn("ZohoMail.messages.READ", query["scope"][0])
        self.assertIn("ZohoMail.folders.READ", query["scope"][0])

    def test_zoho_existing_token_does_not_force_new_consent(self):
        integration = EmailIntegration(provider="ZOHO", status="CONNECTED", refresh_token="saved")
        query = parse_qs(urlparse(build_authorization_url(integration=integration, user_id="user")).query)
        self.assertNotIn("prompt", query)

    def test_zoho_error_connection_requests_consent_even_with_old_token(self):
        integration = EmailIntegration(provider="ZOHO", status="ERROR", refresh_token="saved")
        query = parse_qs(urlparse(build_authorization_url(integration=integration, user_id="user")).query)
        self.assertEqual(query["prompt"], ["consent"])


class EmailOAuthCompletionTests(SimpleTestCase):
    @patch("mail_integration.services.transaction.atomic")
    @patch("mail_integration.services.is_company_admin", return_value=True)
    @patch("mail_integration.services.EmailOAuthClient")
    @patch("mail_integration.services.User.objects")
    @patch("mail_integration.services.resolve_state")
    def test_missing_refresh_token_does_not_connect(self, state, users, client, admin, atomic):
        state.return_value = {"user_id": "user", "integration_id": "mail", "provider": "ZOHO"}
        user = users.select_related.return_value.get.return_value
        integration = EmailIntegration(provider="ZOHO", mailbox_email="bills@example.com", status="ERROR")
        integration.save = Mock()
        client.return_value.exchange_code.return_value = Mock(access_token="access", refresh_token=None)
        client.return_value.authorized_mailbox_identity.return_value = ("bills@example.com", {})
        service = EmailIntegrationService()
        with patch.object(service, "_ensure_operational"), patch.object(service, "_get_for_user", return_value=integration):
            with self.assertRaises(EmailRefreshTokenMissingError):
                service.complete_oauth(code="code", state="state")
        self.assertEqual(integration.status, "ERROR")
        self.assertIsNone(integration.refresh_token)


class EmailOAuthConfigurationTests(SimpleTestCase):
    @override_settings(
        EMAIL_OAUTH_REDIRECT_URI="",
        GOOGLE_MAIL_CLIENT_ID="",
        GOOGLE_MAIL_CLIENT_SECRET="",
    )
    def test_missing_oauth_configuration_is_rejected(self):
        integration = EmailIntegration(provider=EmailIntegration.Provider.GOOGLE)

        with self.assertRaises(EmailIntegrationConfigurationError):
            build_authorization_url(integration=integration, user_id="user-123")


class MailboxParsingTests(SimpleTestCase):
    def test_gmail_message_is_normalized_without_losing_plain_text(self):
        client = GmailMailboxClient(
            integration=EmailIntegration(
                provider=EmailIntegration.Provider.GOOGLE,
                access_token="token",
            )
        )
        parsed = client.parse_message(
            {
                "id": "gmail-123",
                "threadId": "thread-123",
                "internalDate": "1735689600000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Vendor <vendor@example.com>"},
                        {"name": "To", "value": "Bills <bills@example.com>"},
                        {"name": "Subject", "value": "Invoice 42"},
                        {"name": "Message-ID", "value": "<message-42@example.com>"},
                    ],
                    "parts": [
                        {"mimeType": "text/html", "body": {"data": "PGRpdj5JbnZvaWNlIDQyPC9kaXY+"}},
                        {"mimeType": "text/plain", "body": {"data": "SW52b2ljZSA0Mg"}},
                    ],
                },
            }
        )
        self.assertEqual(parsed.provider_message_id, "gmail-123")
        self.assertEqual(parsed.sender_email, "vendor@example.com")
        self.assertEqual(parsed.recipient_emails, ["bills@example.com"])
        self.assertEqual(parsed.normalized_body, "Invoice 42")

    def test_html_normalization_discards_script_content(self):
        self.assertEqual(
            normalize_email_body("<p>Total: 500</p><script>do-not-send()</script>"),
            "Total: 500",
        )
