"""Per-request audit context.

The context is deliberately small and privacy-aware: it carries useful
forensic metadata for an audit event without ever retaining request bodies,
cookies, credentials, or authorization headers.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from django.conf import settings


_audit_request_context: ContextVar[dict | None] = ContextVar(
    "audit_request_context",
    default=None,
)


def _header(request, name: str) -> str:
    return (request.META.get(name) or "").strip()


def _trusted_proxy_addresses() -> set[str]:
    """Return explicitly trusted proxy addresses only.

    ``X-Forwarded-For`` is client-controlled unless the immediate peer is a
    known reverse proxy, so it must never become the canonical client IP by
    default.
    """
    return {
        str(address).strip()
        for address in getattr(settings, "TRUSTED_PROXY_IPS", ())
        if str(address).strip()
    }


def build_request_context(request) -> dict:
    remote_addr = _header(request, "REMOTE_ADDR") or None
    forwarded_for = _header(request, "HTTP_X_FORWARDED_FOR")
    forwarded_chain = [
        address.strip() for address in forwarded_for.split(",") if address.strip()
    ]
    trusted_proxy = bool(remote_addr and remote_addr in _trusted_proxy_addresses())
    client_ip = forwarded_chain[0] if trusted_proxy and forwarded_chain else remote_addr

    supplied_request_id = _header(request, "HTTP_X_REQUEST_ID")
    request_id = supplied_request_id[:128] if supplied_request_id else str(uuid.uuid4())
    return {
        "request_id": request_id,
        "method": request.method,
        "path": request.path[:500],
        "client_ip": client_ip,
        "remote_addr": remote_addr,
        "forwarded_for": forwarded_chain,
        "forwarded_for_trusted": trusted_proxy,
        "user_agent": _header(request, "HTTP_USER_AGENT")[:512] or None,
        "content_type": _header(request, "CONTENT_TYPE")[:200] or None,
        "query_parameter_names": sorted(request.GET.keys()),
    }


def set_request_context(request):
    return _audit_request_context.set(build_request_context(request))


def reset_request_context(token) -> None:
    _audit_request_context.reset(token)


def get_request_context() -> dict | None:
    context = _audit_request_context.get()
    return dict(context) if context else None
