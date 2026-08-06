"""
Demo Request API views.

Views are intentionally thin — they validate input via the serializer,
delegate business logic to ``DemoRequestService``, and format the
standard success envelope. No business rules live here.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from common.throttles import RegisterOTPThrottle
from common.utils.pagination import paginated_response
from common.utils.response import success_response
from superadmin.permissions import IsSuperAdmin

from .serializers import DemoRequestSerializer
from .services import demo_request_service
from common.utils.response import success_response


class DemoRequestViewSet(viewsets.ViewSet):
    """Public request submission + super-admin management."""

    def get_permissions(self):
        # Public endpoint: anyone may submit a demo request.
        if self.action == "submit":
            return [AllowAny()]
        # Every other action is super-admin only.
        return [IsSuperAdmin()]

    def get_throttles(self):
        # Anonymous rate limiting on the public submission endpoint.
        if self.action == "submit":
            return [RegisterOTPThrottle()]
        return super().get_throttles()

    @action(
    detail=False,
    methods=["post"],
    permission_classes=[AllowAny],
    throttle_classes=[RegisterOTPThrottle],
    url_path="submit",
    )
    def submit(self, request):
        serializer = DemoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            demo_request = demo_request_service.create_request(
                serializer.validated_data,
                request.user if request.user.is_authenticated else None,
            )

            return success_response(
                message="Demo request submitted successfully.",
                data=DemoRequestSerializer(demo_request).data,
                status_code=status.HTTP_201_CREATED,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"], url_path="list")
    def all_requests(self, request):
        """GET /api/v1/demo/list/ — super-admin list of requests."""
        page, count, offset, limit = demo_request_service.list_requests(
            request=request,
            status=request.query_params.get("status"),
            search=request.query_params.get("search"),
        )
        return paginated_response(
            message="Demo requests fetched successfully.",
            results=DemoRequestSerializer(page, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    @action(detail=True, methods=["get"], url_path="detail")
    def retrieve_detail(self, request, pk=None):
        """GET /api/v1/demo/<id>/detail/ — super-admin retrieve."""
        demo_request = demo_request_service.get_request(request_id=pk)
        return success_response(
            message="Demo request fetched successfully.",
            data=DemoRequestSerializer(demo_request).data,
        )

    @action(detail=True, methods=["post"], url_path="assign")
    def assign_sales(self, request, pk=None):
        """POST /api/v1/demo/<id>/assign/ — assign an AGSuite sales user."""
        user_id = request.data.get("user_id")
        if not user_id:
            return success_response(
                message="user_id is required",
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            demo_request = demo_request_service.assign_sales(
                request_id=pk,
                user_id=user_id,
                notes=request.data.get("notes"),
                request=request,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return success_response(
            message="Sales user assigned successfully.",
            data=DemoRequestSerializer(demo_request).data,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """POST /api/v1/demo/<id>/approve/ — approve a demo request."""
        demo_request = demo_request_service.approve(
            request_id=pk,
            notes=request.data.get("notes"),
            request=request,
        )
        return success_response(
            message="Demo request approved successfully.",
            data=DemoRequestSerializer(demo_request).data,
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """POST /api/v1/demo/<id>/reject/ — reject a demo request."""
        demo_request = demo_request_service.reject(
            request_id=pk,
            notes=request.data.get("notes"),
            request=request,
        )
        return success_response(
            message="Demo request rejected successfully.",
            data=DemoRequestSerializer(demo_request).data,
        )

    @action(detail=True, methods=["post"], url_path="convert")
    def convert_to_company(self, request, pk=None):
        """POST /api/v1/demo/{id}/convert/ — convert demo request to company."""
        data = request.data
        try:
            result = demo_request_service.convert_to_company(
                request_id=pk,
                request=request,
                plan_id=data.get('plan_id'),
                module_ids=data.get('module_ids'),
                admin_email=data.get('admin_email'),
                admin_first_name=data.get('admin_first_name'),
                admin_last_name=data.get('admin_last_name'),
            )
            return success_response(
                message='Company converted successfully.',
                data=result,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
