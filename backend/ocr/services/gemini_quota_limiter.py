"""Distributed Gemini request/concurrency limiter using Redis."""

from __future__ import annotations

import time
import uuid

import redis
from django.conf import settings


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

    def __init__(self):
        self.redis = redis.Redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True,
        )

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
        token = request_id or uuid.uuid4().hex

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

    def release(self, token: str) -> None:
        try:
            self.redis.zrem(self.active_key, token)
        except redis.RedisError:
            # The lease will expire automatically; never turn a successful
            # OCR result into a failed result only because cleanup Redis
            # communication failed.
            pass
