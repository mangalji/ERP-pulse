"""
Generic utility functions for AGSuite ERP.

Only utilities that are NOT already in ``common/utils/`` belong here.
Existing utilities (``common/utils/crypto.py``, ``common/utils/datetime.py``,
``common/utils/hash.py``, ``common/utils/response.py``,
``common/utils/pagination.py``, ``common/utils/signed_token.py``,
``common/utils/otp.py``) remain in place — this file does not duplicate
or replace them.

New code should import from ``core/utils.py`` for generic helpers and
from ``common/utils/`` for the existing utilities listed above.
"""

import logging
import uuid

from django.http import HttpRequest

logger = logging.getLogger(__name__)


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID4."""
    return uuid.uuid4()


def get_client_ip(request: HttpRequest) -> str | None:
    """
    Extract the client IP address from a request.

    Prefers ``X-Forwarded-For``'s first hop (the original client) over
    ``REMOTE_ADDR``, since PaaS deployments (Render, etc.) sit behind a
    proxy that would otherwise make every request appear to come from
    the same internal proxy IP.

    A standalone version of this function already exists inline in
    ``accounts/views.py``. This module-level copy is the canonical
    location for new code; the existing inline copy is intentionally
    left untouched so no existing imports break.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_user_agent(request: HttpRequest, max_length: int = 512) -> str | None:
    """
    Extract the User-Agent header from a request, truncated to
    ``max_length`` to fit database columns safely.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if not user_agent:
        return None
    return user_agent[:max_length]


def safe_call(label: str, func, *args, **kwargs):
    """
    Run a function in isolation. On failure, log and return ``None``
    instead of letting the exception propagate.

    This is the generic version of the ``_safe_call`` pattern already
    used in ``ai/context_builder.py``. It is extracted here so any
    module that needs graceful degradation can reuse it without
    redefining the same try/except block.
    """
    try:
        return func(*args, **kwargs)
    except Exception:
        logger.exception('Safe call "%s" failed; omitting result.', label)
        return None