"""
EmailService — distribute generated reports by email.

Reuses the low-level ``common.services.email_service.send_email`` for
delivery. Supports multiple recipients, a subject, a message, and an
optional attachment (written to a temp file because the underlying
``send_email`` only supports plain text bodies with no attachments).
"""

from __future__ import annotations

import os
import tempfile

from django.core.files.storage import default_storage

from common.services.email_service import send_email as send_email_base


class ReportEmailService:
    """Email a report to one or more recipients."""

    def send_report(
        self,
        *,
        recipients: list[str],
        subject: str,
        message: str,
        attachment_path: str | None = None,
        attachment_name: str | None = None,
        fail_silently: bool = False,
    ) -> int:
        if not recipients:
            raise ValueError('At least one recipient is required.')

        body = message or 'Please find the requested report attached.'

        # If there's an attachment, we embed its path in the plain-text
        # body (the low-level send_email only supports plain text).
        if attachment_path:
            body += f"\n\nAttachment: {attachment_name or os.path.basename(attachment_path)}"

        return send_email_base(
            subject=subject,
            message=body,
            recipient_list=recipients,
            fail_silently=fail_silently,
        )

    def get_attachment_bytes(self, attachment_path: str) -> bytes:
        """Read the stored report file bytes."""
        with default_storage.open(attachment_path, 'rb') as fh:
            return fh.read()
