"""
Cache-backed storage for in-flight registration state (email, hashed
password, OTP hash/expiry, attempt count, last-sent time) — deliberately
NOT a database model.

Registration state that isn't yet a real User does not get a permanent
(or even soft-deletable) database row. Django's cache framework gives the
same "resumable across separate HTTP requests" property a model would,
plus automatic expiry for free, without adding a table to the schema for
half-finished signups. If the browser is closed before registration
finishes, the entry simply expires and the user starts over — an accepted
product decision, not an oversight.

This module is persistence-only, mirroring the Repository pattern used
elsewhere in this app: no business rules (cooldown enforcement, attempt
limits, expiry semantics) live here — see AuthenticationService.
"""

from django.core.cache import cache

CACHE_KEY_PREFIX = 'registration_pending'


def _cache_key(email: str) -> str:
    return f'{CACHE_KEY_PREFIX}:{email.lower()}'


def save(*, email: str, data: dict, timeout_seconds: int) -> None:
    cache.set(_cache_key(email), data, timeout=timeout_seconds)


def get(email: str) -> dict | None:
    return cache.get(_cache_key(email))


def delete(email: str) -> None:
    cache.delete(_cache_key(email))