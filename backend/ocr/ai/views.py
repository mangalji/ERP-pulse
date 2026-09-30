"""Company-scoped AI integration API views."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.common_utils import success_response
from common.throttles import NetSuiteSyncThrottle
from ocr.ai.catalogue_service import ai_model_catalogue_service
from ocr.ai.config import models_for, providers_for
# from ocr.ai.diagnostics_service import net_suite_diagnostics_service
from netsuite.diagnostics_service import net_suite_diagnostics_service
from ocr.ai.providers import AIProviderError
from ocr.ai.service import ai_configuration_service

logger = logging.getLogger(__name__)


def _is_company_admin(user) -> bool:
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    role = getattr(user, "role", None)
    return role is not None and role.name.lower() == "company admin"


def _error_response(message: str, status_code: int):
    return Response(
        {
            "success": False,
            "message": message,
            "data": {},
        },
        status=status_code,
    )


def _friendly_ai_exception(
    exc,
    *,
    operation: str,
) -> tuple[str, int]:
    if isinstance(exc, ValueError):
        return str(exc), status.HTTP_400_BAD_REQUEST

    if getattr(exc, "quota_exhausted", False):
        return (
            "The AI provider has reached the usage limit for this API key. "
            "Please check your provider quota or plan.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    provider_status = getattr(exc, "status_code", None)

    if provider_status in {401, 403}:
        return (
            "The API key was rejected by the AI provider. "
            "Please check the key and try again.",
            status.HTTP_400_BAD_REQUEST,
        )

    if provider_status == 404:
        return (
            "The selected AI model is not available. "
            "Please refresh the model list and try again.",
            status.HTTP_400_BAD_REQUEST,
        )

    if getattr(exc, "rate_limited", False):
        return (
            "The AI provider is temporarily limiting requests. "
            "Please wait a moment and try again.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if provider_status in {408, 500, 502, 503, 504}:
        return (
            "The AI provider is temporarily unavailable. "
            "Please try again in a moment.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if getattr(exc, "retryable", False):
        return (
            "The AI provider is temporarily unavailable. "
            "Please try again in a moment.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if operation == "refresh":
        return (
            "We couldn't refresh the AI model list. "
            "Please try again.",
            status.HTTP_502_BAD_GATEWAY,
        )

    if operation == "test":
        return (
            "We couldn't verify the AI connection. "
            "Please check the API key and model and try again.",
            status.HTTP_400_BAD_REQUEST,
        )

    if operation == "diagnostics":
        return (
            "We couldn't generate resolution guidance right now. "
            "The NetSuite validation result is still available above. Please try again.",
            status.HTTP_502_BAD_GATEWAY,
        )

    return (
        "We couldn't connect the AI provider. "
        "Please check the configuration and try again.",
        status.HTTP_400_BAD_REQUEST,
    )


def _handle_ai_exception(exc, *, operation: str):
    message, status_code = _friendly_ai_exception(
        exc,
        operation=operation,
    )
    return _error_response(message, status_code)


class AIConfigurationView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        return getattr(request.user, "company", None)

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
            return _handle_ai_exception(exc, operation="connect")
        except Exception:
            logger.exception("Unexpected AI configuration connection error.")
            return _error_response(
                "We couldn't connect the AI provider right now. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            message="AI provider connected successfully.",
            data=ai_configuration_service.serialize(configuration),
        )


class AIConfigurationTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_company_admin(request.user):
            return _error_response(
                "Only a Company Admin can manage AI integration.",
                status.HTTP_403_FORBIDDEN,
            )

        company = getattr(request.user, "company", None)
        if company is None:
            return _error_response(
                "No company is associated with this user.",
                status.HTTP_400_BAD_REQUEST,
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
            return _handle_ai_exception(exc, operation="test")
        except Exception:
            logger.exception("Unexpected AI connection test error.")
            return _error_response(
                "We couldn't verify the AI connection right now. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            message="AI provider connection test successful.",
            data={"tested": True},
        )


class AIConfigurationDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_company_admin(request.user):
            return _error_response(
                "Only a Company Admin can manage AI integration.",
                status.HTTP_403_FORBIDDEN,
            )

        company = getattr(request.user, "company", None)
        if company is None:
            return _error_response(
                "No company is associated with this user.",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            ai_configuration_service.disconnect(
                company=company,
                user=request.user,
                request=request,
            )
        except Exception:
            logger.exception("Unexpected AI disconnect error.")
            return _error_response(
                "We couldn't disconnect the AI provider right now. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            message="AI provider disconnected successfully.",
            data={"connected": False},
        )


class AIProvidersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            providers = providers_for()
            return success_response(
                message="AI providers fetched successfully.",
                data={
                    "providers": providers,
                    "models": {
                        provider["value"]: models_for(provider["value"])
                        for provider in providers
                    },
                },
            )
        except Exception:
            logger.exception("Failed to load AI provider catalogue.")
            return _error_response(
                "We couldn't load the AI provider list right now. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AIProvidersRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_company_admin(request.user):
            return _error_response(
                "Only a Company Admin can refresh AI models.",
                status.HTTP_403_FORBIDDEN,
            )

        company = getattr(request.user, "company", None)
        if company is None:
            return _error_response(
                "No company is associated with this user.",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = ai_model_catalogue_service.refresh_provider(
                company=company,
                provider=request.data.get("provider"),
                supplied_api_key=request.data.get("api_key"),
            )

            return success_response(
                message=f"{result['provider_name']} models refreshed successfully.",
                data=result,
            )
        except (ValueError, AIProviderError) as exc:
            return _handle_ai_exception(exc, operation="refresh")
        except Exception:
            logger.exception("Unexpected AI model catalogue refresh error.")
            return _error_response(
                "We couldn't refresh the AI model list right now. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NetSuiteAIDiagnosticsView(APIView):
    """Generate guidance for persisted NetSuite validation errors only."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def post(self, request):
        company = getattr(request.user, "company", None)
        if company is None:
            return _error_response(
                "No company is associated with this user.",
                status.HTTP_400_BAD_REQUEST,
            )

        connection_id = str(request.data.get("connection_id") or "").strip()
        validation_ids = request.data.get("validation_ids")

        if not connection_id:
            return _error_response(
                "A NetSuite connection is required for resolution guidance.",
                status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(validation_ids, list) or not validation_ids:
            return _error_response(
                "No NetSuite validation results were supplied.",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = net_suite_diagnostics_service.diagnose(
                company=company,
                connection_id=connection_id,
                validation_ids=validation_ids,
            )

            return success_response(
                message="NetSuite resolution guidance generated successfully.",
                data=result,
            )
        except (ValueError, AIProviderError) as exc:
            return _handle_ai_exception(exc, operation="diagnostics")
        except Exception:
            logger.exception("Unexpected NetSuite AI diagnostics error.")
            return _error_response(
                "We couldn't generate resolution guidance right now. "
                "The NetSuite validation result is still available above. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
