"""Safe, structured company audit logging."""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import Mapping

from django.db.models import Model

from audit.context import get_request_context
from audit.models import AuditAction, AuditActivityType, AuditLog, AuditModule, AuditStatus


logger = logging.getLogger(__name__)

SENSITIVE_DETAIL_KEYS = {
    "access_token", "refresh_token", "token", "client_secret", "secret",
    "password", "otp", "raw_body", "normalized_body", "authorization",
}


def redact_detail(value, *, key: str = ""):
    """Keep audit evidence useful without persisting secrets or email bodies."""
    if key.casefold() in SENSITIVE_DETAIL_KEYS:
        return "[redacted]"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_detail(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_detail(item, key=key) for item in value]
    if isinstance(value, str):
        return value[:4000]
    return value


class AuditService:
    """Write immutable audit entries without blocking source workflows."""

    def log(
        self,
        *,
        module: AuditModule,
        action: AuditAction,
        entity: str,
        entity_id: str | None = None,
        company=None,
        user=None,
        old_value: dict | None = None,
        new_value: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        activity_type: str | None = None,
        status: str = AuditStatus.SUCCESS,
        detail: dict | None = None,
    ) -> AuditLog | None:
        """Create a single audit entry; a logging failure never breaks work."""
        try:
            request_context = get_request_context()
            enriched_detail = dict(detail or {})
            if request_context:
                # Retain forensic request evidence without request data,
                # credentials, cookies, or authorization headers.
                enriched_detail.setdefault("request", request_context)
                ip_address = ip_address or request_context.get("client_ip")
                user_agent = user_agent or request_context.get("user_agent")

            enriched_detail.setdefault("execution", {
                "origin": "web_request" if request_context else "background_or_service",
                "hostname": socket.gethostname()[:255],
                "process_id": os.getpid(),
            })
            self._attach_netsuite_context(
                detail=enriched_detail,
                company=company,
                module=module,
            )
            resolved_activity_type = activity_type or (
                AuditActivityType.MANUAL if user is not None else AuditActivityType.AUTOMATED
            )
            return AuditLog.objects.create(
                company=company,
                user=user,
                module=module,
                action=action,
                entity=entity[:100],
                entity_id=str(entity_id)[:100] if entity_id else None,
                old_value=redact_detail(old_value or {}),
                new_value=redact_detail(new_value or {}),
                ip_address=ip_address,
                user_agent=(user_agent or "")[:512] or None,
                activity_type=resolved_activity_type,
                status=status,
                detail=redact_detail(enriched_detail),
            )
        except Exception:
            logger.exception(
                "Audit log write failed — module=%s action=%s entity=%s",
                module, action, entity,
            )
            return None

    @staticmethod
    def _attach_netsuite_context(*, detail: dict, company, module: str) -> None:
        """Attach the active account where a log can affect bill processing.

        The connection record is looked up lazily to avoid an import cycle and
        is only added to modules that use, validate, or feed NetSuite data.
        """
        if (
            not isinstance(company, Model)
            or not company.pk
            or module not in {
            AuditModule.NETSUITE,
            AuditModule.OCR,
            AuditModule.AI,
            AuditModule.EMAIL,
            }
        ):
            return
        if detail.get("netsuite"):
            return
        try:
            from netsuite.models import NetSuiteConnection

            connection = (
                NetSuiteConnection.objects.filter(company=company, is_active=True)
                .order_by("-last_used_at", "-connected_at")
                .first()
            )
            if connection is None:
                detail["netsuite"] = {"active_connection": False}
                return
            detail["netsuite"] = {
                "active_connection": True,
                "connection_id": str(connection.id),
                "account_id": connection.netsuite_account_id,
                "environment": connection.environment,
                "connection_status": connection.status,
                "client_name": connection.client_name or None,
            }
        except Exception:
            # Audit evidence must not alter an otherwise successful action.
            logger.exception("Unable to enrich audit event with NetSuite context.")


audit_service = AuditService()
