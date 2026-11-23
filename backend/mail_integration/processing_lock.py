"""Distributed company-level lock for email AI extraction and quota counting."""

from __future__ import annotations

import logging
import threading
import time
import uuid

import redis
from django.conf import settings
from django.core.cache import cache

from common.infra import get_redis_client, report_redis_failure

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 15 * 60
LOCK_HEARTBEAT_SECONDS = 30

_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""

_RENEW_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
end
return 0
"""


class CompanyEmailProcessingLock:
    """A renewable Redis lock, with shared Django cache as a fallback."""

    def __init__(self, company_id: str, *, wait_seconds: int = 60):
        self.key = f"erp-pulse:email:company-extraction:{company_id}"
        self.token = uuid.uuid4().hex
        self.wait_seconds = max(0, int(wait_seconds))
        self.backend = ""
        self.client = None
        self.stop_event = threading.Event()
        self.heartbeat_thread: threading.Thread | None = None
        self.lost = False

    def acquire(self) -> bool:
        try:
            self.client = get_redis_client()
            self.backend = "redis"
        except redis.RedisError:
            cache_config = getattr(settings, "CACHES", {}).get("default", {})
            cache_backend = cache_config.get("BACKEND", "")
            if cache_backend.endswith("LocMemCache"):
                logger.error(
                    "Company email extraction lock unavailable — no shared lock backend configured"
                )
                return False
            self.backend = "cache"

        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                acquired = (
                    self.client.set(
                        self.key,
                        self.token,
                        nx=True,
                        ex=LOCK_TTL_SECONDS,
                    )
                    if self.backend == "redis"
                    else cache.add(self.key, self.token, timeout=LOCK_TTL_SECONDS)
                )
            except redis.RedisError as exc:
                report_redis_failure(exc)
                return False
            except Exception:
                logger.exception("Company email extraction cache lock failed")
                return False

            if acquired:
                self._start_heartbeat()
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))

    def _start_heartbeat(self) -> None:
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat,
            name="company-email-extraction-lock-heartbeat",
            daemon=True,
        )
        self.heartbeat_thread.start()

    def _heartbeat(self) -> None:
        while not self.stop_event.wait(LOCK_HEARTBEAT_SECONDS):
            try:
                renewed = (
                    bool(self.client.eval(
                        _RENEW_LOCK_SCRIPT,
                        1,
                        self.key,
                        self.token,
                        LOCK_TTL_SECONDS,
                    ))
                    if self.backend == "redis"
                    else cache.get(self.key) == self.token
                    and bool(cache.touch(self.key, LOCK_TTL_SECONDS))
                )
            except Exception:
                renewed = False
            if not renewed:
                self.lost = True
                logger.error("Company email extraction lock ownership was lost")
                return

    def release(self) -> None:
        self.stop_event.set()
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=2)
        if not self.backend:
            return
        try:
            if self.backend == "redis":
                self.client.eval(_RELEASE_LOCK_SCRIPT, 1, self.key, self.token)
            elif cache.get(self.key) == self.token:
                cache.delete(self.key)
        except Exception:
            logger.warning(
                "Company email extraction lock release failed; it will expire by TTL",
                exc_info=True,
            )
