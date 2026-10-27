from django.conf import settings
from django.shortcuts import redirect
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from common.common_utils import success_response
from mail_integration.serializers import (
    EmailIntegrationConfigureSerializer,
    EmailIntegrationCreateSerializer,
    EmailIntegrationSerializer,
    EmailOAuthCallbackSerializer,
)
from mail_integration.services import EmailIntegrationService
from mail_integration.health import email_processing_status


class EmailIntegrationCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        integrations = EmailIntegrationService().list_company_integrations(user=request.user)
        return success_response(
            message="Email integrations fetched successfully.",
            data=EmailIntegrationSerializer(integrations, many=True).data,
        )

    def post(self, request):
        serializer = EmailIntegrationCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        integration, authorization_url = EmailIntegrationService().create_connection(
            user=request.user,
            **serializer.validated_data,
        )
        return success_response(
            message="Mailbox connection is ready for authorization.",
            data={
                "integration": EmailIntegrationSerializer(integration).data,
                "authorization_url": authorization_url,
            },
        )


class EmailProcessingHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        service = EmailIntegrationService()
        service.list_company_integrations(user=request.user)
        return success_response(
            message="Email processing status fetched successfully.",
            data=email_processing_status(),
        )


class EmailOAuthCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = EmailOAuthCallbackSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        service = EmailIntegrationService()
        if data.get("error"):
            service.mark_oauth_failed(
                state=data["state"],
                error_message=data.get("error_description") or data["error"],
            )
            return redirect(
                f"{settings.FRONTEND_URL.rstrip('/')}/#/app/integrations/email?email=failed"
            )
        if not data.get("code"):
            from mail_integration.exceptions import EmailIntegrationStateError
            raise EmailIntegrationStateError("The email provider did not return an authorization code.")
        from mail_integration.exceptions import EmailRefreshTokenMissingError
        try:
            service.complete_oauth(code=data["code"], state=data["state"])
        except EmailRefreshTokenMissingError as exc:
            # complete_oauth rolls back on failure; record the error afterwards.
            service.mark_oauth_failed(state=data["state"], error_message=str(exc))
            return redirect(
                f"{settings.FRONTEND_URL.rstrip('/')}/#/app/integrations/email?email=failed"
            )
        return redirect(
            f"{settings.FRONTEND_URL.rstrip('/')}/#/app/integrations/email?email=connected"
        )


class EmailIntegrationActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, integration_id):
        integration = EmailIntegrationService().activate(
            user=request.user,
            integration_id=integration_id,
        )
        return success_response(
            message="Active mailbox switched successfully.",
            data=EmailIntegrationSerializer(integration).data,
        )


class EmailIntegrationSyncReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, integration_id):
        EmailIntegrationService().check_initial_sync_ready(user=request.user, integration_id=integration_id)
        return success_response(message="Email sync is ready to configure.", data={})


class EmailIntegrationPauseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, integration_id):
        integration = EmailIntegrationService().set_paused(user=request.user, integration_id=integration_id, paused=True)
        return success_response(message="Automatic email processing stopped.", data=EmailIntegrationSerializer(integration).data)


class EmailIntegrationResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, integration_id):
        integration = EmailIntegrationService().set_paused(user=request.user, integration_id=integration_id, paused=False)
        return success_response(message="Automatic email processing resumed.", data=EmailIntegrationSerializer(integration).data)


class EmailIntegrationDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, integration_id):
        integration = EmailIntegrationService().disconnect(user=request.user, integration_id=integration_id)
        return success_response(message="Mailbox disconnected.", data=EmailIntegrationSerializer(integration).data)


class EmailIntegrationInitialSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, integration_id):
        serializer = EmailIntegrationConfigureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        integration = EmailIntegrationService().configure_initial_sync(
            user=request.user,
            integration_id=integration_id,
            **serializer.validated_data,
        )
        return success_response(
            message="Initial email sync is configured.",
            data=EmailIntegrationSerializer(integration).data,
        )


class EmailIntegrationReconnectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, integration_id):
        integration, authorization_url = EmailIntegrationService().reconnect_url(
            user=request.user,
            integration_id=integration_id,
        )
        return success_response(
            message="Mailbox reconnection is ready for authorization.",
            data={
                "integration": EmailIntegrationSerializer(integration).data,
                "authorization_url": authorization_url,
            },
        )
