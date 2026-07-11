"""
Authentication API views.
 
Kept in a dedicated module (rather than accounts/views.py) because the
Authentication module owns several endpoints across Sprint 2 Day 2
(Register, Verify Registration OTP, Login, Verify Login OTP, ...) and
grouping them here keeps accounts/views.py free for other domain views
later.
 
Views only: authenticate, validate via serializer, call
authentication_service, return the standard response envelope. All
business logic lives in AuthenticationService
(accounts/authentication_service.py) — views never touch models or
repositories directly.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView as BaseTokenBlacklistView
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from accounts.authentication_service import AuthenticationService
from accounts.serializers import (
    RegisterSerializer, 
    VerifyRegistrationOTPSerializer,
    UserSerializer,
    LoginSerializer,
    VerifyLoginOTPSerializer,
    )
from common.utils.response import success_response

authentication_service = AuthenticationService()

class RegisterView(APIView):
    """
    POST /api/v1/auth/register
 
    Registers a new user and triggers a REGISTRATION OTP email. The
    account stays inactive/unverified until the OTP is confirmed via
    VerifyRegistrationOTPView.
    """

    permission_classes = [AllowAny]

    def post(self,request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authentication_service.register(**serializer.validated_data)

        return success_response(
            message='Registration successful. Please verify the OTP sent to your email.',
            data={'email':user.email},
            status_code=status.HTTP_201_CREATED
        )

class VerifyRegistrationOTPView(APIView):
    """
    POST /api/v1/register/verify-otp/
 
    Verifies the REGISTRATION OTP and activates the account on success.
    """
    permission_classes = [AllowAny]
    
    def post(self,request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authentication_service.verify_registration_otp(**serializer.validated_data)

        return success_response(
            message="Account verified successfully.",
            data={'email':user.email,'is_active':user.is_active},
        ) 
     
class LoginView(APIView):
    """
    POST /api/v1/auth/login/
 
    Step 1 of login: verifies email/password and, if the account is
    active and verified, sends a LOGIN OTP. Issues no token — that only
    happens after VerifyLoginOTPView succeeds.
    """
 
    permission_classes = [AllowAny]
 
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
 
        user = authentication_service.login(**serializer.validated_data)
 
        return success_response(
            message='OTP sent to your registered email. Please verify to continue.',
            data={'email': user.email},
        )
 
 
class VerifyLoginOTPView(APIView):
    """
    POST /api/v1/auth/login/verify-otp/
 
    Step 2 of login: verifies the LOGIN OTP and, on success, issues a
    fresh JWT access/refresh pair via SimpleJWT. Token generation happens
    here (the view layer), not in authentication_service, since JWTs are a
    delivery-mechanism concern, not a business rule — the service still
    owns all OTP/credential decisions and simply returns the User.
    """
 
    permission_classes = [AllowAny]
 
    def post(self, request):
        serializer = VerifyLoginOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
 
        user = authentication_service.verify_login_otp(**serializer.validated_data)
 
        refresh = RefreshToken.for_user(user)
 
        return success_response(
            message='Login successful.',
            data={
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
            },
        )
 
 
class TokenRefreshView(BaseTokenRefreshView):
    """
    POST /api/v1/auth/token/refresh/
 
    Thin wrapper around SimpleJWT's official TokenRefreshView/serializer —
    no custom refresh logic. Only reformats the output into the project's
    standard response envelope.
    """
 
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            # Mirrors SimpleJWT's own TokenViewBase.post() exactly: a raw
            # TokenError (e.g. blacklisted/expired token) is not a DRF
            # APIException on its own, so it must be converted to
            # InvalidToken or it escapes as an unhandled 500.
            raise InvalidToken(e.args[0])
 
        return success_response(
            message='Token refreshed successfully.',
            data=serializer.validated_data,
        )
 
 
class LogoutView(BaseTokenBlacklistView):
    """
    POST /api/v1/auth/logout/
 
    Thin wrapper around SimpleJWT's official TokenBlacklistView/
    serializer — blacklists the submitted refresh token using the
    official rest_framework_simplejwt.token_blacklist app. No custom
    blacklist mechanism.
 
    Deliberately keeps SimpleJWT's default (empty) authentication/
    permission classes, matching TokenRefreshView — the refresh token in
    the body is the credential. Requiring a separately-valid access token
    on top would be a custom deviation from the official view: a refresh
    token should stay revocable even if its paired access token already
    expired.
    """
 
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])
 
        return success_response(message='Logged out successfully.')
 
 
class MeView(APIView):
    """
    GET /api/v1/auth/me/
 
    Returns the currently authenticated user's public-safe profile.
    Reuses UserSerializer rather than defining the field set again.
    """
 
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        return success_response(
            message='User fetched successfully.',
            data=UserSerializer(request.user).data,
        )