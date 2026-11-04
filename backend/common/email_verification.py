"""Server-side email deliverability verification with provider fallback.

Provider credentials deliberately live only in Django settings.  A provider
result is advisory for catch-all/unknown mailboxes, but a confirmed invalid
mailbox prevents an invitation from being created.
"""
from __future__ import annotations

import hashlib
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_SECONDS = 24 * 60 * 60


def _cache_key(email: str) -> str:
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
    return f"email-deliverability:{digest}"


def _result(*, email: str, status: str, provider: str, detail: str = "") -> dict:
    return {
        "email": email,
        "status": status,
        "provider": provider,
        "detail": detail,
        "is_deliverable": status == "deliverable",
        "should_block": status == "undeliverable",
    }


def _verify_abstract(email: str) -> dict | None:
    api_key = getattr(settings, "ABSTRACT_EMAIL_VALIDATION_API_KEY", "")
    if not api_key:
        return None
    response = requests.get(
        "https://emailreputation.abstractapi.com/v1/",
        params={"api_key": api_key, "email": email},
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()
    deliverability = payload.get("email_deliverability") or {}
    raw_status = str(deliverability.get("status") or "unknown").lower()
    detail = str(deliverability.get("status_detail") or raw_status)
    if raw_status == "deliverable":
        return _result(email=email, status="deliverable", provider="abstract", detail=detail)
    if raw_status in {"undeliverable", "invalid"}:
        return _result(email=email, status="undeliverable", provider="abstract", detail=detail)
    return _result(email=email, status="unknown", provider="abstract", detail=detail)


def _verify_hunter(email: str) -> dict | None:
    api_key = getattr(settings, "HUNTER_API_KEY", "")
    if not api_key:
        return None
    response = requests.get(
        "https://api.hunter.io/v2/email-verifier",
        params={"email": email, "api_key": api_key},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json().get("data") or {}
    raw_status = str(data.get("status") or "unknown").lower()
    if raw_status == "valid":
        return _result(email=email, status="deliverable", provider="hunter", detail=raw_status)
    if raw_status == "invalid":
        return _result(email=email, status="undeliverable", provider="hunter", detail=raw_status)
    return _result(email=email, status="unknown", provider="hunter", detail=raw_status)


def verify_email_deliverability(email: str) -> dict:
    """Return a normalized result without exposing provider payloads or keys."""
    normalized_email = (email or "").strip().casefold()
    if not normalized_email:
        return _result(email="", status="undeliverable", provider="local", detail="missing_email")

    key = _cache_key(normalized_email)
    cached = cache.get(key)
    if cached:
        return cached

    for provider, verifier in (("abstract", _verify_abstract), ("hunter", _verify_hunter)):
        try:
            result = verifier(normalized_email)
        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.warning("Email verification provider %s failed: %s", provider, exc.__class__.__name__)
            continue
        if result is not None:
            cache.set(key, result, CACHE_SECONDS)
            return result

    # Do not block a legitimate invite just because a third-party service is
    # down or has exhausted its free allowance. The invitation email/OTP is
    # still the final ownership check.
    return _result(email=normalized_email, status="unknown", provider="unavailable", detail="verification_unavailable")


def ensure_email_deliverable(email: str) -> dict:
    result = verify_email_deliverability(email)
    if result["should_block"]:
        raise ValueError("Please enter a valid, active email address.")
    return result
