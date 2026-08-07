from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from common.utils.pagination import paginated_response
from common.utils.response import success_response
from notifications.models import Notification
from superadmin.models import (
    CompanyPlan, Plan, SupportSession,
    SubscriptionHistory, Transaction,
)
from superadmin.permissions import IsSuperAdmin
from superadmin.serializers import (
    CompanyModuleSerializer,
    CompanyPlanSerializer,
    CompanySerializer,
    CompanyDetailSerializer,
    ModuleSerializer,
    PlanSerializer,
    PlanDetailSerializer,
    SupportSessionSerializer,
    UserSerializer,
    SubscriptionHistorySerializer,
    TransactionSerializer,
)
from superadmin.services import SuperAdminService
from tenancy.models import Company, CompanyModule, Module
from rbac.models import Role, UserRole

User = get_user_model()
superadmin_service = SuperAdminService()


class CompanyViewSet(viewsets.ModelViewSet):
    """Manage client companies from the AGSuite portal."""

    queryset = Company.objects.all().select_related('settings').prefetch_related('company_modules__module')
    serializer_class = CompanySerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'contact_email']
    ordering_fields = ['name', 'created_at', 'status']
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.annotate(
            user_count=Count('users', distinct=True),
            module_count=Count('company_modules', distinct=True),
        ).prefetch_related('company_plans')

    def list(self, request, *args, **kwargs):
        """Override to return paginated response in success envelope format."""
        queryset = self.filter_queryset(self.get_queryset())
        offset = int(request.query_params.get('offset', 0))
        limit = int(request.query_params.get('limit', 20))
        count = queryset.count()
        page = queryset[offset:offset + limit]
        return paginated_response(
            message='Companies fetched successfully.',
            results=CompanySerializer(page, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    def retrieve(self, request, *args, **kwargs):
        """Override to return company detail with subscription, modules, employees, and netsuite info."""
        company = self.get_object()
        serializer = CompanyDetailSerializer(company)
        return success_response(
            message='Company fetched successfully.',
            data=serializer.data,
        )

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        company = self.get_object()
        company.status = Company.Status.SUSPENDED
        company.save(update_fields=['status'])
        audit_service.log(
            module=AuditModule.TENANCY,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company=company,
            user=request.user,
            old_value={'status': Company.Status.ACTIVE},
            new_value={'status': company.status},
        )
        return success_response(message='Company suspended successfully.', data={'id': str(company.id)})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        company = self.get_object()
        company.status = Company.Status.ACTIVE
        company.save(update_fields=['status'])
        audit_service.log(
            module=AuditModule.TENANCY,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company=company,
            user=request.user,
            old_value={'status': Company.Status.SUSPENDED},
            new_value={'status': company.status},
        )
        return success_response(message='Company activated successfully.', data={'id': str(company.id)})

    @action(detail=True, methods=['post'])
    def soft_delete(self, request, pk=None):
        company = self.get_object()
        company.soft_delete()
        audit_service.log(
            module=AuditModule.TENANCY,
            action=AuditAction.DELETE,
            entity='Company',
            entity_id=str(company.id),
            company=company,
            user=request.user,
        )
        return success_response(message='Company soft deleted successfully.', data={'id': str(company.id)})

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        company = self.get_object()
        company.restore()
        audit_service.log(
            module=AuditModule.TENANCY,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company=company,
            user=request.user,
        )
        return success_response(message='Company restored successfully.', data={'id': str(company.id)})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        data = superadmin_service.get_dashboard_summary()
        return success_response(
            message='Company statistics fetched successfully.',
            data={
            "total_companies": data["total_companies"],
            "active_companies": data["active_companies"],
            "trial_companies": data["trial_companies"],
            "suspended_companies": data["suspended_companies"],
            "total_users": (
                data["total_agsuite_employees"]
                + data["total_client_employees"]
            ),
            "ag_suite_users": data["total_agsuite_employees"],
            "company_users": data["total_client_employees"],
             },
         )

    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        data = superadmin_service.get_company_transactions(company_id=pk)
        return success_response(message='Transactions fetched successfully.', data=data)


class PlanViewSet(viewsets.ModelViewSet):
    queryset = Plan.objects.all().prefetch_related('enabled_models')
    serializer_class = PlanSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'monthly_price', 'yearly_price', 'created_at']
    ordering = ['name']

    def list(self, request, *args, **kwargs):
        """Override to return paginated response in success envelope format."""
        queryset = self.filter_queryset(self.get_queryset())
        offset = int(request.query_params.get('offset', 0))
        limit = int(request.query_params.get('limit', 20))
        count = queryset.count()
        page = queryset[offset:offset + limit]
        return paginated_response(
            message='Plans fetched successfully.',
            results=PlanSerializer(page, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    def retrieve(self, request, *args, **kwargs):
        """Override to return plan detail with included modules and companies using this plan."""
        plan = self.get_object()
        plan_data = PlanDetailSerializer(plan).data

        # Companies using this plan
        companies = CompanyPlan.objects.filter(plan=plan).select_related('company').order_by('company__name')
        company_list = [
            {
                'company_id': str(cp.company.id),
                'company_name': cp.company.name,
                'status': cp.status,
                'start_date': cp.start_date,
                'end_date': cp.end_date,
            }
            for cp in companies
        ]
        plan_data['companies_using'] = company_list

        return success_response(
            message='Plan fetched successfully.',
            data=plan_data,
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        plan = self.get_object()
        plan.status = PlanStatus.ACTIVE
        plan.save(update_fields=['status'])
        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='Plan',
            entity_id=str(plan.id),
            user=request.user,
            old_value={'status': 'INACTIVE'},
            new_value={'status': plan.status},
        )
        return success_response(message='Plan activated successfully.', data=PlanSerializer(plan).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        plan = self.get_object()
        plan.status = PlanStatus.INACTIVE
        plan.save(update_fields=['status'])
        audit_service.log(
            module=AuditModule.SUBSCRIPTION,
            action=AuditAction.UPDATE,
            entity='Plan',
            entity_id=str(plan.id),
            user=request.user,
            old_value={'status': 'ACTIVE'},
            new_value={'status': plan.status},
        )
        return success_response(message='Plan deactivated successfully.', data=PlanSerializer(plan).data)


class CompanyPlanViewSet(viewsets.ModelViewSet):
    queryset = CompanyPlan.objects.select_related('company', 'plan')
    serializer_class = CompanyPlanSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['company__name', 'plan__name']
    ordering_fields = ['start_date', 'created_at', 'status']
    ordering = ['-start_date']

    @action(detail=False, methods=['post'])
    def assign(self, request):
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        status_value = request.data.get('status')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id or not plan_id:
            return Response({'detail': 'company_id and plan_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        company_plan = superadmin_service.assign_plan(
            company_id=company_id, plan_id=plan_id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, assigned_by=request.user,
            status=status_value,
        )
        return success_response(message='Plan assigned successfully.', data=CompanyPlanSerializer(company_plan).data)

    @action(detail=False, methods=['post'])
    def upgrade(self, request):
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id or not plan_id:
            return Response({'detail': 'company_id and plan_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        company_plan = superadmin_service.upgrade_plan(
            company_id=company_id, plan_id=plan_id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, assigned_by=request.user,
        )
        return success_response(message='Plan upgraded successfully.', data=CompanyPlanSerializer(company_plan).data)

    @action(detail=False, methods=['post'])
    def downgrade(self, request):
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id or not plan_id:
            return Response({'detail': 'company_id and plan_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        company_plan = superadmin_service.downgrade_plan(
            company_id=company_id, plan_id=plan_id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, assigned_by=request.user,
        )
        return success_response(message='Plan downgraded successfully.', data=CompanyPlanSerializer(company_plan).data)

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        company_id = request.data.get('company_id')
        if not company_id:
            return Response({'detail': 'company_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        company_plan = superadmin_service.cancel_plan(company_id=company_id, assigned_by=request.user)
        return success_response(message='Plan cancelled successfully.', data=CompanyPlanSerializer(company_plan).data)

    @action(detail=False, methods=['post'])
    def renew(self, request):
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id:
            return Response({'detail': 'company_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        company_plan = superadmin_service.renew_plan(
            company_id=company_id, plan_id=plan_id,
            discount_type=discount_type, discount_value=discount_value,
            billing_cycle=billing_cycle, assigned_by=request.user,
        )
        return success_response(message='Plan renewed successfully.', data=CompanyPlanSerializer(company_plan).data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        data = superadmin_service.get_company_plan_history(company_id=pk)
        return success_response(message='Company plan history fetched successfully.', data=data)


class SupportSessionViewSet(viewsets.ModelViewSet):
    queryset = SupportSession.objects.select_related('company', 'support_user')
    serializer_class = SupportSessionSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reason', 'company__name', 'support_user__email']
    ordering_fields = ['started_at', 'ended_at', 'status']
    ordering = ['-started_at']

    @action(detail=False, methods=['post'])
    def start(self, request):
        company_id = request.data.get('company_id')
        support_user_id = request.data.get('support_user_id')
        reason = request.data.get('reason')
        ip_address = request.data.get('ip_address')
        if not company_id or not support_user_id or not reason:
            return Response({'detail': 'company_id, support_user_id, and reason are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            session = superadmin_service.start_support_session(
                company_id=company_id,
                support_user_id=support_user_id,
                reason=reason,
                ip_address=ip_address,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(message='Support session started successfully.', data=SupportSessionSerializer(session).data)

    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        session = superadmin_service.end_support_session(session_id=pk)
        return success_response(message='Support session ended successfully.', data=SupportSessionSerializer(session).data)


class ModuleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'display_name']
    ordering_fields = ['sort_order', 'name', 'created_at']
    ordering = ['sort_order', 'name']


class CompanyModuleViewSet(viewsets.ViewSet):
    permission_classes = [IsSuperAdmin]

    @action(detail=False, methods=['get'])
    def fetch(self, request):
        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response({'detail': 'company_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        modules = superadmin_service.list_company_modules(company_id=company_id)
        return success_response(message='Company modules fetched successfully.', data=modules)

    @action(detail=False, methods=['post'])
    def set_module(self, request):
        company_id = request.data.get('company_id')
        module_id = request.data.get('module_id')
        enabled = request.data.get('enabled')
        if not company_id or not module_id:
            return Response({'detail': 'company_id and module_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        company_module = superadmin_service.set_company_module_state(
            company_id=company_id,
            module_id=module_id,
            enabled=bool(enabled),
        )
        return success_response(message='Company module updated successfully.', data=CompanyModuleSerializer(company_module).data)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        company_id = request.data.get('company_id')
        module_ids = request.data.get('module_ids')
        enabled = request.data.get('enabled')
        if not company_id or not module_ids:
            return Response({'detail': 'company_id and module_ids are required.'}, status=status.HTTP_400_BAD_REQUEST)
        updated = superadmin_service.bulk_set_company_modules(
            company_id=company_id,
            module_ids=module_ids,
            enabled=bool(enabled),
        )
        return success_response(message='Company modules updated successfully.', data=[CompanyModuleSerializer(item).data for item in updated])


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('company').all()
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name', 'employee_id', 'designation', 'department']
    ordering_fields = ['first_name', 'last_name', 'created_at']
    ordering = ['first_name', 'last_name']

    @action(detail=False, methods=['post'])
    def create_employee(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        company_id = request.data.get('company_id')
        role_ids = request.data.get('role_ids',[])
        if isinstance(role_ids, str):
            role_ids = [role_ids]
        if not email:
            return Response({'detail': 'email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            employee = superadmin_service.create_employee(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                company_id=company_id,
                role_ids=role_ids,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(message='Employee created successfully.', data=UserSerializer(employee).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        employee = superadmin_service.deactivate_employee(employee_id=pk)
        return success_response(message='Employee deactivated successfully.', data=UserSerializer(employee).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        employee = superadmin_service.activate_employee(employee_id=pk)
        return success_response(message='Employee activated successfully.', data=UserSerializer(employee).data)

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        role_id = request.data.get('role_id')
        if not role_id:
            return Response({'detail': 'role_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        result = superadmin_service.assign_user_role(user_id=pk, role_id=role_id)
        return success_response(message='Employee role assigned successfully.', data={'created': result['created']})

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        role_id = request.data.get('role_id')
        if not role_id:
            return Response({'detail': 'role_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        result = superadmin_service.remove_user_role(user_id=pk, role_id=role_id)
        return success_response(message='Employee role removed successfully.', data={'deleted': result['deleted']})


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsSuperAdmin]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        summary = superadmin_service.get_dashboard_summary()
        return success_response(message='Platform dashboard summary fetched successfully.', data=summary)


class NotificationViewSet(viewsets.ViewSet):
    permission_classes = [IsSuperAdmin]

    @action(detail=False, methods=['get'])
    def fetch(self, request):
        searchable = request.query_params.get('search')
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            is_read = is_read.lower() in {'1', 'true', 'yes'}
        try:
            limit = int(request.query_params.get('limit',20))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {
                    'detail':'limit and offset must be integers.'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        notifications = superadmin_service.list_notifications(
            user=request.user,
            searchable=searchable,
            is_read=is_read,
            limit=limit,
            offset=offset,
        )
        return success_response(message='Notifications fetched successfully.', data=notifications)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = superadmin_service.unread_notifications_count(user=request.user)
        return success_response(message='Unread notification count fetched successfully.', data={'count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = superadmin_service.mark_notification_read(notification_id=pk, user=request.user)
        return success_response(message='Notification marked as read.', data={'id': str(notification.id), 'is_read': notification.is_read})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        result = superadmin_service.mark_all_notifications_read(user=request.user)
        return success_response(message='All notifications marked as read.', data=result)