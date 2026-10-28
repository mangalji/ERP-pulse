from unittest.mock import patch

from django.test import SimpleTestCase

from audit.models import AuditAction, AuditModule
from audit.services import audit_service, redact_detail


class AuditServiceSafetyTests(SimpleTestCase):
    def test_redact_detail_removes_credentials_and_raw_email_content(self):
        value = redact_detail({
            "access_token": "secret-access-token",
            "nested": {"refresh_token": "secret-refresh-token"},
            "messages": [{"raw_body": "private bill body", "subject": "Invoice"}],
        })

        self.assertEqual(value["access_token"], "[redacted]")
        self.assertEqual(value["nested"]["refresh_token"], "[redacted]")
        self.assertEqual(value["messages"][0]["raw_body"], "[redacted]")
        self.assertEqual(value["messages"][0]["subject"], "Invoice")

    @patch("audit.services.AuditLog.objects.create", side_effect=RuntimeError("database unavailable"))
    def test_audit_write_failure_is_non_blocking(self, _create):
        with self.assertLogs("audit.services", level="ERROR"):
            result = audit_service.log(
                module=AuditModule.EMAIL,
                action=AuditAction.FETCH,
                entity="Mailbox sync completed",
            )

        self.assertIsNone(result)
