from datetime import timedelta
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
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
    SuperAdminEmployeeSerializer,
    CompanyUpdateSerializer,
)
from superadmin.services import SuperAdminService
from tenancy.models import Company, CompanyModule, Module, CompanyDeletionHistory, CompanySuspensionReason
from tenancy.services import company_lifecycle_service
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

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return CompanyUpdateSerializer
    
        return CompanySerializer

    def list(self, request, *args, **kwargs):
        """
        Return client companies with explicit lifecycle filtering.

        scope:
          - active      -> non-deleted companies
          - soft_deleted -> companies inside the 15-day recovery window
          - all         -> both active and soft-deleted companies
        """        
        queryset = self.filter_queryset(self.get_queryset())
        scope = request.query_params.get('scope','active')
        if scope == 'active':
            queryset = queryset.filter(is_deleted=False)

        elif scope == 'soft_deleted':
            queryset = queryset.filter(
                is_deleted=True,
                deleted_at__isnull=False,
            )

        elif scope != 'all':
            return Response(
                {
                    'detail': (
                        'Invalid scope. Use active, soft_deleted, or all.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            offset = max(0, int(request.query_params.get('offset', 0)))
            limit = int(request.query_params.get('limit', 10))

        except (TypeError, ValueError):
            return Response(
                {'detail': 'offset and limit must be integers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Never allow more than 10 companies in one response
        limit = max(1, min(limit, 10))
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
        company.suspension_reason = CompanySuspensionReason.MANUAL
        company.save(update_fields=['status','suspension_reason'])
        # audit_service.log(
        #     module=AuditModule.TENANCY,
        #     action=AuditAction.UPDATE,
        #     entity='Company',
        #     entity_id=str(company.id),
        #     company=company,
        #     user=request.user,
        #     old_value={'status': Company.Status.ACTIVE},
        #     new_value={'status': company.status},
        # )
        return success_response(message='Company suspended successfully.', data={'id': str(company.id),'status':company.status})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        company = self.get_object()
        if company.is_deleted:
            raise ValidationError(
                {'detail': 'A deleted company must be restored before activation.'}
            )
        effective_status = company_lifecycle_service.get_effective_status(
            company=company
            )
        if effective_status not in {
            Company.Status.ACTIVE,
            Company.Status.TRIAL,
        }:
            raise ValidationError(
                {
                    'detail': (
                        'Company cannot be activated because its subscription '
                        'is not currently valid.'
                    )
                }
            )
        company.status = effective_status
        company.suspension_reason = CompanySuspensionReason.NONE
        company.save(update_fields=['status','suspension_reason'])
        # audit_service.log(
        #     module=AuditModule.TENANCY,
        #     action=AuditAction.UPDATE,
        #     entity='Company',
        #     entity_id=str(company.id),
        #     company=company,
        #     user=request.user,
        #     # old_value={'status': Company.Status.SUSPENDED},
        #     new_value={'status': company.status},
        # )
        return success_response(message='Company activated successfully.', data={'id': str(company.id),'status':company.status})

    @action(detail=True, methods=['post'])
    def soft_delete(self, request, pk=None):
        company = self.get_object()
        now = timezone.now()
        company.is_deleted = True
        company.deleted_at = now
        company.status = Company.Status.SUSPENDED
        company.suspension_reason = CompanySuspensionReason.DELETED
        company.save(update_fields=['is_deleted','deleted_at','status','suspension_reason'])
        # audit_service.log(
        #     module=AuditModule.TENANCY,
        #     action=AuditAction.DELETE,
        #     entity='Company',
        #     entity_id=str(company.id),
        #     company=company,
        #     user=request.user,
        #     old_value={
        #         'status': company.status,
        #         'is_deleted': False,
        #     },
        #     new_value={
        #         'status': Company.Status.SUSPENDED,
        #         'is_deleted': True,
        #         'deleted_at': now.isoformat(),
        #     },
        #     )
        return success_response(message='Company soft deleted successfully.', 
            data={
            'id': str(company.id),
            'status': company.status,
            'deleted_at': company.deleted_at,
            'recovery_period_days': 15,
            },
        )
    

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        company = self.get_object()

        if not company.is_deleted:
            raise ValidationError(
                {'detail': 'This company is not soft deleted.'}
            )

        if company.deleted_at is None:
            raise ValidationError(
                {'detail': 'This company does not have a valid deletion timestamp.'}
            )

        recovery_deadline = company.deleted_at + timedelta(days=15)

        if timezone.now() >= recovery_deadline:
            raise ValidationError(
                {'detail': 'The 15-day recovery period has expired. This company can no longer be restored.'}
            )

        company.is_deleted = False
        company.deleted_at = None
        company.suspension_reason = CompanySuspensionReason.NONE

        # Re-evaluate status after removing soft-delete state.
        effective_status = company_lifecycle_service.get_effective_status(
            company=company
        )

        company.status = effective_status

        company.save(
            update_fields=[
                'is_deleted',
                'deleted_at',
                'status',
                'suspension_reason',
            ]
        )

        # audit_service.log(
        #     module=AuditModule.TENANCY,
        #     action=AuditAction.UPDATE,
        #     entity='Company',
        #     entity_id=str(company.id),
        #     company=company,
        #     user=request.user,
        #     new_value={
        #         'status': company.status,
        #         'is_deleted': False,
        #     },
        # )

        return success_response(
            message='Company restored successfully.',
            data={
                'id': str(company.id),
                'status': company.status,
            },
        )

    @action(detail=False, methods=['get'], url_path='permanently-deleted')
    def permanently_deleted(self, request):
        """
        Return permanent deletion history.
    
        The actual Company row and its tenant data no longer exist.
        Only CompanyDeletionHistory metadata is retained.
        """
        queryset = CompanyDeletionHistory.objects.select_related(
            'deleted_by'
        ).order_by('-permanently_deleted_at')
    
        try:
            offset = max(0, int(request.query_params.get('offset', 0)))
            limit = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'offset and limit must be integers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
        limit = max(1, min(limit, 10))
    
        count = queryset.count()
        page = queryset[offset:offset + limit]
    
        results = [
            {
                'id': str(item.id),
                'company_id': str(item.company_id_snapshot),
                'company_name': item.company_name,
                'company_code': item.company_code,
                'soft_deleted_at': item.soft_deleted_at,
                'permanently_deleted_at': item.permanently_deleted_at,
                'deleted_by': (
                    item.deleted_by.email
                    if item.deleted_by
                    else None
                ),
                'status': Company.Status.SUSPENDED,
                'lifecycle_status': 'PERMANENTLY_DELETED',
            }
            for item in page
        ]
    
        return paginated_response(
            message='Permanently deleted companies fetched successfully.',
            results=results,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    
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
    queryset = Plan.objects.filter(is_deleted=False).prefetch_related('enabled_models')
    serializer_class = PlanSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at']
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
        """Override to return plan detail."""
        plan = self.get_object()
        plan_data = PlanDetailSerializer(plan).data

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

    @action(detail=True, methods=['post'])
    def delete_plan(self, request, pk=None):
        plan = self.get_object()
        plan.is_deleted = True
        plan.deleted_at = timezone.now()
        plan.save(update_fields=['is_deleted', 'deleted_at'])
        return success_response(message='Plan deleted successfully.')


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
    def assign_pending(self, request):
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        if not company_id or not plan_id:
            return Response({'detail': 'company_id and plan_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = superadmin_service.create_pending_assignment(
                company_id=company_id, plan_id=plan_id,
                discount_type=discount_type, discount_value=discount_value,
                assigned_by=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(
            message='Plan assigned. Payment pending.',
            data={'transaction': TransactionSerializer(result['transaction']).data},
        )

    @action(detail=False, methods=['post'], url_path='complete_transaction')
    def complete_transaction(self, request):
        transaction_id = request.data.get('transaction_id')
        if not transaction_id:
            return Response({'detail': 'transaction_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = superadmin_service.complete_transaction(transaction_id=transaction_id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(
            message='Transaction completed. Subscription activated.',
            data={
                'company_plan': CompanyPlanSerializer(result['company_plan']).data,
                'transaction': TransactionSerializer(result['transaction']).data,
            }
        )

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

    def list(self,request,*args,**kwargs):
        """Return paginated employees in the standard success envelope."""
        queryset = self.filter_queryset(self.get_queryset())

        # Hide employees belonging to soft-deleted companies.
        queryset = queryset.filter(
            Q(company__isnull=True) | 
            Q(company__is_deleted=False)
        )
        company_id = request.query_params.get('company_id')

        if company_id:
            queryset = queryset.filter(
                company_id=company_id
            )
        try:
            offset=max(
                0,int(request.query_params.get('offset',0))
            )
            limit = int(request.query_params.get('limit',20))

        except (TypeError, ValueError):
            return Response(
                {
                    'detail':'offset and limit must be integers.'
                },status=status.HTTP_400_BAD_REQUEST,
            )
        count = queryset.count()
        page = queryset[offset:offset + limit]
            
        return paginated_response(
            message='Employees fetched successfully.',
            results=SuperAdminEmployeeSerializer(page, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    @action(detail=False, methods=['post'])
    def create_employee(self, request):
        email = request.data.get('email')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        company_id = request.data.get('company_id')
        mobile_number = request.data.get('mobile_number')
        country = request.data.get('country')
        gender = request.data.get('gender')
        role = request.data.get("role")

        if role not in ["admin","employee"]:
            raise ValidationError("Invalid role selected.")

        if not email:
            return Response({'detail': 'email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            employee = superadmin_service.create_employee(
                email=email,
                first_name=first_name,
                last_name=last_name,
                company_id=company_id,
                # role_ids=role_ids,
                role=role,
                acting_user=request.user,
                mobile_number=mobile_number,
                country=country,
                gender=gender,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return success_response(
            message='Invitation send successfully.', 
            data={
                'user': UserSerializer(employee['user']).data,
                'invitation_email_sent': employee['invitation_email_sent'],
                }
            )

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        try:
            employee = superadmin_service.deactivate_employee(employee_id=pk)
        except ValueError as exc:
            return Response(
                {'detail':str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        return success_response(message='Employee deactivated successfully.', data=UserSerializer(employee).data)

    @action(detail=True, methods=['post'])
    def resend_invitation(self, request, pk=None):
        try:
            invitation = superadmin_service.resend_employee_invitation(
                employee_id=pk,
                acting_user=request.user,
                request=request,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
    
        return success_response(
            message='Invitation resent successfully.',
            data={
                'invitation_id': str(invitation.id),
                'email': invitation.email,
                'expires_at': invitation.expires_at,
            },
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        try:
            employee = superadmin_service.activate_employee(employee_id=pk)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
            )
        return success_response(message='Employee activated successfully.', data=UserSerializer(employee).data)

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        role_id = request.data.get('role_id')
        if not role_id:
            return Response({'detail': 'role_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = superadmin_service.assign_user_role(user_id=pk, role_id=role_id)
        except ValueError as exc:
            return Response(
                {
                    'detail': str(exc)
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return success_response(message='Employee role assigned successfully.', data={'created': result['created']})

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        role_id = request.data.get('role_id')
        if not role_id:
            return Response({'detail': 'role_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = superadmin_service.remove_user_role(user_id=pk, role_id=role_id)
        except ValueError as exc:
            return Response(
                {
                    'detail': str(exc)
                },
                status=status.HTTP_403_FORBIDDEN,
            )
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