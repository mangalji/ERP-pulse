"""Best-effort daily housekeeping for deployments without a scheduler.

The login page already asks the API for a CSRF token.  That inexpensive
public request is used to *start* the existing housekeeping work once per
day when Celery beat/cron is unavailable.  The work is deliberately run in a
daemon thread, so issuing a CSRF token (and therefore opening the login page)
never waits for company cleanup.

This is a fallback, not a scheduler replacement: if nobody visits the app,
there is no request from which to start the work.
"""

from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections
from django.utils import timezone

from common.scheduled import run_scheduled_tasks


logger = logging.getLogger(__name__)

_SUCCESS_KEY = "common:lazy-housekeeping:last-successful-date"
_LEASE_KEY = "common:lazy-housekeeping:lease"
_LEASE_SECONDS = 10 * 60
_SUCCESS_TTL_SECONDS = 2 * 24 * 60 * 60


def _run_housekeeping(date_key: str, success_ttl_seconds: int) -> None:
    """Run work outside the request and record only a fully successful run."""
    succeeded = False

    try:
        # A background thread must not inherit a stale request DB connection.
        close_old_connections()
        outcome = run_scheduled_tasks()
        succeeded = bool(outcome) and all(state == "ok" for state in outcome.values())

        if succeeded:
            cache.set(_SUCCESS_KEY, date_key, timeout=success_ttl_seconds)
            logger.info("Lazy daily housekeeping completed for %s.", date_key)
        else:
            logger.warning(
                "Lazy daily housekeeping did not complete for %s: %s",
                date_key,
                outcome,
            )
    except Exception:  # noqa: BLE001 - a fallback must never take down login
        logger.exception("Lazy daily housekeeping crashed for %s.", date_key)
    finally:
        close_old_connections()
        # A failed run keeps its lease until it expires.  That prevents every
        # login request from retrying immediately, while allowing a retry soon.
        if succeeded:
            try:
                cache.delete(_LEASE_KEY)
            except Exception:  # noqa: BLE001
                logger.exception("Could not clear the lazy-housekeeping lease.")


def trigger_lazy_daily_housekeeping() -> bool:
    """Start today's fallback run when no other request has already claimed it.

    Returns whether this request started a worker.  Cache failures are logged
    and ignored so public login/CSRF availability is never dependent on this
    optional maintenance mechanism.
    """
    if not getattr(settings, "LAZY_HOUSEKEEPING_ENABLED", True):
        return False

    date_key = timezone.localdate().isoformat()
    lease_seconds = int(getattr(settings, "LAZY_HOUSEKEEPING_LEASE_SECONDS", _LEASE_SECONDS))
    success_ttl_seconds = int(
        getattr(settings, "LAZY_HOUSEKEEPING_SUCCESS_TTL_SECONDS", _SUCCESS_TTL_SECONDS)
    )

    try:
        if cache.get(_SUCCESS_KEY) == date_key:
            return False
        if not cache.add(_LEASE_KEY, date_key, timeout=lease_seconds):
            return False
    except Exception:  # noqa: BLE001
        logger.exception("Could not acquire the lazy-housekeeping lease.")
        return False

    try:
        worker = threading.Thread(
            target=_run_housekeeping,
            args=(date_key, success_ttl_seconds),
            name="lazy-daily-housekeeping",
            daemon=True,
        )
        worker.start()
    except Exception:  # noqa: BLE001
        logger.exception("Could not start lazy daily housekeeping.")
        try:
            cache.delete(_LEASE_KEY)
        except Exception:  # noqa: BLE001
            logger.exception("Could not release the lazy-housekeeping lease.")
        return False

    return True
