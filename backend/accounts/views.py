"""
Authentication API views.
 
Kept in a dedicated module (rather than accounts/views.py) because the
Authentication module owns several endpoints across Sprint 2 Day 2
(Register, Verify Registration OTP, Login, Verify Login OTP, ...) and
grouping them here keeps accounts/views.py free for other domain views
later.
 
Views only: authenticate, validate via serializer, call
AuthenticationService, return the standard response envelope. All
business logic lives in AuthenticationService
(accounts/authentication_service.py) — views never touch models or
repositories directly.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from accounts.authentication_service import AuthenticationService
from accounts.serializers import RegisterSerializer, VerifyRegistrationOTPSerializer
from common.utils.response import success_response

class RegisterView(APIView):
    """
    POST /api/v1/auth/
 
    Registers a new user and triggers a REGISTRATION OTP email. The
    account stays inactive/unverified until the OTP is confirmed via
    VerifyRegistrationOTPView.
    """

    permission_classes = [AllowAny]

    def post(self,request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AuthenticationService().register(**serializer.validated_data)

        return success_response(
            message='Registration successful. Please verify the OTP sent to your email.',
            data={'email':user.email},
            status_code=status.HTTP_201_CREATED
        )

class VerifyRegistrationOTPView(APIView):
    """
    POST /api/v1/verify-otp/
 
    Verifies the REGISTRATION OTP and activates the account on success.
    """
    permission_classes = [AllowAny]
    
    def post(self,request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = AuthenticationService().verify_registration_otp(**serializer.validated_data)

        return success_response(
            message="Account verified successfully.",
            data={'email':user.email,'is_active':user.is_active},
        ) 
     