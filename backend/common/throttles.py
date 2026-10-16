"""
Custom DRF throttle classes with rates driven by Django settings.

All rates are defined in settings.py so they can be changed without
touching code. Defaults match the production hardening requirements:

- Anonymous OTP endpoints: 5/min
- AI Chat: 20/min
- Dashboard: 120/min
- NetSuite Sync: 30/min
"""
import hashlib
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, SimpleRateThrottle

class ClientIPThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        identity = self.get_ident(request)
        if not identity:
            return None
        
        return self.cache_format % {
            "scope":self.scope,
            "ident":identity,
        }

class EmailThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        email = str(request.data.get("email") or "").strip().casefold()
        
        if not email:
            return None
        
        email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope":self.scope,
            "ident":email_hash,
        }

class LoginPasswordIPThrottle(ClientIPThrottle):
    scope = "login_password_ip"

class LoginPasswordEmailThrottle(EmailThrottle):
    scope = "login_password_email"

class LoginVerifyIPThrottle(ClientIPThrottle):
    scope = "login_verify_ip"

class LoginVerifyEmailThrottle(EmailThrottle):
    scope = "login_verify_email"

class LoginResendIPThrottle(ClientIPThrottle):
    scope = "login_resend_ip"

class LoginResendEmailThrottle(EmailThrottle):
    scope = "login_resend_email"

class RegisterOTPThrottle(AnonRateThrottle):
    scope = 'register_otp'

class DashboardThrottle(UserRateThrottle):
    scope = 'dashboard'

class NetSuiteSyncThrottle(UserRateThrottle):
    scope = 'netsuite_sync'

class HealthCheckThrottle(AnonRateThrottle):
    scope = 'health_check'
