# this is for date and time related utilities

# from datetime import timedelta
# from django.utils import timezone
# from common.constants import OTP_EXPIRY_MINUTES

# def get_otp_expiry(minutes:int = OTP_EXPIRY_MINUTES,):
#     """
#     Return OTP expiry timestamp.

#     Args:
#         minutes: Expiry duration.

#     Returns:
#         Timezone-aware datetime.
#     """
#     return timezone.now() + timedelta(minutes = minutes)

from datetime import datetime, timedelta

from django.utils import timezone


def calculate_expiry(minutes: int) -> datetime:
    """Return a timezone-aware timestamp `minutes` from now."""
    return timezone.now() + timedelta(minutes=minutes)


def is_expired(expires_at: datetime) -> bool:
    """Return True if the given timestamp is at or before the current time."""
    return timezone.now() >= expires_at
