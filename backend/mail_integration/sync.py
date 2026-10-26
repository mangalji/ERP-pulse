"""Fetch new mailbox messages and durably stage them before AI processing."""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from mail_integration.client import EmailOAuthClient
from mail_integration.exceptions import EmailIntegrationOAuthError, EmailIntegrationStateError, EmailMailboxFetchError
from mail_integration.mailbox import IncomingMailboxMessage, mailbox_client_for
from mail_integration.models import EmailIntegration, EmailMessage


logger = logging.getLogger(__name__)
SYNC_LOOKBACK = timedelta(minutes=5)
RETRY_DELAY = timedelta(minutes=10)
TOKEN_REFRESH_SKEW = timedelta(seconds=60)


class EmailSyncService:
    """Idempotent mailbox-to-staging synchronisation; no AI work belongs here."""

    def sync_due_integrations(self) -> dict:
        now = timezone.now()
        due = EmailIntegration.objects.filter(
            status=EmailIntegration.Status.CONNECTED,
            is_active=True,
            is_paused=False,
            initial_sync_from_at__isnull=False,
        ).filter(Q(next_sync_at__isnull=True) | Q(next_sync_at__lte=now))
        outcomes = {"checked": 0, "staged": 0, "failed": 0}
        for integration_id in due.values_list("id", flat=True):
            outcomes["checked"] += 1
            try:
                outcomes["staged"] += self.sync_integration(integration_id=integration_id)
            except Exception:  # Individual mailbox failures must not block others.
                outcomes["failed"] += 1
                logger.exception("Email mailbox sync failed — integration=%s", integration_id)
        return outcomes

    def sync_integration(self, *, integration_id) -> int:
        integration = EmailIntegration.objects.get(id=integration_id)
        if integration.status != EmailIntegration.Status.CONNECTED or not integration.is_active or integration.is_paused:
            return 0
        if integration.initial_sync_from_at is None:
            raise EmailIntegrationStateError("Initial email sync is not configured.")

        now = timezone.now()
        since = integration.last_successful_sync_at or integration.initial_sync_from_at
        # The overlap protects messages delivered at a provider timestamp boundary.
        if integration.last_successful_sync_at:
            since -= SYNC_LOOKBACK

        try:
            self._refresh_access_token_if_needed(integration)
            self._verify_mailbox_identity(integration)
            staged = 0
            for message in mailbox_client_for(integration).iter_messages_since(since):
                if not EmailIntegration.objects.filter(pk=integration.id, status=EmailIntegration.Status.CONNECTED, is_active=True, is_paused=False).exists():
                    return staged
                staged += int(self._stage_message(integration=integration, message=message))
        except EmailIntegrationOAuthError as exc:
            self._record_failure(integration=integration, error=str(exc), authorization_error=exc.authorization_required)
            raise
        except EmailMailboxFetchError as exc:
            self._record_failure(
                integration=integration,
                error=str(exc),
                authorization_error=str(exc).startswith("MAILBOX_AUTHORIZATION_REQUIRED:"),
            )
            raise
        except Exception as exc:
            self._record_failure(integration=integration, error=str(exc), authorization_error=False)
            raise

        # Advance only after every page and message has been durably staged.
        # A terminal message stays for two *future successful* syncs.  This is
        # deliberately sync-count based: a failed mailbox fetch must not make
        # the overlap-window de-duplication marker disappear.
        self._advance_terminal_dedupe(integration)
        integration.last_successful_sync_at = now
        integration.next_sync_at = now + timedelta(minutes=integration.sync_interval_minutes)
        integration.last_error = ""
        integration.consecutive_failures = 0
        integration.provider_cursor = now.isoformat()
        integration.save(update_fields=[
            "last_successful_sync_at", "next_sync_at", "last_error",
            "consecutive_failures", "provider_cursor", "updated_at",
        ])
        return staged

    @staticmethod
    def _verify_mailbox_identity(integration: EmailIntegration) -> None:
        """Verify legacy connections once before allowing mailbox reads."""
        metadata = dict(integration.provider_metadata or {})
        expected = integration.mailbox_email.casefold()
        if str(metadata.get("authorized_mailbox_email") or "").casefold() == expected:
            return
        actual_email, identity_metadata = EmailOAuthClient(
            integration=integration,
        ).authorized_mailbox_identity(access_token=integration.access_token)
        if actual_email.casefold() != expected:
            raise EmailMailboxFetchError(
                "MAILBOX_AUTHORIZATION_REQUIRED: The authorized mailbox does not match this connection. Reconnect it."
            )
        integration.provider_metadata = {
            **metadata,
            **identity_metadata,
            "authorized_mailbox_email": actual_email,
        }
        integration.save(update_fields=["provider_metadata", "updated_at"])

    @staticmethod
    def _advance_terminal_dedupe(integration: EmailIntegration) -> None:
        retained = EmailMessage.objects.filter(
            integration=integration,
            dedupe_syncs_remaining__isnull=False,
        )
        retained.filter(dedupe_syncs_remaining__lte=1).delete()
        retained.filter(dedupe_syncs_remaining__gt=1).update(
            dedupe_syncs_remaining=F("dedupe_syncs_remaining") - 1,
        )

    def _refresh_access_token_if_needed(self, integration: EmailIntegration) -> None:
        expires_at = integration.access_token_expires_at
        if expires_at and expires_at > timezone.now() + TOKEN_REFRESH_SKEW:
            return
        token_set = EmailOAuthClient(integration=integration).refresh_access_token()
        integration.access_token = token_set.access_token
        integration.refresh_token = token_set.refresh_token or integration.refresh_token
        integration.access_token_expires_at = token_set.access_token_expires_at
        integration.provider_metadata = token_set.provider_metadata
        EmailIntegration.objects.filter(pk=integration.pk, status=EmailIntegration.Status.CONNECTED, is_active=True, is_paused=False).update(
            access_token=integration.access_token, refresh_token=integration.refresh_token,
            access_token_expires_at=integration.access_token_expires_at,
            provider_metadata=integration.provider_metadata, updated_at=timezone.now(),
        )

    def _stage_message(self, *, integration: EmailIntegration, message: IncomingMailboxMessage) -> bool:
        body_hash = hashlib.sha256(message.normalized_body.encode("utf-8")).hexdigest()
        # Provider IDs are primary de-duplication. The fallback tuple avoids
        # accepting a duplicate if a provider omits that ID in an edge response.
        if message.provider_message_id:
            defaults = self._message_defaults(message, body_hash)
            try:
                _, created = EmailMessage.objects.get_or_create(
                    integration=integration,
                    provider_message_id=message.provider_message_id,
                    defaults=defaults,
                )
                return created
            except IntegrityError:
                return False

        duplicate_filters = Q(
            sender_email=message.sender_email,
            sent_at=message.sent_at,
            body_hash=body_hash,
        )
        if message.internet_message_id:
            duplicate_filters |= Q(internet_message_id=message.internet_message_id)
        if EmailMessage.objects.filter(integration=integration).filter(duplicate_filters).exists():
            return False
        try:
            EmailMessage.objects.create(
                integration=integration,
                provider_message_id="",
                **self._message_defaults(message, body_hash),
            )
            return True
        except IntegrityError:
            return False

    @staticmethod
    def _message_defaults(message: IncomingMailboxMessage, body_hash: str) -> dict:
        return {
            "provider_thread_id": message.provider_thread_id[:512],
            "internet_message_id": message.internet_message_id[:1024],
            "sender_email": message.sender_email[:254],
            "recipient_emails": message.recipient_emails,
            "subject": message.subject,
            "sent_at": message.sent_at,
            "received_at": message.received_at,
            "raw_body": message.raw_body,
            "normalized_body": message.normalized_body,
            "body_hash": body_hash,
        }

    @staticmethod
    def _record_failure(*, integration: EmailIntegration, error: str, authorization_error: bool) -> None:
        integration.consecutive_failures += 1
        integration.last_error = error[:2000]
        integration.next_sync_at = timezone.now() + RETRY_DELAY
        if authorization_error:
            integration.status = EmailIntegration.Status.ERROR
        updated = EmailIntegration.objects.filter(pk=integration.pk, status=EmailIntegration.Status.CONNECTED, is_active=True, is_paused=False).update(
            status=integration.status, consecutive_failures=integration.consecutive_failures,
            last_error=integration.last_error, next_sync_at=integration.next_sync_at, updated_at=timezone.now(),
        )
        if updated:
            from audit.notifications import notify
            message = f'Email connection {integration.mailbox_email} needs to be reconnected.' if authorization_error else f'Email sync failed for {integration.mailbox_email}; it will be retried.'
            notify(integration.created_by_id, integration.company_id, message, '/app/integrations/email', activity_type='automated')
