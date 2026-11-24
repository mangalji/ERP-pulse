from urllib.parse import parse_qs, urlparse
from unittest.mock import ANY, Mock, PropertyMock, patch
from datetime import timedelta

import requests

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from mail_integration.client import EmailOAuthClient
from mail_integration.exceptions import EmailIntegrationConfigurationError, EmailIntegrationOAuthError, EmailRefreshTokenMissingError
from mail_integration.mailbox import GmailMailboxClient, OutlookMailboxClient, normalize_email_body
from mail_integration.models import EmailIntegration
from mail_integration.oauth import build_authorization_url, resolve_state, oauth_config_for
from mail_integration.serializers import EmailIntegrationConfigureSerializer, EmailIntegrationCreateSerializer, EmailIntegrationSerializer
from mail_integration.sync import EmailSyncService, dedupe_syncs_to_retain, sync_lookback_for
from mail_integration.health import ensure_email_processing_available
from mail_integration.exceptions import EmailIntegrationStateError
from mail_integration.services import EmailIntegrationService
from mail_integration.pipeline import EmailBillPipeline
from mail_integration.tasks import _record_mailbox_sync_summary, run_scheduled_mailbox
from netsuite.services import NetSuiteValidationService
from tenancy.models import Company


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
    @patch("mail_integration.pipeline.company_lifecycle_service.is_operational", return_value=True)
    @patch("mail_integration.pipeline.audit_service.log")
    @patch("mail_integration.pipeline.ai_extractor.extract_email_text")
    @patch("mail_integration.pipeline.NetSuiteValidationService")
    @patch("mail_integration.pipeline.NetSuiteConnectionRepository")
    def test_unmatched_sender_is_terminal_without_an_ai_request(
        self, repository, validation_service, extract_email, audit_log, is_operational,
    ):
        """Ordinary mailbox traffic must never consume an AI extraction call."""
        user = Mock()
        template = Mock(fields_config={"standard_fields": ["vendor_name"]})
        integration = Mock(created_by=user, ocr_template=template, company=Mock())
        message = Mock(
            id="4a3a0d89-6af9-4a63-8fc7-4d7d4717b20c",
            integration=integration,
            lease_owner="lease-1",
            sender_email="unknown@example.com",
            subject="Ordinary mailbox message",
            provider_message_id="provider-message-1",
            internet_message_id="internet-message-1",
            sent_at=None,
            received_at=None,
        )
        repository.return_value.get_for_user.return_value = Mock()
        validation_service.return_value.resolve_vendor_from_sender_email.return_value = {
            "matched": False,
            "reason": "vendor_email_not_found",
        }
        pipeline = EmailBillPipeline()

        with patch.object(pipeline, "_claim", return_value=message), \
             patch.object(pipeline, "_mark_terminal") as mark_terminal:
            result = pipeline.process_message(message_id=message.id)

        self.assertEqual(result, "discarded")
        extract_email.assert_not_called()
        mark_terminal.assert_called_once_with(
            message_id=message.id,
            lease_owner="lease-1",
            integration=integration,
            is_vendor_bill=False,
            extracted_data=None,
        )
        audit_log.assert_called_once()

    @patch("mail_integration.pipeline.audit_service.log")
    @patch("mail_integration.pipeline.company_lifecycle_service.is_operational", return_value=True)
    @patch("mail_integration.pipeline.ai_extractor.extract_email_text")
    @patch("mail_integration.pipeline.NetSuiteValidationService")
    @patch("mail_integration.pipeline.NetSuiteConnectionRepository")
    def test_matched_vendor_normal_email_is_terminal_after_one_ai_classification(
        self, repository, validation_service, extract_email, is_operational, audit_log,
    ):
        """A vendor follow-up must not become an OCR bill merely because its sender matches."""
        user = Mock()
        template = Mock(fields_config={"standard_fields": ["vendor_name"]})
        integration = Mock(created_by=user, ocr_template=template, company=Mock())
        message = Mock(
            id="9ba8a3f9-28ab-4c7d-a873-96f735d0f8ac",
            integration=integration,
            lease_owner="lease-2",
            sender_email="vendor@example.com",
            subject="Delivery status follow-up",
            provider_message_id="provider-message-2",
            internet_message_id="internet-message-2",
            normalized_body="Can you confirm the delivery status for our earlier order?",
            raw_body="Can you confirm the delivery status for our earlier order?",
            received_at=timezone.now(),
            sent_at=None,
            is_vendor_bill=None,
            ai_extracted_data_json=None,
        )
        repository.return_value.get_for_user.return_value = Mock()
        validation_service.return_value.resolve_vendor_from_sender_email.return_value = {
            "matched": True,
            "vendor_id": "102",
        }
        extract_email.return_value = {"is_vendor_bill": False, "data": None}
        pipeline = EmailBillPipeline()

        with patch.object(pipeline, "_claim", return_value=message), \
             patch.object(pipeline, "_mark_terminal") as mark_terminal:
            result = pipeline.process_message(message_id=message.id)

        self.assertEqual(result, "discarded")
        extract_email.assert_called_once()
        mark_terminal.assert_called_once_with(
            message_id=message.id,
            lease_owner="lease-2",
            integration=integration,
            is_vendor_bill=False,
            extracted_data=None,
        )
        audit_log.assert_called_once()

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
    def test_sender_email_without_vendor_is_reported_as_unmatched(self, mappings):
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
    @patch("mail_integration.services.is_company_admin", return_value=True)
    def test_resume_requires_a_new_schedule(self, is_admin):
        service = EmailIntegrationService()
        integration = EmailIntegration(status="CONNECTED", is_active=True, initial_sync_from_at=timezone.now(), last_successful_sync_at=timezone.now())
        integration.save = Mock()
        user = Mock()
        before = integration.last_successful_sync_at
        with patch.object(service, "_ensure_operational"), patch.object(service, "_get_for_user", return_value=integration):
            service.set_paused(user=user, integration_id=integration.id, paused=True)
            self.assertTrue(integration.is_paused)
            with self.assertRaisesRegex(EmailIntegrationStateError, "Choose a new email fetching schedule"):
                service.set_paused(user=user, integration_id=integration.id, paused=False)
        self.assertTrue(integration.is_paused)
        self.assertEqual(integration.last_successful_sync_at, before)

    @patch("mail_integration.health._broker_redis", side_effect=ConnectionError("offline"))
    def test_unavailable_broker_is_reported(self, broker_factory):
        with self.assertRaisesRegex(EmailIntegrationStateError, "Redis broker"):
            ensure_email_processing_available()


class EmailScheduleRestartTests(SimpleTestCase):
    def test_completed_single_schedule_requires_a_new_schedule(self):
        integration = EmailIntegration(
            schedule_config={"type": "SINGLE"},
            last_successful_sync_at=timezone.now(),
            next_sync_at=None,
            provider_cursor="",
        )

        self.assertTrue(integration.is_fetching_stopped)

    def test_completed_recurring_schedule_requires_a_new_schedule(self):
        integration = EmailIntegration(
            schedule_config={"type": "DAILY"},
            last_successful_sync_at=timezone.now(),
            next_sync_at=None,
            provider_cursor="",
        )

        self.assertTrue(integration.is_fetching_stopped)

    def test_restarted_schedule_resets_the_old_watermark(self):
        service = EmailIntegrationService()
        integration = EmailIntegration(
            company=Company(name="Test Company", code="test-company"),
            status="CONNECTED",
            is_active=True,
            is_paused=True,
            last_successful_sync_at=timezone.now(),
            latest_fetched_email_received_at=timezone.now() - timedelta(days=2),
            provider_cursor="old-cursor",
        )
        integration.save = Mock()
        schedule = {
            "type": "DAILY", "start_date": "2026-12-01", "start_time": "09:00",
            "timezone": "Asia/Calcutta", "repeat_minutes": None,
            "repeat_every": 1, "daily_mode": "INTERVAL", "no_end_date": True,
        }

        with patch.object(service, "check_initial_sync_ready", return_value=integration), \
             patch.object(service, "_ensure_email_capacity"), \
             patch("mail_integration.services.next_run_at", return_value=timezone.now()), \
             patch("mail_integration.tasks.enqueue_next_mailbox_run") as enqueue, \
             patch("audit.integration_alerts.mark_integration_healthy"):
            service.configure_initial_sync(
                user=Mock(),
                integration_id=integration.id,
                schedule=schedule,
                fetch_from_at=timezone.now() - timedelta(days=1),
            )

        self.assertFalse(integration.is_paused)
        self.assertIsNone(integration.last_successful_sync_at)
        self.assertEqual(integration.provider_cursor, "")
        self.assertEqual(integration.schedule_config, schedule)
        enqueue.assert_called_once_with(integration.id)


class EmailFetchBoundaryTests(SimpleTestCase):
    def test_fetch_from_validator_returns_an_aware_timestamp(self):
        serializer = EmailIntegrationConfigureSerializer()

        value = serializer.validate_fetch_from({
            "date": "2026-11-20",
            "time": "09:30",
            "timezone": "Asia/Calcutta",
        })

        self.assertTrue(timezone.is_aware(value))
        self.assertEqual(value.hour, 9)
        self.assertEqual(value.minute, 30)

    def test_fetch_from_at_or_before_prior_received_email_is_rejected(self):
        service = EmailIntegrationService()
        integration = EmailIntegration(
            company=Company(name="Test Company", code="boundary-company"),
            provider="GOOGLE",
            mailbox_email="bills@example.com",
            status="CONNECTED",
            is_active=True,
        )
        latest_received_at = timezone.now() - timedelta(hours=1)
        integration.latest_fetched_email_received_at = latest_received_at
        schedule = {
            "type": "SINGLE", "start_date": "2026-12-01", "start_time": "09:00",
            "timezone": "Asia/Calcutta", "repeat_minutes": None,
            "repeat_every": 1, "daily_mode": "INTERVAL", "no_end_date": True,
        }

        with patch.object(service, "check_initial_sync_ready", return_value=integration), \
             patch.object(service, "_ensure_email_capacity"), \
             self.assertRaisesRegex(EmailIntegrationStateError, "already fetched emails through"):
            service.configure_initial_sync(
                user=Mock(),
                integration_id=integration.id,
                schedule=schedule,
                fetch_from_at=latest_received_at,
            )

    @patch("mail_integration.services.EmailMessage.objects.filter")
    def test_existing_message_received_time_backfills_integration_boundary(self, messages):
        service = EmailIntegrationService()
        integration = EmailIntegration(provider="GOOGLE", mailbox_email="bills@example.com")
        integration.save = Mock()
        latest_received_at = timezone.now() - timedelta(hours=1)
        messages.return_value.aggregate.return_value = {"latest": latest_received_at}

        boundary = service._latest_fetched_email_received_at(integration)

        self.assertEqual(boundary, latest_received_at)
        self.assertEqual(integration.latest_fetched_email_received_at, latest_received_at)
        integration.save.assert_called_once_with(
            update_fields=["latest_fetched_email_received_at", "updated_at"]
        )

    def test_newest_received_email_time_is_kept_on_the_integration(self):
        integration = EmailIntegration(
            provider="GOOGLE",
            mailbox_email="bills@example.com",
            latest_fetched_email_received_at=timezone.now() - timedelta(days=3),
        )
        older = timezone.now() - timedelta(days=2)
        newest = timezone.now() - timedelta(days=1)

        EmailSyncService._remember_latest_fetched_email_received_at(
            integration=integration,
            received_times=[older, newest],
        )

        self.assertEqual(integration.latest_fetched_email_received_at, newest)


class EmailActivationTests(TestCase):
    @patch("mail_integration.services.is_company_admin", return_value=True)
    @patch("mail_integration.services.EmailIntegration.objects.filter")
    def test_activate_reschedules_configured_mailbox_immediately(self, active_filter, is_admin):
        service = EmailIntegrationService()
        old_next_sync = timezone.now() - timedelta(hours=1)
        integration = EmailIntegration(
            status="CONNECTED",
            is_active=False,
            is_paused=False,
            initial_sync_from_at=timezone.now() - timedelta(minutes=5),
            next_sync_at=old_next_sync,
        )
        integration.save = Mock()
        active_filter.return_value.update = Mock()
        user = Mock(company_id="company-1")

        with patch.object(service, "_ensure_operational"), patch.object(
            service, "_get_for_user", return_value=integration
        ):
            service.activate(user=user, integration_id=integration.id)

        self.assertTrue(integration.is_active)
        self.assertGreater(integration.next_sync_at, old_next_sync)
        integration.save.assert_called_once_with(
            update_fields=["is_active", "updated_at", "next_sync_at"]
        )


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
                 patch.object(EmailIntegration.objects, "select_related", return_value=Mock(get=Mock(return_value=integration))), \
                 patch.object(EmailIntegration.objects, "filter"), \
                 patch("mail_integration.sync.audit_service.log"), \
                 patch.object(EmailIntegration, "company", new_callable=PropertyMock, return_value=Mock()), \
                 patch("mail_integration.sync.company_lifecycle_service.is_operational", return_value=True), \
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
        with patch.object(EmailIntegration.objects, "select_related", return_value=Mock(get=Mock(return_value=integration))), \
             patch.object(EmailIntegration.objects, "filter"), \
             patch("mail_integration.sync.audit_service.log"), \
             patch.object(EmailIntegration, "company", new_callable=PropertyMock, return_value=Mock()), \
             patch("mail_integration.sync.company_lifecycle_service.is_operational", return_value=True), \
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

    def test_one_minute_sync_uses_safe_overlap_and_retention(self):
        integration = EmailIntegration(sync_interval_minutes=1)

        self.assertEqual(sync_lookback_for(integration), timedelta(minutes=65))
        self.assertEqual(dedupe_syncs_to_retain(integration), 65)

    def test_error_connection_never_fetches(self):
        integration = EmailIntegration(status="ERROR", is_active=True)
        with patch.object(EmailIntegration.objects, "select_related", return_value=Mock(get=Mock(return_value=integration))), \
             patch("mail_integration.sync.mailbox_client_for") as mailbox:
            self.assertEqual(EmailSyncService().sync_integration(integration_id=integration.id), 0)
        mailbox.assert_not_called()


@override_settings(
    EMAIL_OAUTH_REDIRECT_URI="http://localhost:8000/api/v1/email/callback/",
    GOOGLE_MAIL_CLIENT_ID="google-client-id",
    GOOGLE_MAIL_CLIENT_SECRET="google-client-secret",
    ZOHO_MAIL_CLIENT_ID="zoho-client-id",
    ZOHO_MAIL_CLIENT_SECRET="zoho-client-secret",
    OUTLOOK_MAIL_CLIENT_ID="outlook-client-id",
    OUTLOOK_MAIL_CLIENT_SECRET="outlook-client-secret",
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

    def test_outlook_authorization_url_requests_graph_mail_and_refresh_access(self):
        integration = EmailIntegration(provider=EmailIntegration.Provider.OUTLOOK)

        authorization_url = build_authorization_url(integration=integration, user_id="user-789")

        parsed = urlparse(authorization_url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "login.microsoftonline.com")
        self.assertIn("Mail.Read", query["scope"][0])
        self.assertIn("User.Read", query["scope"][0])
        self.assertIn("offline_access", query["scope"][0])
        self.assertNotIn("access_type", query)

    @patch("mail_integration.client.requests.get")
    def test_outlook_identity_is_verified_through_microsoft_graph(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = {"mail": "bills@example.com"}
        client = EmailOAuthClient(
            integration=EmailIntegration(
                provider=EmailIntegration.Provider.OUTLOOK,
                mailbox_email="bills@example.com",
            )
        )

        email, metadata = client.authorized_mailbox_identity(access_token="token")

        self.assertEqual(email, "bills@example.com")
        self.assertEqual(metadata, {})
        self.assertIn("graph.microsoft.com", get.call_args.args[0])


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

    def test_outlook_message_is_normalized_with_provider_received_time(self):
        client = OutlookMailboxClient(
            integration=EmailIntegration(
                provider=EmailIntegration.Provider.OUTLOOK,
                access_token="token",
            )
        )

        parsed = client.parse_message(
            {
                "id": "outlook-123",
                "conversationId": "conversation-123",
                "internetMessageId": "<message-123@example.com>",
                "from": {"emailAddress": {"address": "vendor@example.com"}},
                "toRecipients": [{"emailAddress": {"address": "bills@example.com"}}],
                "subject": "Invoice 43",
                "sentDateTime": "2026-11-24T07:00:00Z",
                "receivedDateTime": "2026-11-24T07:05:00Z",
                "body": {"contentType": "text", "content": "Invoice 43"},
            }
        )

        self.assertEqual(parsed.provider_message_id, "outlook-123")
        self.assertEqual(parsed.sender_email, "vendor@example.com")
        self.assertEqual(parsed.recipient_emails, ["bills@example.com"])
        self.assertEqual(parsed.received_at.isoformat(), "2026-11-24T07:05:00+00:00")

    def test_html_normalization_discards_script_content(self):
        self.assertEqual(
            normalize_email_body("<p>Total: 500</p><script>do-not-send()</script>"),
            "Total: 500",
        )

class MailboxSyncSummaryTests(SimpleTestCase):
    """``last_sync_summary`` must stay live on the per-mailbox scheduling path.

    ``process_due_messages`` drains due messages system-wide, so these tests
    pin down that only the target mailbox's own counts are read back out of
    its ``by_integration`` breakdown — another mailbox's activity in the same
    run must never leak into this one's "Latest processing result".
    """

    @patch("mail_integration.tasks.EmailIntegration.objects.filter")
    def test_summary_uses_only_this_integrations_counts_from_a_system_wide_pipeline_run(self, integrations):
        update = Mock()
        integrations.return_value.update = update
        pipeline = {
            "processed": 9,
            "promoted": 4,
            "by_integration": {
                "this-integration": {"processed": 3, "promoted": 1, "discarded": 2, "deferred": 0},
                "other-integration": {"processed": 6, "promoted": 3, "discarded": 0, "deferred": 0},
            },
        }

        _record_mailbox_sync_summary(integration_id="this-integration", emails_fetched=5, pipeline=pipeline)

        integrations.assert_called_once_with(pk="this-integration")
        summary = update.call_args.kwargs["last_sync_summary"]
        self.assertEqual(summary["emails_fetched"], 5)
        self.assertEqual(summary["emails_processed"], 3)
        self.assertEqual(summary["vendor_bill_records_created"], 1)
        self.assertEqual(summary["emails_ignored"], 2)
        self.assertEqual(summary["emails_deferred"], 0)

    @patch("mail_integration.tasks.EmailIntegration.objects.filter")
    def test_summary_defaults_to_zero_counts_when_integration_is_missing_from_the_breakdown(self, integrations):
        update = Mock()
        integrations.return_value.update = update

        _record_mailbox_sync_summary(
            integration_id="idle-integration",
            emails_fetched=0,
            pipeline={"processed": 0, "by_integration": {}},
        )

        summary = update.call_args.kwargs["last_sync_summary"]
        self.assertEqual(
            {summary["emails_processed"], summary["vendor_bill_records_created"], summary["emails_ignored"], summary["emails_deferred"]},
            {0},
        )

    @patch("mail_integration.tasks.EmailIntegration.objects.filter")
    def test_summary_write_failure_is_swallowed_and_logged(self, integrations):
        integrations.return_value.update.side_effect = Exception("db unavailable")

        try:
            _record_mailbox_sync_summary(integration_id="any-integration", emails_fetched=1, pipeline={})
        except Exception:  # pragma: no cover - failing this test means the swallow broke
            self.fail("_record_mailbox_sync_summary must not raise; it is a best-effort status write")

    @patch("mail_integration.tasks.EmailIntegration.objects.filter")
    def test_missing_pipeline_breakdown_does_not_raise(self, integrations):
        update = Mock()
        integrations.return_value.update = update

        _record_mailbox_sync_summary(integration_id="any-integration", emails_fetched=2, pipeline=None)

        summary = update.call_args.kwargs["last_sync_summary"]
        self.assertEqual(summary["emails_fetched"], 2)
        self.assertEqual(summary["emails_processed"], 0)


class RunScheduledMailboxTests(SimpleTestCase):
    """End-to-end safety checks for the active per-mailbox Celery task."""

    def _due_integration(self):
        return EmailIntegration(
            id="integration-1",
            status="CONNECTED",
            is_active=True,
            is_paused=False,
            next_sync_at=timezone.now() - timedelta(minutes=1),
        )

    @patch("mail_integration.tasks.enqueue_next_mailbox_run")
    @patch("mail_integration.tasks._record_mailbox_sync_summary")
    @patch("mail_integration.tasks.EmailBillPipeline")
    @patch("mail_integration.tasks.EmailSyncService")
    @patch("mail_integration.tasks.EmailIntegration.objects.filter")
    def test_successful_run_records_summary_and_reenqueues(
        self, integrations, sync_service, pipeline_cls, record_summary, enqueue,
    ):
        integrations.return_value.first.return_value = self._due_integration()
        sync_service.return_value.sync_integration.return_value = 7
        pipeline_cls.return_value.process_due_messages.return_value = {"by_integration": {}}

        result = run_scheduled_mailbox("integration-1")

        self.assertEqual(result["emails_fetched"], 7)
        record_summary.assert_called_once_with(
            integration_id="integration-1", emails_fetched=7, pipeline={"by_integration": {}},
        )
        enqueue.assert_called_once_with("integration-1")

    @patch("mail_integration.tasks.enqueue_next_mailbox_run")
    @patch("mail_integration.tasks._record_mailbox_sync_summary", side_effect=Exception("unexpected"))
    @patch("mail_integration.tasks.EmailBillPipeline")
    @patch("mail_integration.tasks.EmailSyncService")
    @patch("mail_integration.tasks.EmailIntegration.objects.filter")
    def test_reenqueues_even_if_summary_recording_unexpectedly_raises(
        self, integrations, sync_service, pipeline_cls, record_summary, enqueue,
    ):
        """Belt-and-braces: the ``finally`` must fire even past the swallow above."""
        integrations.return_value.first.return_value = self._due_integration()
        sync_service.return_value.sync_integration.return_value = 1
        pipeline_cls.return_value.process_due_messages.return_value = {"by_integration": {}}

        with self.assertRaises(Exception):
            run_scheduled_mailbox("integration-1")

        enqueue.assert_called_once_with("integration-1")

    @patch("mail_integration.tasks.enqueue_next_mailbox_run")
    @patch("mail_integration.tasks._record_mailbox_sync_summary")
    @patch("mail_integration.tasks.EmailIntegration.objects.filter")
    def test_skipped_mailbox_never_writes_a_summary(self, integrations, record_summary, enqueue):
        integrations.return_value.first.return_value = EmailIntegration(
            id="integration-2", status="CONNECTED", is_active=False,
        )

        result = run_scheduled_mailbox("integration-2")

        self.assertEqual(result, {"skipped": True})
        record_summary.assert_not_called()
        enqueue.assert_not_called()
