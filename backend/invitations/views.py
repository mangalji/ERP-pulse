"""
Invitation API views.

Views are intentionally thin — they validate input via serializers,
delegate business logic to InvitationService, and format the standard
success envelope. No business rules live here.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from common.throttles import RegisterOTPThrottle
from common.pagination import paginated_response
from common.common_utils import success_response
from .models import Invitation
from .permissions import IsSuperAdmin
from .serializers import (
    AcceptInvitationSerializer,
    InvitationSerializer,
    InvitationValidateSerializer,
    RequestInvitationOTPSerializer,
)
from .services import invitation_service


class InvitationViewSet(viewsets.ViewSet):
    """
    Invitation management for super admins and public acceptance.
    """

    def get_permissions(self):
        if self.action in ['validate', 'request_otp', 'accept']:
            return [AllowAny()]
        if self.action in ['send', 'resend', 'list_invitations', 'retrieve_invitation']:
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action in ['request_otp', 'accept', 'validate']:
            return [RegisterOTPThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=['get'], url_path='list')
    def list_invitations(self, request):
        """
        GET /api/v1/invitations/list/ — super admin lists invitations.
        """
        from .models import Invitation
        qs = Invitation.objects.select_related('company', 'role', 'created_by').all()
        
        company_id = request.query_params.get('company_id')
        status_param = request.query_params.get('status')
        search = request.query_params.get('search')
        
        if company_id:
            qs = qs.filter(company_id=company_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if search:
            qs = qs.filter(email__icontains=search)
        
        qs = qs.order_by('-created_at')
        
        try:
            offset = int(request.query_params.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get('limit', 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))
        
        count = qs.count()
        page = qs[offset:offset + limit]
        
        return paginated_response(
            message='Invitations fetched successfully.',
            results=InvitationSerializer(page, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    @action(detail=True, methods=['get'], url_path='detail')
    def retrieve_invitation(self, request, pk=None):
        """
        GET /api/v1/invitations/{id}/detail/ — super admin retrieves invitation.
        """
        invitation = invitation_service.get_invitation(request_id=pk)
        return success_response(
            message='Invitation fetched successfully.',
            data=InvitationSerializer(invitation).data,
        )

    @action(detail=True, methods=['post'], url_path='send')
    def send(self, request, pk=None):
        """
        POST /api/v1/invitations/{id}/send/ — resend invitation email.
        """
        invitation = invitation_service.send_invitation(
            invitation_id=pk,
            request=request,
        )
        return success_response(
            message='Invitation sent successfully.',
            data=InvitationSerializer(invitation).data,
        )

    @action(detail=True, methods=['post'], url_path='resend')
    def resend(self, request, pk=None):
        """
        POST /api/v1/invitations/{id}/resend/ — resend with extended expiry.
        """
        invitation = invitation_service.resend_invitation(
            invitation_id=pk,
            request=request,
        )
        return success_response(
            message='Invitation resent successfully.',
            data=InvitationSerializer(invitation).data,
        )

    @action(detail=False, methods=['get'])
    def validate(self, request):
        """
        GET /api/v1/invitations/validate/ — public token validation.
        """
        token = request.query_params.get('token')
        if not token:
            return Response(
                {'detail': 'token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            invitation = invitation_service.validate_token(token)
            return success_response(
                message='Invitation is valid.',
                data=InvitationSerializer(invitation).data,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
    @action(detail=False, methods=['post'], url_path='request-otp')
    def request_otp(self,request):
        """
        POST /api/v1/invitations/request-otp/

        Validate the invitation and send an invitation-specific OTP.
        """
        serializer = RequestInvitationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = invitation_service.request_invitation_otp(
                token=serializer.validated_data['token'],
                password=serializer.validated_data['password'],
            )

            return success_response(
                message='OTP sent successfully. Please check your email.',
                data={
                    'email': user.email,
                },
            )

        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(
        detail=False,
        methods=['post'],
        url_path='resend-otp',
        permission_classes=[AllowAny],
        throttle_classes=[RegisterOTPThrottle],
    )
    def resend_otp(self, request):
        """
        POST /api/v1/invitations/resend-otp/

        Resend the invitation-specific OTP.
        Invitation links themselves can be resent only by an authenticated
        company or platform administrator.
        """
        serializer = InvitationValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = invitation_service.resend_invitation_otp(
                token=serializer.validated_data['token'],
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message='A new OTP has been sent successfully. Please check your email.',
            data={'email': user.email},
        )

    @action(detail=False, methods=['post'])
    def accept(self, request):
        """
        POST /api/v1/invitations/accept/
        Verify invitation OTP and complete account activation.
        """
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = invitation_service.accept_invitation(
                token=serializer.validated_data['token'],
                password=serializer.validated_data['password'],
                otp=serializer.validated_data['otp'],
                # first_name=serializer.validated_data['first_name'],
                # last_name=serializer.validated_data['last_name'],
            )
            return success_response(
                message='Invitation accepted successfully. You can now log in.',
                data={'email': user.email},
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
