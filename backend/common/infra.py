"""
Optional-infrastructure helpers.

Redis is an *optional* accelerator in this project, never a requirement.
Everything here is written so that a missing, misconfigured or temporarily
unreachable Redis produces one short, throttled warning and a clean
"unavailable" signal instead of a crash or a wall of tracebacks.

Design notes
------------
* ``get_redis_client()`` either returns a working client or raises
  ``RedisUnavailable``. ``RedisUnavailable`` subclasses ``redis.ConnectionError``
  (and therefore ``redis.RedisError``), so every existing
  ``except redis.RedisError`` handler keeps working unchanged.
* Availability is probed with a cheap ``PING`` (short timeouts) and cached for
  ``REDIS_RETRY_INTERVAL`` seconds. While Redis is considered down, callers fail
  immediately instead of waiting on a connect timeout for every request.
* Warnings are throttled per key so a Redis outage logs once every few minutes,
  not once per request.
"""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlsplit

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


class RedisUnavailable(redis.ConnectionError):
    """Redis is not configured or is currently unreachable."""


_lock = threading.Lock()
_client = None
_client_url = ""
_checked_at = 0.0
_available = False
_last_reason = ""
_warned_at: dict[str, float] = {}


def warn_throttled(key: str, message: str, *args, interval: float = 300.0) -> None:
    """Log ``message`` as a warning at most once per ``interval`` seconds per key."""
    now = time.monotonic()
    with _lock:
        last = _warned_at.get(key)
        if last is not None and (now - last) < interval:
            return
        _warned_at[key] = now
    logger.warning(message, *args)


def redis_url() -> str:
    """Configured Redis URL, or ``""`` when Redis is disabled/not configured."""
    if not getattr(settings, "REDIS_ENABLED", True):
        return ""
    return (getattr(settings, "REDIS_URL", "") or "").strip()


def _describe(url: str) -> str:
    """host:port/db of a Redis URL, with credentials stripped (safe to log)."""
    try:
        parts = urlsplit(url)
        if not parts.hostname:
            return "invalid-redis-url"
        host = parts.hostname
        port = f":{parts.port}" if parts.port else ""
        db = parts.path or ""
        return f"{host}{port}{db}"
    except ValueError:
        return "invalid-redis-url"


def get_redis_client():
    """
    Return a connected Redis client, or raise ``RedisUnavailable``.

    The result of the connectivity probe is cached for ``REDIS_RETRY_INTERVAL``
    seconds in both directions (up and down).
    """
    global _client, _client_url, _checked_at, _available, _last_reason

    url = redis_url()
    if not url:
        raise RedisUnavailable(
            "Redis is not configured (REDIS_URL unset or REDIS_ENABLED=false)"
        )

    interval = max(1.0, float(getattr(settings, "REDIS_RETRY_INTERVAL", 30)))

    with _lock:
        now = time.monotonic()

        if _client_url == url and _checked_at and (now - _checked_at) < interval:
            if _available and _client is not None:
                return _client
            raise RedisUnavailable(_last_reason)

        was_available = _available and _client_url == url

        try:
            client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=float(
                    getattr(settings, "REDIS_CONNECT_TIMEOUT", 1.0)
                ),
                socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT", 2.0)),
            )
            client.ping()
        except Exception as exc:  # noqa: BLE001 - any probe failure means "unavailable"
            _client = None
            _client_url = url
            _checked_at = now
            _available = False
            _last_reason = (
                f"Redis unavailable at {_describe(url)} ({type(exc).__name__}); "
                "continuing without Redis"
            )
            # Release the lock-protected state before logging.
            reason = _last_reason
        else:
            _client = client
            _client_url = url
            _checked_at = now
            _available = True
            _last_reason = ""
            reason = ""

    if reason:
        warn_throttled("redis-unavailable", reason)
        raise RedisUnavailable(reason)

    if not was_available and _warned_at.get("redis-unavailable") is not None:
        logger.info("Redis connection restored at %s", _describe(url))

    return _client

def report_redis_failure(exc: BaseException) -> None:
    """
    Call this when a Redis command fails at runtime. Opens the circuit breaker
    immediately (instead of waiting for the next periodic probe) so following
    calls fail fast and use the fallback backends.
    """
    global _checked_at, _available, _last_reason

    if isinstance(exc, RedisUnavailable):
        return  # already known to be down

    url = redis_url()
    if not url:
        return

    with _lock:
        _checked_at = time.monotonic()
        _available = False
        _last_reason = (
            f"Redis unavailable at {_describe(url)} ({type(exc).__name__}); "
            "continuing without Redis"
        )
        reason = _last_reason

    warn_throttled("redis-unavailable", reason)

def redis_available() -> bool:
    """True when Redis is configured and answered the latest probe."""
    try:
        get_redis_client()
        return True
    except redis.RedisError:
        return False


def reset_redis_state() -> None:
    """Forget cached probe state (used by tests)."""
    global _client, _client_url, _checked_at, _available, _last_reason
    with _lock:
        _client = None
        _client_url = ""
        _checked_at = 0.0
        _available = False
        _last_reason = ""
        _warned_at.clear()

