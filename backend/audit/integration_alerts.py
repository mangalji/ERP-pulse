"""Reliable outbound alerts for broken company integrations.

The checker is deliberately called from Celery work, not from request paths.
It therefore also catches connections that remain broken while a worker or
beat process is temporarily unavailable.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from audit.models import (
    AuditAction,
    AuditActivityType,
    AuditModule,
    AuditStatus,
    IntegrationFailureAlert,
)
from audit.services import audit_service
from common.email_service import send_email


logger = logging.getLogger(__name__)

REMINDER_INTERVAL = timedelta(hours=24)
DELIVERY_RETRY_INTERVAL = timedelta(minutes=15)


def _safe_error(error: str) -> str:
    return " ".join(str(error or "Unknown connection failure.").split())[:1200]


def _friendly_type(integration_type: str) -> str:
    return {
        IntegrationFailureAlert.IntegrationType.EMAIL: "email mailbox",
        IntegrationFailureAlert.IntegrationType.NETSUITE: "NetSuite",
        IntegrationFailureAlert.IntegrationType.AI: "AI",
    }.get(integration_type, "integration")


def _send_alert(*, alert: IntegrationFailureAlert, reminder: bool) -> bool:
    owner = alert.owner
    recipient = (getattr(owner, "email", "") or "").strip()
    if not recipient:
        logger.warning(
            "Integration failure alert has no recipient — type=%s connection=%s company=%s",
            alert.integration_type, alert.connection_id, alert.company_id,
        )
        return False

    prefix = "Reminder: " if reminder else "Action required: "
    label = alert.connection_label or alert.provider or _friendly_type(alert.integration_type)
    subject = f"{prefix}{_friendly_type(alert.integration_type)} connection needs attention"
    reconnect_line = (
        f"\nReconnect it in AGSuite ERP: {alert.reconnect_path}\n"
        if alert.reconnect_path else "\nOpen AGSuite ERP and reconnect the integration.\n"
    )
    message = (
        f"Hello,\n\n"
        f"Your { _friendly_type(alert.integration_type) } connection "
        f"\"{label}\" is unavailable and needs attention.\n\n"
        f"Reason: {alert.last_error or 'The connection could not be used.'}\n"
        f"Provider: {alert.provider or 'Not specified'}\n"
        f"Connection: {label}\n"
        f"{reconnect_line}\n"
        "Automatic processing that depends on this connection will remain paused or retry "
        "until the connection is restored.\n\n"
        "This is an automated AGSuite ERP alert."
    )
    delivered = send_email(
        subject=subject,
        message=message,
        recipient_list=[recipient],
        fail_silently=True,
    ) > 0
    audit_service.log(
        module=AuditModule.SETTINGS,
        action=AuditAction.SEND,
        entity="Integration failure email alert",
        entity_id=str(alert.id),
        company=alert.company,
        user=None,
        activity_type=AuditActivityType.AUTOMATED,
        status=AuditStatus.SUCCESS if delivered else AuditStatus.FAILED,
        detail={
            "summary": "Integration failure reminder email sent." if reminder else "Integration failure email alert sent.",
            "integration_type": alert.integration_type,
            "connection_id": alert.connection_id,
            "recipient": recipient,
            "delivered": delivered,
        },
    )
    return delivered


def report_integration_failure(
    *,
    integration_type: str,
    connection_id: str,
    company,
    owner,
    connection_label: str,
    provider: str,
    error: str,
    reconnect_path: str,
) -> None:
    """Best-effort alert handling that never interrupts the primary workflow."""
    try:
        _report_integration_failure(
            integration_type=integration_type,
            connection_id=connection_id,
            company=company,
            owner=owner,
            connection_label=connection_label,
            provider=provider,
            error=error,
            reconnect_path=reconnect_path,
        )
    except Exception:
        logger.exception(
            "Integration failure alert handling failed — type=%s connection=%s",
            integration_type,
            connection_id,
        )


def _report_integration_failure(
    *,
    integration_type: str,
    connection_id: str,
    company,
    owner,
    connection_label: str,
    provider: str,
    error: str,
    reconnect_path: str,
) -> None:
    """Record one failed connection and deliver an initial/daily reminder.

    A delivery failure is retried after 15 minutes. A successfully delivered
    alert is not repeated until 24 hours pass while the connection is still
    unhealthy.
    """
    if company is None:
        return

    now = timezone.now()
    safe_error = _safe_error(error)
    with transaction.atomic():
        alert, _ = IntegrationFailureAlert.objects.select_for_update().get_or_create(
            company=company,
            integration_type=integration_type,
            connection_id=str(connection_id),
            defaults={
                "owner": owner,
                "connection_label": (connection_label or "")[:255],
                "provider": (provider or "")[:100],
                "reconnect_path": (reconnect_path or "")[:500],
                "last_error": safe_error,
                "failed_at": now,
            },
        )
        if not alert.is_open:
            alert.is_open = True
            alert.failed_at = now
            alert.last_delivery_attempt_at = None
            alert.last_alert_sent_at = None
            alert.resolved_at = None
        alert.owner = owner or alert.owner
        alert.connection_label = (connection_label or alert.connection_label)[:255]
        alert.provider = (provider or alert.provider)[:100]
        alert.reconnect_path = (reconnect_path or alert.reconnect_path)[:500]
        alert.last_error = safe_error

        reminder = bool(alert.last_alert_sent_at)
        due = alert.last_alert_sent_at is None or now - alert.last_alert_sent_at >= REMINDER_INTERVAL
        retry_blocked = bool(
            alert.last_delivery_attempt_at
            and now - alert.last_delivery_attempt_at < DELIVERY_RETRY_INTERVAL
        )
        should_send = due and not retry_blocked
        if should_send:
            alert.last_delivery_attempt_at = now
        alert.save()

    if not should_send:
        return
    delivered = _send_alert(alert=alert, reminder=reminder)
    if delivered:
        IntegrationFailureAlert.objects.filter(pk=alert.pk, is_open=True).update(
            last_alert_sent_at=timezone.now(),
        )


def mark_integration_healthy(*, integration_type: str, connection_id: str, company) -> None:
    """Close alert state after recovery without sending a recovery email."""
    if company is None:
        return
    IntegrationFailureAlert.objects.filter(
        company=company,
        integration_type=integration_type,
        connection_id=str(connection_id),
        is_open=True,
    ).update(is_open=False, resolved_at=timezone.now())


def is_ai_connection_failure(error: Exception) -> bool:
    """Return true only for persistent credential/authorization failures."""
    status_code = getattr(error, "status_code", None)
    if status_code in {401, 403}:
        return True
    message = str(error or "").lower()
    markers = (
        "invalid api key", "api key not valid", "api_key_invalid",
        "unauthorized", "authentication", "permission denied",
        "invalid credential", "credentials are invalid",
    )
    return any(marker in message for marker in markers)


def report_ai_connection_failure(*, company, error: Exception) -> None:
    """Persist an AI credential failure so the checker can alert/retry later."""
    from ocr.models import AIConfiguration

    configuration = AIConfiguration.objects.filter(company=company, is_active=True).first()
    if configuration is None or not is_ai_connection_failure(error):
        return
    configuration.last_error = _safe_error(str(error))
    configuration.save(update_fields=["last_error", "updated_at"])
    report_integration_failure(
        integration_type=IntegrationFailureAlert.IntegrationType.AI,
        connection_id=str(configuration.id),
        company=company,
        owner=configuration.configured_by or getattr(company, "created_by", None),
        connection_label=f"{configuration.provider}:{configuration.model}",
        provider=configuration.provider,
        error=configuration.last_error,
        reconnect_path="/app/settings/ai-integration",
    )


def mark_ai_healthy(*, company) -> None:
    from ocr.models import AIConfiguration

    configuration = AIConfiguration.objects.filter(company=company, is_active=True).first()
    if configuration is None:
        return
    if configuration.last_error:
        configuration.last_error = ""
        configuration.save(update_fields=["last_error", "updated_at"])
    mark_integration_healthy(
        integration_type=IntegrationFailureAlert.IntegrationType.AI,
        connection_id=str(configuration.id),
        company=company,
    )


def check_integration_failure_alerts() -> None:
    """Re-evaluate persisted Email/NetSuite health after every scheduled run."""
    # Local imports prevent model-import cycles while Django initializes apps.
    from mail_integration.models import EmailIntegration
    from netsuite.models import NetSuiteConnection
    from ocr.models import AIConfiguration

    for integration in EmailIntegration.objects.select_related("company", "created_by").all().iterator():
        if integration.status == EmailIntegration.Status.ERROR:
            report_integration_failure(
                integration_type=IntegrationFailureAlert.IntegrationType.EMAIL,
                connection_id=str(integration.id),
                company=integration.company,
                owner=integration.created_by,
                connection_label=integration.display_name or integration.mailbox_email,
                provider=integration.provider,
                error=integration.last_error,
                reconnect_path="/app/integrations/email",
            )
        elif integration.status == EmailIntegration.Status.CONNECTED:
            mark_integration_healthy(
                integration_type=IntegrationFailureAlert.IntegrationType.EMAIL,
                connection_id=str(integration.id),
                company=integration.company,
            )

    for connection in NetSuiteConnection.objects.select_related("company", "user").all().iterator():
        if connection.status == "error":
            report_integration_failure(
                integration_type=IntegrationFailureAlert.IntegrationType.NETSUITE,
                connection_id=str(connection.id),
                company=connection.company,
                owner=connection.user,
                connection_label=connection.client_name or connection.netsuite_account_id,
                provider="NetSuite",
                error=connection.last_error or "NetSuite connection is unavailable.",
                reconnect_path="/app/integrations/netsuite",
            )
        elif connection.status == "connected":
            mark_integration_healthy(
                integration_type=IntegrationFailureAlert.IntegrationType.NETSUITE,
                connection_id=str(connection.id),
                company=connection.company,
            )

    for configuration in AIConfiguration.objects.select_related("company", "configured_by", "company__created_by").filter(is_active=True).iterator():
        if configuration.last_error:
            report_integration_failure(
                integration_type=IntegrationFailureAlert.IntegrationType.AI,
                connection_id=str(configuration.id),
                company=configuration.company,
                owner=configuration.configured_by or configuration.company.created_by,
                connection_label=f"{configuration.provider}:{configuration.model}",
                provider=configuration.provider,
                error=configuration.last_error,
                reconnect_path="/app/settings/ai-integration",
            )
