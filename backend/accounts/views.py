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
from accounts.repositories import LoginActivityRepository
from accounts.serializers import (
    RegisterSerializer, 
    ResendRegistrationOTPSerializer,
    VerifyRegistrationOTPSerializer,
    CompleteProfileSerializer,
    UserSerializer,
    LoginSerializer,
    VerifyLoginOTPSerializer,
    ResendLoginOTPSerializer,
    LoginActivitySerializer,
    )
from common.utils.response import success_response
from common.throttles import LoginOTPThrottle, RegisterOTPThrottle

authentication_service = AuthenticationService()
login_activity_repository = LoginActivityRepository()

def _get_client_ip(request) -> str | None:
    """
    Prefers X-Forwarded-For's first hop (the original client) over
    REMOTE_ADDR, since Render/most PaaS deployments sit behind a proxy
    that would otherwise make every login appear to come from the same
    internal proxy IP.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

class RegisterView(APIView):
    """
    POST /api/v1/auth/register/

    Step 1 of registration: validates email/password and triggers a
    REGISTRATION OTP email. No User row is created here — the pending
    registration (email + hashed password + OTP) lives in a cache-backed
    store until Complete Profile succeeds (see
    accounts/registration_cache.py and AuthenticationService's module
    docstring for the full flow).
    """

    permission_classes = [AllowAny]
    throttle_classes = [RegisterOTPThrottle]

    def post(self,request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = authentication_service.register(**serializer.validated_data)

        return success_response(
            message='OTP sent to your email. Please verify to continue registration.',
            data=result,
            status_code=status.HTTP_201_CREATED
        )

class ResendRegistrationOTPView(APIView):
    """
    POST /api/v1/auth/register/resend-otp/

    Resends the REGISTRATION OTP for an in-flight registration.
    AuthenticationService enforces the 60-second cooldown and invalidates
    the previous code — this view only validates shape and calls it.
    """

    permission_classes = [AllowAny]
    throttle_classes = [RegisterOTPThrottle]

    def post(self, request):
        serializer = ResendRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = authentication_service.resend_registration_otp(**serializer.validated_data)

        return success_response(
            message='A new verification code has been sent to your email.',
            data=result,
        )

class VerifyRegistrationOTPView(APIView):
    """
    POST /api/v1/auth/register/verify-otp/

    Verifies the REGISTRATION OTP. Still does not create the User — on
    success it returns a short-lived signed `registration_token` that
    CompleteProfileView requires, proving this email passed OTP
    verification. The frontend should navigate to the Complete Profile
    page with this token after a successful response.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegisterOTPThrottle]
    
    def post(self,request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = authentication_service.verify_registration_otp(**serializer.validated_data)

        return success_response(
            message='Email verified. Please complete your profile to finish registration.',
            data=result,
        ) 

class CompleteProfileView(APIView):
    """
    POST /api/v1/auth/register/complete-profile/

    Final step of registration: validates the signed registration_token
    and mobile-number uniqueness, then creates the User — active and
    email-verified immediately, since OTP verification already proved the
    email. Issues no JWT (matching the existing decision that registration
    never auto-logs a user in — they complete the normal Login flow next).
    """

    permission_classes = [AllowAny]
    throttle_classes = [RegisterOTPThrottle]

    def post(self, request):
        serializer = CompleteProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authentication_service.complete_registration(**serializer.validated_data)

        return success_response(
            message='Registration completed successfully. Please log in to continue.',
            data={'email': user.email},
            status_code=status.HTTP_201_CREATED,
        )
    
class LoginView(APIView):
    """
    POST /api/v1/auth/login/
 
    Step 1 of login: verifies email/password and, if the account is
    active and verified, sends a LOGIN OTP. Issues no token — that only
    happens after VerifyLoginOTPView succeeds.
    """
 
    permission_classes = [AllowAny]
    throttle_classes = [LoginOTPThrottle]
 
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
    throttle_classes = [LoginOTPThrottle]
  
    def post(self, request):
        serializer = VerifyLoginOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
 
        user = authentication_service.verify_login_otp(**serializer.validated_data)
 
        refresh = RefreshToken.for_user(user)

        login_activity_repository.create(
            user=user,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512] or None,
        )

        return success_response(
            message='Login successful.',
            data={
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
            },
        )
 
class ResendLoginOTPView(APIView):
    """
    POST /api/v1/auth/login/resend-otp/
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginOTPThrottle]

    def post(self, request):
        serializer = ResendLoginOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = authentication_service.resend_login_otp(**serializer.validated_data)

        return success_response(
            message="A new login verification code has been sent to your email.",
            data=result,
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

class LoginHistoryView(APIView):
    """
    GET /api/v1/auth/login-history/

    Most recent logins first (LoginActivity.Meta.ordering), capped at 50
    by LoginActivityRepository.list_by_user()'s default limit.
    """

    permission_classes = [IsAuthenticated]

    def get(self,request):
        activities = login_activity_repository.list_by_user(request.user)
        return success_response(
            message="login history fetched successfully.",
            date=LoginActivitySerializer(activities,many=True).data,
        )
    
from django.http import JsonResponse

def health(request):
    return JsonResponse({
        "status": "ok",
        "service": "ERP Pulse Backend"
    })