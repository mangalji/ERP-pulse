"""Distributed Gemini request/concurrency limiter using Redis."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta

import redis
from django.conf import settings

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from common.infra import get_redis_client, report_redis_failure, warn_throttled

# Arbitrary constant: transaction-scoped advisory lock that serialises the
# check-and-insert of the PostgreSQL fallback limiter. Transaction-scoped
# locks are safe behind PgBouncer in transaction-pooling mode.
_DB_GATE_LOCK_ID = 727_001

logger = logging.getLogger(__name__)

class DatabaseGeminiLimiter:
    """
    PostgreSQL fallback with the same semantics as the Redis limiter:
    a concurrency cap (with expiring leases) plus a rolling 60-second RPM cap.
    """

    def __init__(self, max_concurrency: int, target_rpm: int, lease_seconds: int):
        self.max_concurrency = max_concurrency
        self.target_rpm = target_rpm
        self.lease_seconds = lease_seconds

    def _try_acquire(self, token: str) -> float:
        """Return 0 when acquired, otherwise the seconds to wait."""
        from ocr.models import OCRGeminiLease

        now = timezone.now()

        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(%s)", [_DB_GATE_LOCK_ID]
                    )

            # Housekeeping: rows outside the RPM window that no longer hold a slot.
            OCRGeminiLease.objects.filter(
                created_at__lt=now - timedelta(seconds=60)
            ).filter(
                Q(released_at__isnull=False) | Q(lease_expires_at__lt=now)
            ).delete()

            active = OCRGeminiLease.objects.filter(
                released_at__isnull=True,
                lease_expires_at__gt=now,
            )
            if active.count() >= self.max_concurrency:
                first = (
                    active.order_by("lease_expires_at")
                    .values_list("lease_expires_at", flat=True)
                    .first()
                )
                return max(0.0, (first - now).total_seconds()) if first else 1.0

            recent = OCRGeminiLease.objects.filter(
                created_at__gt=now - timedelta(seconds=60)
            )
            if recent.count() >= self.target_rpm:
                first = (
                    recent.order_by("created_at")
                    .values_list("created_at", flat=True)
                    .first()
                )
                if first:
                    return max(0.0, (first + timedelta(seconds=60) - now).total_seconds())
                return 1.0

            OCRGeminiLease.objects.update_or_create(
                token=token,
                defaults={
                    "created_at": now,
                    "lease_expires_at": now + timedelta(seconds=self.lease_seconds),
                    "released_at": None,
                },
            )
            return 0.0

    def acquire(self, token: str) -> str:
        while True:
            wait_seconds = self._try_acquire(token)
            if wait_seconds <= 0:
                return token
            # Poll faster than the Redis variant so a freed slot is noticed quickly.
            time.sleep(min(max(wait_seconds, 0.25), 2.0))

    def release(self, token: str) -> None:
        from ocr.models import OCRGeminiLease

        try:
            OCRGeminiLease.objects.filter(token=token).update(
                released_at=timezone.now()
            )
        except Exception as exc:  # noqa: BLE001 - lease expires on its own
            logger.warning(
                "Gemini DB limiter release skipped (lease will expire) — token=%s reason=%s",
                token,
                exc,
            )

class GeminiQuotaLimiter:
    """
    Global limiter shared by all Celery workers/processes.

    It protects:
    - maximum active Gemini calls
    - maximum Gemini request starts per rolling 60-second window

    The active-call lease prevents a dead worker from permanently consuming
    a concurrency slot.
    """

    _ACQUIRE_SCRIPT = """
    local now = tonumber(ARGV[1])
    local request_id = ARGV[2]
    local max_concurrency = tonumber(ARGV[3])
    local target_rpm = tonumber(ARGV[4])
    local lease_seconds = tonumber(ARGV[5])

    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
    redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now - 60)

    local active_count = redis.call('ZCARD', KEYS[1])
    if active_count >= max_concurrency then
        local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
        if #first >= 2 then
            return math.max(0, tonumber(first[2]) - now)
        end
        return 1
    end

    local recent_count = redis.call('ZCARD', KEYS[2])
    if recent_count >= target_rpm then
        local first = redis.call('ZRANGE', KEYS[2], 0, 0, 'WITHSCORES')
        if #first >= 2 then
            return math.max(0, (tonumber(first[2]) + 60) - now)
        end
        return 1
    end

    redis.call('ZADD', KEYS[1], now + lease_seconds, request_id)
    redis.call('ZADD', KEYS[2], now, request_id)
    return 0
    """

    @property
    def redis(self):
        """Optional Redis client; raises ``RedisUnavailable`` if not reachable."""
        return get_redis_client()

    def __init__(self):
        self._db_tokens: set[str] = set()
        self.active_key = "erp-pulse:ocr:gemini:active"
        self.rpm_key = "erp-pulse:ocr:gemini:requests"

        self.max_concurrency = max(
            1,
            int(getattr(settings, "OCR_GEMINI_MAX_CONCURRENCY", 2)),
        )
        self.target_rpm = max(
            1,
            int(getattr(settings, "OCR_GEMINI_TARGET_RPM", 8)),
        )
        self.lease_seconds = max(
            30,
            int(getattr(settings, "OCR_GEMINI_CONCURRENCY_LEASE_SECONDS", 180)),
        )

    def acquire(self, request_id: str | None = None) -> str:
        """
        Acquire a global Gemini slot. Uses Redis when available; otherwise
        falls back to the PostgreSQL limiter with identical semantics.
        """
        token = request_id or uuid.uuid4().hex

        try:
            return self._acquire_redis(token)
        except redis.RedisError as exc:
            report_redis_failure(exc)
            warn_throttled(
                "gemini-limiter-db-fallback",
                "Gemini rate limiter is using the PostgreSQL fallback "
                "(Redis unavailable): %s",
                exc,
            )
            self._db_tokens.add(token)
            return self._db_limiter().acquire(token)
        
    def _acquire_redis(self, token: str) -> str:
        while True:
            now = time.time()

            wait_seconds = float(
                self.redis.eval(
                    self._ACQUIRE_SCRIPT,
                    2,
                    self.active_key,
                    self.rpm_key,
                    now,
                    token,
                    self.max_concurrency,
                    self.target_rpm,
                    self.lease_seconds,
                )
            )

            if wait_seconds <= 0:
                return token

            # Keep workers from hammering Redis while waiting. This sleep
            # does not call Gemini.
            time.sleep(min(max(wait_seconds, 0.25), 5.0))

    def _db_limiter(self) -> DatabaseGeminiLimiter:
        return DatabaseGeminiLimiter(
            self.max_concurrency,
            self.target_rpm,
            self.lease_seconds,
        )


    def release(self, token: str) -> None:
        if token in self._db_tokens:
            self._db_tokens.discard(token)
            self._db_limiter().release(token)
            return
        
        try:
            self.redis.zrem(self.active_key, token)
        except redis.RedisError:
            # The lease will expire automatically; never turn a successful
            # OCR result into a failed result only because cleanup Redis
            # communication failed.
            pass
