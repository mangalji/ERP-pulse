"""Company-scoped AI integration API views."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.common_utils import success_response
from ocr.ai.config import PROVIDERS, models_for
from ocr.ai.providers import AIProviderError
from ocr.ai.service import ai_configuration_service


def _is_company_admin(user) -> bool:
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    role = getattr(user, "role", None)
    return role is not None and role.name.lower() == "company admin"


class AIConfigurationView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        company = getattr(request.user, "company", None)
        if company is None:
            return None
        return company

    def get(self, request):
        company = self._company(request)
        if company is None:
            return Response(
                {"detail": "No company is associated with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        configuration = ai_configuration_service.get_configuration(company=company)
        return success_response(
            message="AI configuration fetched successfully.",
            data=ai_configuration_service.serialize(configuration),
        )

    def post(self, request):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only a Company Admin can manage AI integration."},
                status=status.HTTP_403_FORBIDDEN,
            )

        company = self._company(request)
        if company is None:
            return Response(
                {"detail": "No company is associated with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            configuration = ai_configuration_service.connect(
                company=company,
                provider=request.data.get("provider"),
                model=request.data.get("model"),
                api_key=request.data.get("api_key"),
                user=request.user,
                request=request,
            )
        except (ValueError, AIProviderError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="AI provider connected successfully.",
            data=ai_configuration_service.serialize(configuration),
        )


class AIConfigurationTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only a Company Admin can manage AI integration."},
                status=status.HTTP_403_FORBIDDEN,
            )

        company = getattr(request.user, "company", None)
        if company is None:
            return Response(
                {"detail": "No company is associated with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ai_configuration_service.test(
                company=company,
                provider=request.data.get("provider"),
                model=request.data.get("model"),
                api_key=request.data.get("api_key"),
                user=request.user,
            )
        except (ValueError, AIProviderError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="AI provider connection test successful.",
            data={"tested": True},
        )


class AIConfigurationDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only a Company Admin can manage AI integration."},
                status=status.HTTP_403_FORBIDDEN,
            )

        company = getattr(request.user, "company", None)
        if company is None:
            return Response(
                {"detail": "No company is associated with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ai_configuration_service.disconnect(
            company=company,
            user=request.user,
            request=request,
        )

        return success_response(
            message="AI provider disconnected successfully.",
            data={"connected": False},
        )


class AIProvidersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(
            message="AI providers fetched successfully.",
            data={
                "providers": list(PROVIDERS),
                "models": {
                    provider["value"]: models_for(provider["value"])
                    for provider in PROVIDERS
                },
            },
        )
