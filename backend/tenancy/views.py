"""
Client Company Portal API views.

Thin views: authenticate, validate input, call ClientPortalService, and
return the standard response envelope. Every company-scoped operation
derives the company from ``request.user.company`` — never from the
client. Views never touch models directly.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import UserSerializer
from common.utils.pagination import paginated_response
from common.utils.response import success_response
from tenancy.permissions import IsCompanyUser
from tenancy.serializers import (
    ClientRoleSerializer,
    CompanyEmployeeSerializer,
    CompanyProfileSerializer,
    CompanySettingsUpdateSerializer,
    CreateEmployeeSerializer,
    UpdateEmployeeSerializer,
)
from tenancy.services import ClientPortalService
from tenancy.permissions import IsCompanyUser, CanManageEmployees

client_portal_service = ClientPortalService()


class ClientMeView(APIView):
    """
    GET /api/v1/client/me/

    Returns the authenticated user's context: user profile, company,
    enabled modules and role names.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        context = client_portal_service.get_client_context(user=request.user)
        data = {
            'user': UserSerializer(context['user']).data,
            'company': (
                {
                    'id': str(context['company'].id),
                    'name': context['company'].name,
                    'code': context['company'].code,
                    'status': context['company'].status,
                }
                if context['company']
                else None
            ),
            'modules': context['modules'],
            'roles': context['roles'],
            'permissions': context['permissions'],
            'plan': context['plan'],
        }
        return success_response(message='Client context fetched successfully.', data=data)


class CompanyEmployeeViewSet(viewsets.ViewSet):
    """
    Company-scoped employee management.

    All operations are scoped to ``request.user.company``. A company_id
    supplied by the client is never trusted.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser, CanManageEmployees]
    # required_permission = 'employee.manage'

    def _company(self, request):
        return request.user.company

    def list(self, request):
        company = self._company(request)
        search = request.query_params.get('search')
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

        queryset = client_portal_service.list_employees(company=company, search=search)
        count = queryset.count()
        page = queryset[offset:offset + limit]
        return paginated_response(
            message='Employees fetched successfully.',
            results=CompanyEmployeeSerializer(page, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    def retrieve(self, request, pk=None):
        company = self._company(request)
        employee = client_portal_service.get_employee(company=company, employee_id=pk)
        return success_response(
            message='Employee fetched successfully.',
            data=CompanyEmployeeSerializer(employee).data,
        )

    def create(self, request):
        company = self._company(request)
        serializer = CreateEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            employee = client_portal_service.create_employee(
                company=company,
                acting_user=request.user,
                **serializer.validated_data,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(
            message='Employee created successfully.',
            data=CompanyEmployeeSerializer(employee).data,
            status_code=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        company = self._company(request)
        serializer = UpdateEmployeeSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        employee = client_portal_service.update_employee(
            company=company,
            employee_id=pk,
            acting_user=request.user,
            **serializer.validated_data,
        )
        return success_response(
            message='Employee updated successfully.',
            data=CompanyEmployeeSerializer(employee).data,
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        company = self._company(request)
        employee = client_portal_service.activate_employee(
            company=company, employee_id=pk, acting_user=request.user,
        )
        return success_response(
            message='Employee activated successfully.',
            data=CompanyEmployeeSerializer(employee).data,
        )

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        company = self._company(request)
        employee = client_portal_service.deactivate_employee(
            company=company, employee_id=pk, acting_user=request.user,
        )
        return success_response(
            message='Employee deactivated successfully.',
            data=CompanyEmployeeSerializer(employee).data,
        )

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        company = self._company(request)
        role_id = request.data.get('role_id')
        if not role_id:
            return Response({'detail': 'role_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = client_portal_service.assign_role(
                company=company, employee_id=pk, role_id=role_id, acting_user=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(
            message='Role assigned successfully.',
            data={'created': result['created']},
        )

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        company = self._company(request)
        role_id = request.data.get('role_id')
        if not role_id:
            return Response({'detail': 'role_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = client_portal_service.remove_role(
                company=company, employee_id=pk, role_id=role_id, acting_user=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(
            message='Role removed successfully.',
            data={'deleted': result['deleted']},
        )

    @action(detail=True, methods=['post'])
    def resend_invitation(self, request, pk=None):
        company = self._company(request)
        try:
            employee = client_portal_service.resend_employee_invitation(
                company=company, employee_id=pk, acting_user=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(
            message='Invitation resent successfully.',
            data=CompanyEmployeeSerializer(employee).data,
        )


class ClientRoleListView(APIView):
    """
    GET /api/v1/client/roles/

    Returns only global roles (company IS NULL) and roles belonging to
    the current user's company. Never exposes another company's roles.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        roles = client_portal_service.list_assignable_roles(company=request.user.company)
        return success_response(
            message='Roles fetched successfully.',
            data=ClientRoleSerializer(roles, many=True).data,
        )


class CompanySettingsView(APIView):
    """
    GET /api/v1/client/settings/  — company profile
    PATCH /api/v1/client/settings/ — update company-level settings
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        company = request.user.company
        result = client_portal_service.get_company_settings(company=company)
        return success_response(
            message='Company settings fetched successfully.',
            data=CompanyProfileSerializer(result['company']).data,
        )

    def patch(self, request):
        company = request.user.company
        serializer = CompanySettingsUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        result = client_portal_service.update_company_settings(
            company=company,
            acting_user=request.user,
            data=serializer.validated_data,
        )
        return success_response(
            message='Company settings updated successfully.',
            data=CompanyProfileSerializer(result['company']).data,
        )


class ClientNotificationViewSet(viewsets.ViewSet):
    """
    User-scoped notification endpoints for the client portal.

    Dedicated client endpoints so the Super Admin notification API is
    never exposed to client company users.
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        try:
            limit = int(request.query_params.get('limit', 20))
            offset = int(request.query_params.get('offset', 0))
        except (ValueError, TypeError):
            return Response({'detail': 'limit and offset must be integers.'}, status=status.HTTP_400_BAD_REQUEST)

        is_read = request.query_params.get('is_read')
        if is_read is not None:
            is_read = is_read.lower() in {'1', 'true', 'yes'}

        notifications, count = client_portal_service.list_notifications(
            user=request.user,
            is_read=is_read,
            limit=limit,
            offset=offset,
        )
        data = [
            {
                'id': str(n.id),
                'title': n.title,
                'message': n.message,
                'type': n.type,
                'is_read': n.is_read,
                'created_at': n.created_at,
            }
            for n in notifications
        ]
        return success_response(
            message='Notifications fetched successfully.',
            data={'count': count, 'results': data},
        )

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = client_portal_service.unread_notifications_count(user=request.user)
        return success_response(message='Unread notification count fetched successfully.', data={'count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = client_portal_service.mark_notification_read(notification_id=pk, user=request.user)
        return success_response(
            message='Notification marked as read.',
            data={'id': str(notification.id), 'is_read': notification.is_read},
        )

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        result = client_portal_service.mark_all_notifications_read(user=request.user)
        return success_response(message='All notifications marked as read.', data=result)