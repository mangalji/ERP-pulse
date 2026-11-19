"""Company/provider/model-scoped AI request limiter.

The limiter protects the configured AI account for one company without
letting another company's workload consume its concurrency or RPM budget.
Redis is the fast path; PostgreSQL is the durable fallback.
"""

from __future__ import annotations

import hashlib
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

_DB_GATE_LOCK_ID = 727_001
logger = logging.getLogger(__name__)


def build_ai_scope_key(*, company_id, provider: str, model: str) -> str:
    """Return a stable, non-secret scope key for one company AI config."""
    raw = f"{company_id}:{(provider or '').strip().lower()}:{(model or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class DatabaseAILimiter:
    """PostgreSQL fallback with the same scoped semantics as Redis."""

    def __init__(self, *, scope_key: str, max_concurrency: int, target_rpm: int, lease_seconds: int):
        self.scope_key = scope_key
        self.max_concurrency = max_concurrency
        self.target_rpm = target_rpm
        self.lease_seconds = lease_seconds

    def _try_acquire(self, token: str) -> float:
        from ocr.models import OCRAILimitLease

        now = timezone.now()
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_DB_GATE_LOCK_ID])

            OCRAILimitLease.objects.filter(
                scope_key=self.scope_key,
                created_at__lt=now - timedelta(seconds=60),
            ).filter(
                Q(released_at__isnull=False) | Q(lease_expires_at__lt=now)
            ).delete()

            active = OCRAILimitLease.objects.filter(
                scope_key=self.scope_key,
                released_at__isnull=True,
                lease_expires_at__gt=now,
            )
            if active.count() >= self.max_concurrency:
                first = active.order_by("lease_expires_at").values_list(
                    "lease_expires_at", flat=True
                ).first()
                return max(0.0, (first - now).total_seconds()) if first else 1.0

            recent = OCRAILimitLease.objects.filter(
                scope_key=self.scope_key,
                created_at__gt=now - timedelta(seconds=60),
            )
            if recent.count() >= self.target_rpm:
                first = recent.order_by("created_at").values_list(
                    "created_at", flat=True
                ).first()
                if first:
                    return max(0.0, (first + timedelta(seconds=60) - now).total_seconds())
                return 1.0

            OCRAILimitLease.objects.update_or_create(
                token=token,
                defaults={
                    "scope_key": self.scope_key,
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
            time.sleep(min(max(wait_seconds, 0.25), 2.0))

    def release(self, token: str) -> None:
        from ocr.models import OCRAILimitLease

        try:
            OCRAILimitLease.objects.filter(
                token=token,
                scope_key=self.scope_key,
            ).update(released_at=timezone.now())
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI DB limiter release skipped — token=%s reason=%s", token, exc)


class AIQuotaLimiter:
    """Per-company, per-provider, per-model concurrency/RPM limiter."""

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

    def __init__(self, *, company_id, provider: str, model: str):
        self.company_id = str(company_id)
        self.provider = (provider or "").strip().lower()
        self.model = (model or "").strip()
        self.scope_key = build_ai_scope_key(
            company_id=self.company_id,
            provider=self.provider,
            model=self.model,
        )
        self.active_key = f"erp-pulse:ocr:ai:active:{self.scope_key}"
        self.rpm_key = f"erp-pulse:ocr:ai:requests:{self.scope_key}"
        self._db_tokens: set[str] = set()
        self.max_concurrency = max(1, int(getattr(settings, "OCR_AI_MAX_CONCURRENCY", 2)))
        self.target_rpm = max(1, int(getattr(settings, "OCR_AI_TARGET_RPM", 8)))
        self.lease_seconds = max(
            30,
            int(getattr(settings, "OCR_AI_CONCURRENCY_LEASE_SECONDS", 180)),
        )

    @property
    def redis(self):
        return get_redis_client()

    def acquire(self, request_id: str | None = None) -> str:
        token = request_id or uuid.uuid4().hex
        try:
            return self._acquire_redis(token)
        except redis.RedisError as exc:
            report_redis_failure(exc)
            warn_throttled(
                "ai-limiter-db-fallback",
                "AI quota limiter is using PostgreSQL fallback: %s",
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
            time.sleep(min(max(wait_seconds, 0.25), 5.0))

    def _db_limiter(self) -> DatabaseAILimiter:
        return DatabaseAILimiter(
            scope_key=self.scope_key,
            max_concurrency=self.max_concurrency,
            target_rpm=self.target_rpm,
            lease_seconds=self.lease_seconds,
        )

    def release(self, token: str) -> None:
        if token in self._db_tokens:
            self._db_tokens.discard(token)
            self._db_limiter().release(token)
            return
        try:
            self.redis.zrem(self.active_key, token)
        except redis.RedisError:
            pass
