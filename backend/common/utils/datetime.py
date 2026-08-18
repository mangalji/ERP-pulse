from datetime import datetime, timedelta

from django.utils import timezone


def calculate_expiry(minutes: int) -> datetime:
    """Return a timezone-aware timestamp `minutes` from now."""
    return timezone.now() + timedelta(minutes=minutes)


def is_expired(expires_at: datetime) -> bool:
    """Return True if the given timestamp is at or before the current time."""
    return timezone.now() >= expires_at
