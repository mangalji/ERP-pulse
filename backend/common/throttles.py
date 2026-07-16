"""
Custom DRF throttle classes with rates driven by Django settings.

All rates are defined in settings.py so they can be changed without
touching code. Defaults match the production hardening requirements:

- Anonymous OTP endpoints: 5/min
- AI Chat: 20/min
- Dashboard: 120/min
- NetSuite Sync: 30/min
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from django.conf import settings


# class _SettingsRateThrottleMixin:
#     """Mixin that reads `rate` from Django settings instead of hardcoding."""

#     @property
#     def rate(self):
#         key = getattr(self, 'setting_name', None)
#         if key and hasattr(settings, key):
#             return getattr(settings, key)
#         return super().rate

#     @rate.setter
#     def rate(self, value):
#         # DRF expects a setter; delegate to parent.
#         super(type(self), self.__class__).rate.fset(self, value)


# class LoginOTPThrottle(_SettingsRateThrottleMixin, AnonRateThrottle):
#     setting_name = 'THROTTLE_LOGIN_OTP'
#     scope = 'login_otp'

class LoginOTPThrottle(AnonRateThrottle):
     scope = 'login_otp'


# class RegisterOTPThrottle(_SettingsRateThrottleMixin, AnonRateThrottle):
class RegisterOTPThrottle(AnonRateThrottle):
    # setting_name = 'THROTTLE_REGISTER_OTP'
    scope = 'register_otp'


# class AIChatThrottle(_SettingsRateThrottleMixin, UserRateThrottle):
class AIChatThrottle(UserRateThrottle):
    # setting_name = 'THROTTLE_AI_CHAT'
    scope = 'ai_chat'


# class DashboardThrottle(_SettingsRateThrottleMixin, UserRateThrottle):
class DashboardThrottle(UserRateThrottle):
    # setting_name = 'THROTTLE_DASHBOARD'
    scope = 'dashboard'


# class NetSuiteSyncThrottle(_SettingsRateThrottleMixin, UserRateThrottle):
class NetSuiteSyncThrottle(UserRateThrottle):
    # setting_name = 'THROTTLE_NETSUITE_SYNC'
    scope = 'netsuite_sync'
