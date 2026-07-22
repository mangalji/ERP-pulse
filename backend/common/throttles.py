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

class LoginOTPThrottle(AnonRateThrottle):
     scope = 'login_otp'

class RegisterOTPThrottle(AnonRateThrottle):
    scope = 'register_otp'

class AIChatThrottle(UserRateThrottle):
    scope = 'ai_chat'

class DashboardThrottle(UserRateThrottle):
    scope = 'dashboard'

class NetSuiteSyncThrottle(UserRateThrottle):
    scope = 'netsuite_sync'
