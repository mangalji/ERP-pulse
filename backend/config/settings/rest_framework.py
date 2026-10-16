"""
Django REST Framework configuration for AGSuite ERP.
"""

from decouple import config


# ------------------------------------------------------------------
# Django REST Framework
# ------------------------------------------------------------------

REST_FRAMEWORK = {

    # Authentication
    # CookieJWTAuthentication: reads access token from the httpOnly
    # cookie set on login (safe from XSS). Falls back to the standard
    # Authorization header if present, so API clients (curl, Postman)
    # keep working unchanged.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "common.authentication.CookieJWTAuthentication",
        "common.authentication.TenantJWTAuthentication",
    ),

    # Permissions
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),

    # Exception Handler
    "EXCEPTION_HANDLER": (
        "common.exception_handler.standard_exception_handler"
    ),

    "NUM_PROXIES": config(
        "THROTTLE_NUM_PROXIES",
        default=1,
        cast=int,
    ),

    # Throttling
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),

    "DEFAULT_THROTTLE_RATES": {

        "anon": config(
            "THROTTLE_ANON",
            default="100/min",
        ),

        "user": config(
            "THROTTLE_USER",
            default="1000/min",
        ),

        "login_password_ip": config(
            "THROTTLE_LOGIN_PASSWORD_IP",
            default="10/min",
        ),
        "login_password_email": config(
            "THROTTLE_LOGIN_PASSWORD_EMAIL",
            default="10/hour",
        ),
        "login_verify_ip": config(
            "THROTTLE_LOGIN_VERIFY_IP",
            default="10/min",
        ),
        "login_verify_email": config(
            "THROTTLE_LOGIN_VERIFY_EMAIL",
            default="5/hour",
        ),
        "login_resend_ip": config(
            "THROTTLE_LOGIN_RESEND_IP",
            default="5/min",
        ),
        "login_resend_email": config(
            "THROTTLE_LOGIN_RESEND_EMAIL",
            default="5/hour",
        ),

        "register_otp": config(
            "THROTTLE_REGISTER_OTP",
            default="5/min",
        ),
        
        "dashboard": config(
            "THROTTLE_DASHBOARD",
            default="120/min",
        ),

        "netsuite_sync": config(
            "THROTTLE_NETSUITE_SYNC",
            default="30/min",
        ),

        "health_check": config(
            "THROTTLE_HEALTH_CHECK",
            default="60/min",
        ),
    },
}