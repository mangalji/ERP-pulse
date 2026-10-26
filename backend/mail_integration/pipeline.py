"""Promote staged email bodies through the existing OCR and NetSuite workflow."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from mail_integration.models import EmailIntegration, EmailMessage
from mail_integration.mailbox import readable_email_body
from netsuite.repositories import NetSuiteConnectionRepository
from netsuite.diagnostics_service import net_suite_diagnostics_service
from netsuite.services import NetSuiteValidationService, NetSuiteVendorBillPostingService
from ocr.models import DocumentType, OCRBatch, OCRDocument, OCRDocumentStatus
from ocr.notebook_extraction_service import notebook_gemini_extractor
from ocr.services.extraction_persistence import persist_extraction
from audit.notifications import automated_activity

logger = logging.getLogger(__name__)
LEASE_MINUTES = 15
RETRY_DELAY_MINUTES = 15


class EmailBillPipeline:
    """One-email-at-a-time processor; the OCR document becomes the audit record."""

    def process_due_messages(self, *, limit: int = 100) -> dict[str, int]:
        now = timezone.now()
        candidates = list(
            EmailMessage.objects.filter(
                Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now),
                Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lte=now),
                dedupe_syncs_remaining__isnull=True,
                integration__is_active=True,
                integration__is_paused=False,
                integration__status=EmailIntegration.Status.CONNECTED,
            )
            .select_related("integration", "integration__created_by", "integration__ocr_template", "integration__company")
            .order_by("received_at", "created_at")[:limit]
        )
        outcome = {"processed": 0, "promoted": 0, "discarded": 0, "deferred": 0}
        for candidate in candidates:
            result = self.process_message(message_id=candidate.id)
            outcome["processed"] += 1
            if result == "promoted":
                outcome["promoted"] += 1
            elif result == "discarded":
                outcome["discarded"] += 1
            else:
                outcome["deferred"] += 1
        return outcome

    def _claim(self, message_id):
        now = timezone.now()
        with transaction.atomic():
            message = (
                EmailMessage.objects.select_for_update(of=("self",))
                .select_related("integration", "integration__created_by", "integration__ocr_template", "integration__company")
                .filter(pk=message_id)
                .first()
            )
            if message is None:
                return None
            if not EmailIntegration.objects.filter(pk=message.integration_id, is_active=True, is_paused=False, status=EmailIntegration.Status.CONNECTED).exists():
                return None
            if message.dedupe_syncs_remaining is not None:
                return None
            if message.lease_expires_at and message.lease_expires_at > now:
                return None
            message.lease_owner = uuid.uuid4().hex[:32]
            message.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
            message.attempt_count += 1
            message.last_attempt_at = now
            message.next_attempt_at = None
            message.save(update_fields=[
                "lease_owner", "lease_expires_at", "attempt_count", "last_attempt_at",
                "next_attempt_at", "updated_at",
            ])
            return message

    def _defer(self, message_id, error: Exception):
        EmailMessage.objects.filter(pk=message_id).update(
            lease_owner="",
            lease_expires_at=None,
            next_attempt_at=timezone.now() + timedelta(minutes=RETRY_DELAY_MINUTES),
        )
        logger.warning("Email bill processing deferred — message=%s error=%s", message_id, error)
        message = EmailMessage.objects.select_related('integration').filter(pk=message_id).first()
        if message and message.attempt_count == 1:
            from audit.notifications import notify
            notify(message.integration.created_by_id, message.integration.company_id, f'Email processing failed for {message.sender_email or "unknown sender"}; it will be retried.', '/app/integrations/email')

    @automated_activity
    def process_message(self, *, message_id) -> str:
        message = self._claim(message_id)
        if message is None:
            return "deferred"
        integration = message.integration
        user = integration.created_by
        template = integration.ocr_template
        if user is None or template is None:
            self._defer(message.id, ValueError("Mailbox requires an owner and OCR template before processing."))
            return "deferred"
        try:
            # A successful AI result is retained in staging until it has been
            # promoted atomically.  A retry can therefore resume extraction
            # without asking the AI to classify the same email again.
            if message.is_vendor_bill is True and isinstance(message.ai_extracted_data_json, dict):
                data = message.ai_extracted_data_json
            else:
                result = notebook_gemini_extractor.extract_email_text(
                    message.normalized_body or message.raw_body,
                    requested_fields=template.fields_config,
                    company=integration.company,
                )
                if not result["is_vendor_bill"]:
                    self._mark_terminal(
                        message_id=message.id,
                        lease_owner=message.lease_owner,
                        is_vendor_bill=False,
                        extracted_data=None,
                    )
                    return "discarded"

                data = result["data"]
                EmailMessage.objects.filter(
                    pk=message.id,
                    lease_owner=message.lease_owner,
                ).update(is_vendor_bill=True, ai_extracted_data_json=data)

            if not isinstance(data, dict):
                raise ValueError("Vendor-bill email extraction did not return JSON data.")

            with transaction.atomic():
                locked = EmailMessage.objects.select_for_update().select_related("integration").get(pk=message.id)
                if locked.lease_owner != message.lease_owner:
                    return "deferred"
                if not EmailIntegration.objects.filter(pk=locked.integration_id, is_active=True, is_paused=False, status=EmailIntegration.Status.CONNECTED).exists():
                    locked.lease_owner = ""
                    locked.lease_expires_at = None
                    locked.save(update_fields=["lease_owner", "lease_expires_at", "updated_at"])
                    return "deferred"
                # Use the persisted AI result, rather than an in-memory value,
                # so promotion always consumes the durable staged extraction.
                data = locked.ai_extracted_data_json
                if not isinstance(data, dict):
                    raise ValueError("Vendor-bill email staging data is missing.")
                connection = NetSuiteConnectionRepository().get_for_user(user)
                fingerprint = hashlib.sha256(
                    f"{locked.integration_id}:{locked.provider_message_id or locked.internet_message_id or locked.id}".encode()
                ).hexdigest()
                # The retained staging row handles normal provider overlap.
                # This fingerprint check also protects records created before
                # that retention was introduced, or an unexpected replay.
                if OCRBatch.objects.filter(source_fingerprint=fingerprint).exists():
                    self._mark_terminal(
                        message_id=locked.id,
                        lease_owner=message.lease_owner,
                        is_vendor_bill=True,
                        extracted_data=data,
                    )
                    return "discarded"
                batch = OCRBatch.objects.create(
                    user=user,
                    company=integration.company,
                    source_type=OCRBatch.SourceType.EMAIL,
                    processing_mode=OCRBatch.ProcessingMode.AUTOMATIC,
                    email_integration=integration,
                    netsuite_connection=connection,
                    source_fingerprint=fingerprint,
                    source_content=readable_email_body(locked.raw_body, locked.normalized_body),
                    source_metadata_json={
                        "provider": integration.provider,
                        "mailbox": integration.mailbox_email,
                        "message_id": locked.provider_message_id,
                        "internet_message_id": locked.internet_message_id,
                        "sender": locked.sender_email,
                        "subject": locked.subject,
                        "sent_at": locked.sent_at.isoformat() if locked.sent_at else None,
                    },
                    original_filename=(locked.subject or "Email vendor bill")[:255],
                    requested_fields_json=template.fields_config,
                    extraction_template=template,
                    status=OCRBatch.Status.PROCESSING,
                )
                document = OCRDocument.objects.create(
                    batch=batch,
                    user=user,
                    company=integration.company,
                    document_type=DocumentType.INVOICE,
                    status=OCRDocumentStatus.PROCESSING,
                    processing_metadata={"source": "email", "automation": "automatic"},
                )
                document, _version = persist_extraction(
                    document=document,
                    batch=batch,
                    user=user,
                    result=data,
                    allow_company_admin=True,
                )
                batch.status = OCRBatch.Status.COMPLETED
                batch.completed_at = timezone.now()
                batch.save(update_fields=["status", "completed_at"])
                # Keep the terminal row through two later successful syncs so
                # an overlap-window fetch cannot re-run this email.
                locked.dedupe_syncs_remaining = 2
                locked.lease_owner = ""
                locked.lease_expires_at = None
                locked.next_attempt_at = None
                locked.save(update_fields=[
                    "dedupe_syncs_remaining", "lease_owner", "lease_expires_at",
                    "next_attempt_at", "updated_at",
                ])
            self._validate_and_post(document_id=document.id, user=user, connection_id=connection.id if connection else None)
            return "promoted"
        except Exception as exc:
            self._defer(message.id, exc)
            return "deferred"

    @staticmethod
    def _mark_terminal(*, message_id, lease_owner: str, is_vendor_bill: bool, extracted_data) -> None:
        """Retain a terminal message until two later successful syncs."""
        EmailMessage.objects.filter(pk=message_id, lease_owner=lease_owner).update(
            is_vendor_bill=is_vendor_bill,
            ai_extracted_data_json=extracted_data,
            dedupe_syncs_remaining=2,
            lease_owner="",
            lease_expires_at=None,
            next_attempt_at=None,
        )

    def _validate_and_post(self, *, document_id, user, connection_id):
        if not connection_id:
            logger.warning("Email OCR document awaits NetSuite connection — document=%s", document_id)
            return
        try:
            validation = NetSuiteValidationService().validate_document(
                document_id=document_id, connection_id=connection_id, user=user
            )
            if validation.get("status") != "VALIDATED":
                if validation.get("validation_id") and validation.get("errors"):
                    try:
                        net_suite_diagnostics_service.diagnose_and_persist(
                            company=user.company, connection_id=connection_id,
                            validation_ids=[str(validation["validation_id"])],
                        )
                    except Exception:
                        logger.exception("Email OCR AI diagnostics failed — document=%s", document_id)
                return
            NetSuiteVendorBillPostingService().post_vendor_bill(
                document_id=document_id, connection_id=connection_id, user=user
            )
        except Exception as exc:
            # Existing validation/posting services persist their user-visible outcomes.
            logger.warning("Email OCR auto validation/posting stopped — document=%s error=%s", document_id, exc)
