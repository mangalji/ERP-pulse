"""Promote staged email bodies through the existing OCR and NetSuite workflow."""

from __future__ import annotations

from common.timing import timed_stage

import hashlib
import json
import logging
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.models import AuditAction, AuditModule, AuditStatus
from audit.services import audit_service
from mail_integration.models import EmailIntegration, EmailMessage
from mail_integration.mailbox import readable_email_body
from mail_integration.sync import dedupe_syncs_to_retain
from netsuite.repositories import NetSuiteConnectionRepository
from netsuite.diagnostics_service import net_suite_diagnostics_service
from netsuite.services import NetSuiteValidationService, NetSuiteVendorBillPostingService
from ocr.models import DocumentType, OCRBatch, OCRDocument, OCRDocumentStatus
from ocr.ai_extraction_service import ai_extractor
from ocr.services.extraction_persistence import persist_extraction
from audit.notifications import automated_activity, notify
from tenancy.services import company_lifecycle_service

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
                integration__company__status="ACTIVE",
                integration__company__is_deleted=False,
            )
            .select_related("integration", "integration__created_by", "integration__ocr_template", "integration__company")
            .order_by("received_at", "created_at")[:limit]
        )
        outcome = {
            "processed": 0,
            "promoted": 0,
            "discarded": 0,
            "deferred": 0,
            "by_integration": {},
        }
        for candidate in candidates:
            result = self.process_message(message_id=candidate.id)
            outcome["processed"] += 1
            per_integration = outcome["by_integration"].setdefault(
                str(candidate.integration_id),
                {"processed": 0, "promoted": 0, "discarded": 0, "deferred": 0},
            )
            per_integration["processed"] += 1
            if result == "promoted":
                outcome["promoted"] += 1
                per_integration["promoted"] += 1
            elif result == "discarded":
                outcome["discarded"] += 1
                per_integration["discarded"] += 1
            else:
                outcome["deferred"] += 1
                per_integration["deferred"] += 1
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
            if not company_lifecycle_service.is_operational(
                company=message.integration.company
            ):
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
        if message:
            audit_service.log(
                module=AuditModule.EMAIL,
                action=AuditAction.PROCESS,
                entity="Email processing deferred",
                entity_id=str(message.id),
                company=message.integration.company,
                activity_type="automated",
                status=AuditStatus.FAILED,
                detail={
                    "summary": f"Processing deferred for email from {message.sender_email or 'unknown sender'}.",
                    **self._message_metadata(message),
                    "attempt": message.attempt_count,
                    "retry_at": (timezone.now() + timedelta(minutes=RETRY_DELAY_MINUTES)).isoformat(),
                    "error": str(error)[:2000],
                },
            )
        if message and message.attempt_count == 1:
            from audit.notifications import notify
            notify(message.integration.created_by_id, message.integration.company_id, f'Email processing failed for {message.sender_email or "unknown sender"}; it will be retried.', '/app/integrations/email')

    @automated_activity
    @timed_stage("email.process_message")
    def process_message(self, *, message_id) -> str:
        message = self._claim(message_id)
        if message is None:
            return "deferred"
        integration = message.integration
        # A suspension can happen after the message was claimed. Release the
        # lease before doing any NetSuite/OCR work so the company is fully
        # quiescent until it is explicitly activated again.
        if not company_lifecycle_service.is_operational(company=integration.company):
            EmailMessage.objects.filter(
                pk=message.id,
                lease_owner=message.lease_owner,
            ).update(
                lease_owner="",
                lease_expires_at=None,
                updated_at=timezone.now(),
            )
            return "deferred"
        user = integration.created_by
        template = integration.ocr_template
        if user is None or template is None:
            self._defer(message.id, ValueError("Mailbox requires an owner and OCR template before processing."))
            return "deferred"
        try:
            # Sender email is the first and only vendor-bill gate.  AI is not
            # called until the sender has an active vendor record in NetSuite.
            # This avoids AI cost for ordinary mailbox traffic and makes the
            # vendor identity deterministic.
            connection = NetSuiteConnectionRepository().get_for_user(user)
            validation_service = NetSuiteValidationService()
            sender_vendor_data = {}
            sender_vendor = validation_service.resolve_vendor_from_sender_email(
                data=sender_vendor_data,
                requested_fields=template.fields_config,
                user=user,
                sender_email=message.sender_email,
                connection=connection,
            )
            if not sender_vendor.get("matched"):
                reason = sender_vendor.get("reason") or "vendor_email_not_found"
                logger.info(
                    "AI EXTRACTION DEBUG | source=email | message=%s | "
                    "AI SKIPPED | reason=%s | sender=%s | subject=%s",
                    message.id,
                    reason,
                    message.sender_email or "unknown",
                    (message.subject or "")[:250],
                )
                if reason in {"vendor_email_not_found", "sender_email_missing"}:
                    self._mark_terminal(
                        message_id=message.id,
                        lease_owner=message.lease_owner,
                        integration=integration,
                        is_vendor_bill=False,
                        extracted_data=None,
                    )
                    audit_service.log(
                        module=AuditModule.EMAIL,
                        action=AuditAction.PROCESS,
                        entity="Email sender not matched to a NetSuite vendor",
                        entity_id=str(message.id),
                        company=integration.company,
                        activity_type="automated",
                        status=AuditStatus.INFO,
                        detail={
                            "summary": "Email was ignored because its sender is not an active NetSuite vendor.",
                            **self._message_metadata(message),
                            "classification": "not_vendor_bill",
                            "vendor_lookup_reason": reason,
                        },
                    )
                    return "discarded"
                self._defer(
                    message.id,
                    ValueError(
                        f"NetSuite sender-email vendor lookup could not complete: {reason}. "
                        f"{sender_vendor.get('error') or ''}".strip()
                    ),
                )
                return "deferred"

            # A successful classification/extraction is retained in staging
            # until it has been promoted atomically. A retry resumes from that
            # data without a second AI request, while sender resolution still
            # occurs above.
            if message.is_vendor_bill is True and isinstance(message.ai_extracted_data_json, dict):
                logger.info(
                    "AI EXTRACTION DEBUG | source=email | message=%s | "
                    "AI SKIPPED | reason=already_extracted_cached_result\n"
                    "CACHED TEMPLATE-MAPPED RESULT:\n%s\n"
                    "RAW AI RESPONSE: unavailable (not retained in the existing cache)",
                    message.id,
                    json.dumps(
                        message.ai_extracted_data_json,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    ),
                )
                data = dict(message.ai_extracted_data_json)
                data.update(sender_vendor_data)
                self._notify_vendor_bill_detected(message)
            else:
                logger.info(
                    "AI EXTRACTION DEBUG | source=email | message=%s | "
                    "AI STARTING | sender=%s | subject=%s | template=%s",
                    message.id,
                    message.sender_email or "unknown",
                    (message.subject or "")[:250],
                    template.name,
                )
                classification = ai_extractor.extract_email_text(
                    message.normalized_body or message.raw_body,
                    requested_fields=template.fields_config,
                    company=integration.company,
                    email_received_at=message.received_at,
                )
                if classification.get("is_vendor_bill") is not True:
                    self._mark_terminal(
                        message_id=message.id,
                        lease_owner=message.lease_owner,
                        integration=integration,
                        is_vendor_bill=False,
                        extracted_data=None,
                    )
                    audit_service.log(
                        module=AuditModule.EMAIL,
                        action=AuditAction.PROCESS,
                        entity="Vendor email classified as not a vendor bill",
                        entity_id=str(message.id),
                        company=integration.company,
                        activity_type="automated",
                        status=AuditStatus.INFO,
                        detail={
                            "summary": (
                                f"A known vendor's email from {message.sender_email or 'unknown sender'} "
                                "was classified as ordinary mailbox traffic and was ignored."
                            ),
                            **self._message_metadata(message),
                            "classification": "not_vendor_bill",
                            "vendor_lookup_reason": "sender_matched_but_message_not_bill",
                        },
                    )
                    return "discarded"
                data = classification.get("data")
                if not isinstance(data, dict):
                    raise ValueError("Vendor-bill email classification did not include extraction data.")
                data.update(sender_vendor_data)
                classified = EmailMessage.objects.filter(
                    pk=message.id,
                    lease_owner=message.lease_owner,
                    vendor_bill_notification_sent=False,
                ).update(
                    is_vendor_bill=True,
                    ai_extracted_data_json=data,
                    vendor_bill_notification_sent=True,
                )
                if classified:
                    audit_service.log(
                        module=AuditModule.AI,
                        action=AuditAction.PROCESS,
                        entity="Vendor-bill email extracted",
                        entity_id=str(message.id),
                        company=integration.company,
                        activity_type="automated",
                        status=AuditStatus.SUCCESS,
                        detail={
                            "summary": f"Vendor-matched email from {message.sender_email or 'unknown sender'} was extracted.",
                            **self._message_metadata(message),
                            "classification": "vendor_bill",
                            "extracted_fields": sorted(str(key) for key in data.keys())[:100],
                        },
                    )
                    notify(
                        integration.created_by_id,
                        integration.company_id,
                        f"Vendor-bill email detected from {message.sender_email or 'unknown sender'}; processing started.",
                        "/app/integrations/email",
                        activity_type="automated",
                    )

            if not isinstance(data, dict):
                raise ValueError("Vendor-bill email extraction did not return JSON data.")

            # Resolve missing vendor defaults before taking the message lock.
            # This can make a NetSuite request, and holding a row lock while
            # waiting for an external service would unnecessarily block retry.
            enrichment = validation_service.enrich_transaction_references(
                data=data,
                # The OCR batch is created only after enrichment succeeds.
                # Use the selected integration template here; the same
                # configuration is snapshotted onto the batch below.
                requested_fields=template.fields_config,
                user=user,
                connection=connection,
            )
            if enrichment.get("changed"):
                logger.info(
                    "Email vendor reference enrichment completed — message=%s vendor=%s fields=%s",
                    message.id,
                    enrichment.get("vendor_id"),
                    ",".join(sorted(enrichment["changed"])),
                )
            elif enrichment.get("reason") not in {
                "nothing_missing_or_not_mapped",
                "no_active_connection",
            }:
                logger.info(
                    "Email vendor reference enrichment skipped — message=%s reason=%s",
                    message.id,
                    enrichment.get("reason"),
                )

            with transaction.atomic():
                locked = EmailMessage.objects.select_for_update().select_related("integration").get(pk=message.id)
                if locked.lease_owner != message.lease_owner:
                    return "deferred"
                if not EmailIntegration.objects.filter(pk=locked.integration_id, is_active=True, is_paused=False, status=EmailIntegration.Status.CONNECTED).exists():
                    locked.lease_owner = ""
                    locked.lease_expires_at = None
                    locked.save(update_fields=["lease_owner", "lease_expires_at", "updated_at"])
                    return "deferred"
                # The staged result is required for recovery.  The local copy
                # below is the same result, optionally enriched before this
                # transaction with safe vendor defaults from NetSuite.
                if not isinstance(locked.ai_extracted_data_json, dict):
                    raise ValueError("Vendor-bill email staging data is missing.")
                # Persist sender-email vendor resolution and any NetSuite
                # defaults with the staged message as well as the OCR record.
                locked.ai_extracted_data_json = data
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
                        integration=locked.integration,
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
                # Retain through every overlapping sync so a delayed provider
                # listing cannot send the same email through OCR twice.
                locked.dedupe_syncs_remaining = dedupe_syncs_to_retain(integration)
                locked.lease_owner = ""
                locked.lease_expires_at = None
                locked.next_attempt_at = None
                locked.save(update_fields=[
                    "ai_extracted_data_json",
                    "dedupe_syncs_remaining", "lease_owner", "lease_expires_at",
                    "next_attempt_at", "updated_at",
                ])
            audit_service.log(
                module=AuditModule.OCR,
                action=AuditAction.CREATE,
                entity="OCR document created from email",
                entity_id=str(document.id),
                company=integration.company,
                activity_type="automated",
                status=AuditStatus.SUCCESS,
                detail={
                    "summary": "Email extraction was saved as an OCR record.",
                    **self._message_metadata(message),
                    "document_id": str(document.id),
                    "source": "email",
                },
            )
            if sender_vendor.get("matched"):
                audit_service.log(
                    module=AuditModule.NETSUITE,
                    action=AuditAction.PROCESS,
                    entity="Vendor resolved from email sender",
                    entity_id=str(document.id),
                    company=integration.company,
                    activity_type="automated",
                    status=AuditStatus.SUCCESS,
                    detail={
                        "summary": "The email sender was matched to the latest active NetSuite vendor.",
                        **self._message_metadata(message),
                        "document_id": str(document.id),
                        "vendor_id": sender_vendor.get("vendor_id"),
                        "vendor_name": sender_vendor.get("vendor_name"),
                    },
                )
            if enrichment.get("changed"):
                audit_service.log(
                    module=AuditModule.NETSUITE,
                    action=AuditAction.PROCESS,
                    entity="Vendor defaults enriched from NetSuite",
                    entity_id=str(document.id),
                    company=integration.company,
                    activity_type="automated",
                    status=AuditStatus.SUCCESS,
                    detail={
                        "summary": "Missing vendor-bill reference fields were filled from the matched NetSuite vendor.",
                        **self._message_metadata(message),
                        "document_id": str(document.id),
                        "vendor_id": enrichment.get("vendor_id"),
                        "filled_fields": enrichment["changed"],
                    },
                )
            self._validate_and_post(
                document_id=document.id,
                user=user,
                connection_id=connection.id if connection else None,
            )
            return "promoted"
        except Exception as exc:
            self._defer(message.id, exc)
            return "deferred"

    @staticmethod
    def _mark_terminal(*, message_id, lease_owner: str, integration, is_vendor_bill: bool, extracted_data) -> None:
        """Retain a terminal message until its full provider overlap has elapsed."""
        EmailMessage.objects.filter(pk=message_id, lease_owner=lease_owner).update(
            is_vendor_bill=is_vendor_bill,
            ai_extracted_data_json=extracted_data,
            dedupe_syncs_remaining=dedupe_syncs_to_retain(integration),
            lease_owner="",
            lease_expires_at=None,
            next_attempt_at=None,
        )

    @staticmethod
    def _notify_vendor_bill_detected(message: EmailMessage) -> None:
        """Backfill the detection notification for a safely resumed message."""
        notified = EmailMessage.objects.filter(
            pk=message.id,
            vendor_bill_notification_sent=False,
        ).update(vendor_bill_notification_sent=True)
        if notified:
            notify(
                message.integration.created_by_id,
                message.integration.company_id,
                f"Vendor-bill email detected from {message.sender_email or 'unknown sender'}; processing started.",
                "/app/integrations/email",
                activity_type="automated",
            )

    @staticmethod
    def _message_metadata(message: EmailMessage) -> dict:
        """Safe message evidence for audit logs; deliberately excludes bodies."""
        return {
            "provider_message_id": message.provider_message_id or None,
            "internet_message_id": message.internet_message_id or None,
            "sender": message.sender_email or None,
            "subject": (message.subject or "")[:500] or None,
            "sent_at": message.sent_at.isoformat() if message.sent_at else None,
            "received_at": message.received_at.isoformat() if message.received_at else None,
        }

    def _validate_and_post(self, *, document_id, user, connection_id):
        if not connection_id:
            logger.warning("Email OCR document awaits NetSuite connection — document=%s", document_id)
            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.VALIDATE,
                entity="Automatic validation deferred",
                entity_id=str(document_id),
                company=user.company,
                activity_type="automated",
                status=AuditStatus.INFO,
                detail={"summary": "No active NetSuite connection was available for this email OCR record.", "document_id": str(document_id)},
            )
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
                audit_service.log(
                    module=AuditModule.NETSUITE,
                    action=AuditAction.VALIDATE,
                    entity="Vendor bill validation failed",
                    entity_id=str(document_id),
                    company=user.company,
                    activity_type="automated",
                    status=AuditStatus.FAILED,
                    detail={
                        "summary": "NetSuite validation failed; the OCR record requires review.",
                        "document_id": str(document_id),
                        "connection_id": str(connection_id),
                        "validation_id": str(validation.get("validation_id") or "") or None,
                        "errors": validation.get("errors") or [],
                    },
                )
                return
            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.VALIDATE,
                entity="Vendor bill validation succeeded",
                entity_id=str(document_id),
                company=user.company,
                activity_type="automated",
                status=AuditStatus.SUCCESS,
                detail={"summary": "NetSuite validation succeeded; automatic posting started.", "document_id": str(document_id), "connection_id": str(connection_id)},
            )
            posting = NetSuiteVendorBillPostingService().post_vendor_bill(
                document_id=document_id, connection_id=connection_id, user=user
            )
            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.POST,
                entity="Vendor bill posted automatically",
                entity_id=str(document_id),
                company=user.company,
                activity_type="automated",
                status=AuditStatus.SUCCESS,
                detail={
                    "summary": "Vendor bill was posted to NetSuite automatically.",
                    "document_id": str(document_id),
                    "connection_id": str(connection_id),
                    "netsuite_record_id": (posting or {}).get("netsuite_record_id") if isinstance(posting, dict) else None,
                },
            )
        except Exception as exc:
            # Existing validation/posting services persist their user-visible outcomes.
            logger.warning("Email OCR auto validation/posting stopped — document=%s error=%s", document_id, exc)
            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.POST,
                entity="Automatic validation or posting failed",
                entity_id=str(document_id),
                company=user.company,
                activity_type="automated",
                status=AuditStatus.FAILED,
                detail={"summary": "Automatic NetSuite processing stopped; review the OCR record.", "document_id": str(document_id), "connection_id": str(connection_id), "error": str(exc)[:2000]},
            )
