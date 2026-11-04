"""Company-scoped mailbox OAuth and configuration service."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from audit.models import AuditAction, AuditModule, AuditStatus
from audit.services import audit_service
from mail_integration.client import EmailOAuthClient
from mail_integration.exceptions import (
    EmailIntegrationNotFoundError,
    EmailIntegrationStateError,
)
from mail_integration.models import EmailIntegration
from mail_integration.oauth import (
    build_authorization_url,
    resolve_state,
    validate_oauth_configuration,
)
from tenancy.services import company_lifecycle_service


def is_company_admin(user) -> bool:
    return bool(
        getattr(user, "is_superuser", False)
        or (
            getattr(user, "company_id", None)
            and getattr(user, "role", None) is not None
            and user.role.name.lower() == "company admin"
        )
    )


class EmailIntegrationService:
    def _ensure_operational(self, *, user: User) -> None:
        company = getattr(user, "company", None)
        if company is None:
            raise PermissionError("A company account is required.")
        company_lifecycle_service.ensure_operational(company=company)

    def _get_for_user(self, *, user: User, integration_id, lock=False):
        query = EmailIntegration.objects.filter(id=integration_id, company_id=user.company_id)
        if lock:
            query = query.select_for_update()
        integration = query.first()
        if integration is None:
            raise EmailIntegrationNotFoundError("Email integration not found.")
        return integration

    def list_company_integrations(self, *, user: User):
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")
        return EmailIntegration.objects.filter(company_id=user.company_id).order_by("-created_at")

    def create_connection(self, *, user: User, **data):
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")

        ocr_template_id = data.pop("ocr_template_id", None)
        client_id = data.pop("client_id", None)
        client_secret = data.pop("client_secret", None)
        provider_metadata = {}
        if data["provider"] == EmailIntegration.Provider.ZOHO:
            provider_metadata["zoho_data_center"] = data.get("zoho_data_center", "IN")

        # Validate deployment credentials before modifying any connection row.
        existing = EmailIntegration.objects.filter(company_id=user.company_id, provider=data["provider"], mailbox_email=data["mailbox_email"].lower()).first()
        configuration_probe = EmailIntegration(
            provider=data["provider"],
            provider_metadata=provider_metadata,
            oauth_client_id=client_id or (existing.oauth_client_id if existing else ""),
            oauth_client_secret=client_secret or (existing.oauth_client_secret if existing else None),
        )
        validate_oauth_configuration(integration=configuration_probe)

        try:
            with transaction.atomic():
                integration, created = EmailIntegration.objects.get_or_create(
                    company_id=user.company_id,
                    provider=data["provider"],
                    mailbox_email=data["mailbox_email"].lower(),
                    defaults={
                        "created_by": user,
                        "display_name": data.get("display_name", ""),
                        "provider_metadata": provider_metadata,
                        "ocr_template_id": ocr_template_id,
                        "oauth_client_id": client_id or "",
                        "oauth_client_secret": client_secret,
                    },
                )
                if not created:
                    integration.display_name = data.get("display_name", integration.display_name)
                    integration.provider_metadata = provider_metadata
                    if ocr_template_id is not None:
                        integration.ocr_template_id = ocr_template_id
                    integration.status = EmailIntegration.Status.PENDING
                    integration.last_error = ""
                    if client_id and client_secret:
                        integration.oauth_client_id = client_id
                        integration.oauth_client_secret = client_secret
                    integration.save(
                        update_fields=[
                            "display_name",
                            "provider_metadata",
                            "ocr_template",
                            "oauth_client_id",
                            "oauth_client_secret",
                            "status",
                            "last_error",
                            "updated_at",
                        ]
                    )
        except IntegrityError as exc:
            raise EmailIntegrationStateError("Could not prepare this mailbox connection.") from exc

        audit_service.log(
            module=AuditModule.SETTINGS,
            action=AuditAction.CREATE if created else AuditAction.UPDATE,
            entity="EmailIntegration",
            entity_id=str(integration.id),
            company=user.company,
            user=user,
            new_value={"event": "oauth_started", "provider": integration.provider, "mailbox": integration.mailbox_email},
        )
        return integration, build_authorization_url(integration=integration, user_id=str(user.id))

    def complete_oauth(self, *, code: str, state: str) -> EmailIntegration:
        payload = resolve_state(state)
        try:
            user = User.objects.select_related("company", "role").get(id=payload["user_id"])
        except User.DoesNotExist as exc:
            raise EmailIntegrationStateError("Invalid OAuth state parameter.") from exc

        self._ensure_operational(user=user)
        try:
            with transaction.atomic():
                integration = self._get_for_user(
                    user=user,
                    integration_id=payload["integration_id"],
                    lock=True,
                )
                if integration.provider != payload["provider"]:
                    raise EmailIntegrationStateError("OAuth provider does not match the mailbox.")
                if not is_company_admin(user):
                    raise EmailIntegrationStateError("The authorizing user can no longer manage email integrations.")

                oauth_client = EmailOAuthClient(integration=integration)
                token_set = oauth_client.exchange_code(code=code)
                authorized_email, identity_metadata = oauth_client.authorized_mailbox_identity(
                    access_token=token_set.access_token,
                )
                if authorized_email.casefold() != integration.mailbox_email.casefold():
                    raise EmailIntegrationStateError(
                        "Authorize the same mailbox email that was entered for this connection."
                    )
                if not token_set.refresh_token and (
                    not integration.refresh_token or integration.status == EmailIntegration.Status.ERROR
                ):
                    from mail_integration.exceptions import EmailRefreshTokenMissingError
                    raise EmailRefreshTokenMissingError(
                        "The email provider did not issue a refresh token. Reconnect and approve access again."
                    )
                integration.access_token = token_set.access_token
                integration.refresh_token = token_set.refresh_token or integration.refresh_token
                integration.access_token_expires_at = token_set.access_token_expires_at
                integration.provider_metadata = {
                    **token_set.provider_metadata,
                    **identity_metadata,
                    "authorized_mailbox_email": authorized_email,
                }
                integration.status = EmailIntegration.Status.CONNECTED
                integration.last_error = ""
                integration.consecutive_failures = 0
                if not EmailIntegration.objects.filter(
                    company_id=user.company_id,
                    is_active=True,
                ).exclude(pk=integration.pk).exists():
                    integration.is_active = True
                integration.save(
                    update_fields=[
                        "access_token",
                        "refresh_token",
                        "access_token_expires_at",
                        "provider_metadata",
                        "status",
                        "last_error",
                        "consecutive_failures",
                        "is_active",
                        "updated_at",
                    ]
                )
        except Exception as exc:
            # The OAuth work above is atomic. Persist the failure only after
            # that transaction has rolled back, otherwise the ERROR state and
            # audit record are rolled back with the failed token exchange.
            self._mark_oauth_failed(
                user=user,
                payload=payload,
                error_message=str(exc),
            )
            raise

        from audit.integration_alerts import mark_integration_healthy
        from audit.models import IntegrationFailureAlert
        mark_integration_healthy(
            integration_type=IntegrationFailureAlert.IntegrationType.EMAIL,
            connection_id=str(integration.id),
            company=integration.company,
        )

        audit_service.log(
            module=AuditModule.SETTINGS,
            action=AuditAction.CONNECT,
            entity="EmailIntegration",
            entity_id=str(integration.id),
            company=user.company,
            user=user,
            new_value={"event": "oauth_completed", "provider": integration.provider, "mailbox": integration.mailbox_email},
        )
        return integration

    def mark_oauth_failed(self, *, state: str, error_message: str) -> None:
        payload = resolve_state(state)
        try:
            user = User.objects.select_related("company").get(id=payload["user_id"])
        except User.DoesNotExist as exc:
            raise EmailIntegrationStateError("Invalid OAuth state parameter.") from exc
        self._mark_oauth_failed(
            user=user,
            payload=payload,
            error_message=error_message,
        )

    def _mark_oauth_failed(self, *, user: User, payload: dict, error_message: str) -> None:
        integration = self._get_for_user(user=user, integration_id=payload["integration_id"])
        if integration.provider != payload["provider"]:
            raise EmailIntegrationStateError("OAuth provider does not match the mailbox.")
        integration.status = EmailIntegration.Status.ERROR
        integration.last_error = error_message[:2000]
        integration.save(update_fields=["status", "last_error", "updated_at"])
        # Unit-level callers may use an unsaved integration to validate the
        # OAuth state transition. Only persisted connections have an audit or
        # failure-alert identity to record.
        if integration._state.adding:
            return
        audit_service.log(
            module=AuditModule.EMAIL,
            action=AuditAction.CONNECT,
            entity="EmailIntegration",
            entity_id=str(integration.id),
            company=user.company,
            user=user,
            status=AuditStatus.FAILED,
            new_value={
                "event": "oauth_failed",
                "provider": integration.provider,
                "mailbox": integration.mailbox_email,
            },
            detail={"summary": "Email OAuth authorization failed.", "reason": integration.last_error},
        )
        from audit.integration_alerts import report_integration_failure
        from audit.models import IntegrationFailureAlert
        report_integration_failure(
            integration_type=IntegrationFailureAlert.IntegrationType.EMAIL,
            connection_id=str(integration.id),
            company=user.company,
            owner=integration.created_by,
            connection_label=integration.display_name or integration.mailbox_email,
            provider=integration.provider,
            error=integration.last_error,
            reconnect_path='/app/integrations/email',
        )

    def activate(self, *, user: User, integration_id):
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")
        with transaction.atomic():
            integration = self._get_for_user(user=user, integration_id=integration_id, lock=True)
            if integration.status != EmailIntegration.Status.CONNECTED:
                raise EmailIntegrationStateError("Only a connected mailbox can be active.")
            EmailIntegration.objects.filter(company_id=user.company_id, is_active=True).update(is_active=False)
            integration.is_active = True
            update_fields = ["is_active", "updated_at"]
            if integration.initial_sync_from_at is not None and not integration.is_paused:
                integration.next_sync_at = timezone.now()
                update_fields.append("next_sync_at")
            integration.save(update_fields=update_fields)
        return integration

    def check_initial_sync_ready(self, *, user: User, integration_id):
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")
        integration = self._get_for_user(user=user, integration_id=integration_id)
        if integration.status != EmailIntegration.Status.CONNECTED:
            raise EmailIntegrationStateError("Connect the mailbox before configuring email sync.")
        if not integration.is_active:
            raise EmailIntegrationStateError(
                "Make this mailbox active before starting automatic email processing."
            )
        if integration.initial_sync_from_at is not None:
            raise EmailIntegrationStateError("Initial email sync is already configured.")

        from mail_integration.health import ensure_email_processing_available
        ensure_email_processing_available()
        return integration

    def set_paused(self, *, user: User, integration_id, paused: bool):
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")
        integration = self._get_for_user(user=user, integration_id=integration_id)
        if integration.status != EmailIntegration.Status.CONNECTED:
            raise EmailIntegrationStateError("Connect the mailbox before changing automatic processing.")
        if not paused:
            if not integration.is_active or integration.initial_sync_from_at is None:
                raise EmailIntegrationStateError("Make this mailbox active and configure its initial sync first.")
            from mail_integration.health import ensure_email_processing_available
            ensure_email_processing_available()
            integration.next_sync_at = timezone.now()
        integration.is_paused = paused
        integration.save(update_fields=["is_paused", "next_sync_at", "updated_at"])
        return integration

    def disconnect(self, *, user: User, integration_id):
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")
        with transaction.atomic():
            integration = self._get_for_user(user=user, integration_id=integration_id, lock=True)
            integration.status = EmailIntegration.Status.DISCONNECTED
            integration.is_active = False
            integration.is_paused = True
            integration.access_token = None
            integration.refresh_token = None
            integration.access_token_expires_at = None
            integration.next_sync_at = None
            integration.initial_sync_from_at = None
            integration.last_successful_sync_at = None
            integration.provider_cursor = ""
            integration.last_error = ""
            integration.save(update_fields=["status", "is_active", "is_paused", "access_token", "refresh_token", "access_token_expires_at", "initial_sync_from_at", "last_successful_sync_at", "provider_cursor", "next_sync_at", "last_error", "updated_at"])
        return integration

    def delete_disconnected(self, *, user: User, integration_id):
        """Permanently remove a mailbox only after it has been disconnected."""
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")
        with transaction.atomic():
            integration = self._get_for_user(
                user=user,
                integration_id=integration_id,
                lock=True,
            )
            if integration.status != EmailIntegration.Status.DISCONNECTED:
                raise EmailIntegrationStateError(
                    "Disconnect this mailbox before deleting it."
                )
            audit_service.log(
                module=AuditModule.EMAIL,
                action=AuditAction.DELETE,
                entity="EmailIntegration",
                entity_id=str(integration.id),
                company=integration.company,
                user=user,
                old_value={
                    "mailbox_email": integration.mailbox_email,
                    "provider": integration.provider,
                    "status": integration.status,
                },
                detail={"summary": "Disconnected email integration deleted."},
            )
            integration.delete()

    def configure_initial_sync(self, *, user: User, integration_id, initial_sync_from_at):
        integration = self.check_initial_sync_ready(user=user, integration_id=integration_id)
        integration.initial_sync_from_at = initial_sync_from_at
        integration.is_paused = False
        integration.sync_interval_minutes = EmailIntegration.DEFAULT_SYNC_INTERVAL_MINUTES
        integration.next_sync_at = timezone.now()
        integration.save(
            update_fields=[
                "initial_sync_from_at",
                "is_paused",
                "sync_interval_minutes",
                "next_sync_at",
                "updated_at",
            ]
        )
        from audit.integration_alerts import mark_integration_healthy
        from audit.models import IntegrationFailureAlert
        mark_integration_healthy(
            integration_type=IntegrationFailureAlert.IntegrationType.EMAIL,
            connection_id=str(integration.id),
            company=integration.company,
        )
        return integration

    def reconnect_url(self, *, user: User, integration_id) -> tuple[EmailIntegration, str]:
        self._ensure_operational(user=user)
        if not is_company_admin(user):
            raise PermissionError("Only Company Admin can manage email integrations.")
        integration = self._get_for_user(user=user, integration_id=integration_id)
        if integration.status == EmailIntegration.Status.DISCONNECTED and integration.initial_sync_from_at is not None:
            integration.initial_sync_from_at = None
            integration.last_successful_sync_at = None
            integration.provider_cursor = ""
            integration.save(update_fields=["initial_sync_from_at", "last_successful_sync_at", "provider_cursor", "updated_at"])
        return integration, build_authorization_url(integration=integration, user_id=str(user.id))

    def refresh_token(self, *, integration: EmailIntegration) -> EmailIntegration:
        """Reusable by the mailbox-fetch worker in the next phase."""
        token_set = EmailOAuthClient(integration=integration).refresh_access_token()
        integration.access_token = token_set.access_token
        integration.refresh_token = token_set.refresh_token or integration.refresh_token
        integration.access_token_expires_at = token_set.access_token_expires_at
        integration.provider_metadata = token_set.provider_metadata
        integration.status = EmailIntegration.Status.CONNECTED
        integration.last_error = ""
        integration.consecutive_failures = 0
        integration.save(
            update_fields=[
                "access_token", "refresh_token", "access_token_expires_at",
                "provider_metadata", "status", "last_error", "consecutive_failures", "updated_at",
            ]
        )
        from audit.integration_alerts import mark_integration_healthy
        from audit.models import IntegrationFailureAlert

        mark_integration_healthy(
            integration_type=IntegrationFailureAlert.IntegrationType.EMAIL,
            connection_id=str(integration.id),
            company=integration.company,
        )
        return integration
