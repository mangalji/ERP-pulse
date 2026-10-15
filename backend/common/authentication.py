"""
Custom JWT authentication that reads the access token from an httpOnly
cookie (in addition to the standard Authorization header).

This allows the refresh token to be stored as an httpOnly cookie (safe from
XSS — JavaScript can never read it) while the access token can travel
either way. The cookie approach means the frontend never needs to
explicitly manage token strings in JavaScript (no localStorage, no
sessionStorage, no JS-accessible variables).

Backward-compatible: the Authorization header is checked first, then the
cookie. This lets API clients (curl, Postman, third-party integrations)
continue using the Bearer header without any code change.
"""

import logging

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


def enforce_cookie_csrf(request):
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied('CSRF verification failed. Reload the page and retry.')


class TenantJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.company_id:
            from tenancy.services import company_lifecycle_service
            if not company_lifecycle_service.is_operational(company=user.company):
                raise PermissionDenied('Your company account is suspended.')
        return user


class CheckedTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs['refresh'])
        # SimpleJWT's default refresh serializer does not check the password
        # revocation claim. Reuse get_user for both revocation and tenancy.
        TenantJWTAuthentication().get_user(token)
        return super().validate(attrs)


logger = logging.getLogger(__name__)

# Cookie names — must match what the login/refresh/logout views set.
ACCESS_COOKIE_NAME = getattr(settings, 'JWT_AUTH_COOKIE', 'access_token')
REFRESH_COOKIE_NAME = getattr(settings, 'JWT_AUTH_REFRESH_COOKIE', 'refresh_token')


class CookieJWTAuthentication(BaseAuthentication):
    """
    Falls back to reading the access token from an httpOnly cookie named
    `access_token` when no Authorization header is present.

    Usage in settings:
        REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = [
            'common.authentication.CookieJWTAuthentication',
            'rest_framework_simplejwt.authentication.JWTAuthentication',
        ]
    """

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    def authenticate(self, request):
        """
        Try the Authorization header first (standard SimpleJWT path), then
        fall back to the httpOnly cookie. This way curl/Postman clients
        keep working unchanged.
        """
        # If the request already has an Authorization header, let SimpleJWT
        # handle it as usual — no need to read the cookie.
        raw_token = request.META.get('HTTP_AUTHORIZATION')
        if raw_token:
            return None  # Let the next auth class in the chain handle it

        # No Authorization header — try the access_token cookie.
        access_token = request.COOKIES.get(ACCESS_COOKIE_NAME)
        if not access_token:
            return None  # No cookie either — move to the next auth class

        # Validate the token via SimpleJWT's own validator.
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

        jwt_auth = TenantJWTAuthentication()
        try:
            validated_token = jwt_auth.get_validated_token(access_token)

        except (InvalidToken, TokenError):
            logger.debug("Ignoring invalid access_token cookie.")
            return None
        try:
            user = jwt_auth.get_user(validated_token)
        except AuthenticationFailed:
            logger.debug("Ignoring access_token cookie for inactive/invalid user.")
            return None
        enforce_cookie_csrf(request)
        return user, validated_token


def set_auth_cookies(response, access_token, refresh_token=None):
    """
    Set JWT tokens as httpOnly cookies on the given response.
    Safe to call on login, token refresh, or any view that issues new tokens.

    The access token cookie is used by CookieJWTAuthentication (above) and
    the frontend's apiClient (which sends credentials automatically).
    The refresh token cookie is used by the custom TokenRefreshView to
    obtain new access tokens without exposing the refresh token to JS.
    """
    _set_cookie(
        response,
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=getattr(settings, 'JWT_AUTH_COOKIE_ACCESS_MAX_AGE', None),
    )
    if refresh_token:
        _set_cookie(
            response,
            REFRESH_COOKIE_NAME,
            refresh_token,
            max_age=getattr(settings, 'JWT_AUTH_COOKIE_REFRESH_MAX_AGE', None),
        )


def clear_auth_cookies(response):
    """Remove JWT auth cookies — call on logout."""
    _set_cookie(response, ACCESS_COOKIE_NAME, '', max_age=0)
    _set_cookie(response, REFRESH_COOKIE_NAME, '', max_age=0)


def _set_cookie(response, name, value, max_age=None):
    """
    Set a single httpOnly cookie with production-hardened defaults.
    All parameters are configurable via Django settings with the
    JWT_AUTH_COOKIE_* prefix so they can differ between local dev and
    production without touching code.
    """
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        secure=getattr(settings, 'JWT_AUTH_COOKIE_SECURE', not settings.DEBUG),
        httponly=True,
        samesite=getattr(settings, 'JWT_AUTH_COOKIE_SAMESITE', 'Lax'),
        path=getattr(settings, 'JWT_AUTH_COOKIE_PATH', '/'),
    )
