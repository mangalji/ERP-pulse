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
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),

    # Permissions
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),

    # Exception Handler
    "EXCEPTION_HANDLER": (
        "common.exception_handler.standard_exception_handler"
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

        "login_otp": config(
            "THROTTLE_LOGIN_OTP",
            default="5/min",
        ),

        "register_otp": config(
            "THROTTLE_REGISTER_OTP",
            default="5/min",
        ),

        "ai_chat": config(
            "THROTTLE_AI_CHAT",
            default="60/min",
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