from datetime import timedelta
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from common.pagination import paginated_response
from common.common_utils import success_response
from superadmin.models import Plan, PlanStatus
from superadmin.permissions import IsSuperAdmin
from superadmin.serializers import (
    CompanySerializer,
    CompanyDetailSerializer,
    PlanSerializer,
    PlanDetailSerializer,
    UserSerializer,
    TransactionSerializer,
    SuperAdminEmployeeSerializer,
    CompanyUpdateSerializer,
)
from superadmin.services import SuperAdminService
from tenancy.models import Company, CompanyDeletionHistory, CompanyDepartment, CompanySuspensionReason
from tenancy.services import company_lifecycle_service
from subscriptions.services import subscription_service
from invitations.models import Invitation

User = get_user_model()
superadmin_service = SuperAdminService()


class CompanyViewSet(viewsets.ModelViewSet):
    """Manage client companies from the AGSuite portal."""

    queryset = Company.objects.all()    
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
        )

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
        """Override to return company detail with subscription, employees, and netsuite info."""
        company = self.get_object()
        serializer = CompanyDetailSerializer(company)
        return success_response(
            message='Company fetched successfully.',
            data=serializer.data,
        )

    @staticmethod
    def _ensure_departments(company):
        existing = CompanyDepartment.objects.filter(company=company)
        if not existing.exists():
            CompanyDepartment.objects.bulk_create(
                [
                    CompanyDepartment(company=company, name=name)
                    for name in ('HR', 'NetSuite', 'IT Support', 'Development')
                ]
            )

    @action(detail=True, methods=['get', 'post'], url_path='departments')
    def departments(self, request, pk=None):
        company = self.get_object()
        self._ensure_departments(company)
        if request.method == 'GET':
            departments = CompanyDepartment.objects.filter(
                company=company,
                is_active=True,
                is_deleted=False,
            ).order_by('name')
            return success_response(
                message='Departments fetched successfully.',
                data=[{'id': str(item.id), 'name': item.name} for item in departments],
            )

        name = str(request.data.get('name') or '').strip()
        if not name or len(name) > 150:
            raise ValidationError('Enter a department name up to 150 characters.')
        item = CompanyDepartment.objects.filter(company=company, name__iexact=name).first()
        if item is None:
            item = CompanyDepartment.objects.create(
                company=company,
                name=name,
                created_by=request.user,
                updated_by=request.user,
            )
        elif not item.is_active:
            item.is_active, item.is_deleted, item.deleted_at = True, False, None
            item.save(update_fields=['is_active', 'is_deleted', 'deleted_at', 'updated_at'])
        return success_response(
            message='Department saved successfully.',
            data={'id': str(item.id), 'name': item.name},
        )

    @action(detail=True, methods=['delete'], url_path=r'departments/(?P<department_id>[^/.]+)')
    def delete_department(self, request, pk=None, department_id=None):
        company = self.get_object()
        item = CompanyDepartment.objects.filter(
            pk=department_id,
            company=company,
            is_active=True,
            is_deleted=False,
        ).first()
        if item is None:
            return Response({'detail': 'Department not found.'}, status=status.HTTP_404_NOT_FOUND)
        item.is_active = False
        item.save(update_fields=['is_active', 'updated_at'])
        return success_response(message='Department removed successfully.')

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        with transaction.atomic():
            company = Company.objects.select_for_update().get(pk=pk)
            old_state = {
                'status': company.status,
                'suspension_reason': company.suspension_reason,
            }
            company.status = Company.Status.SUSPENDED
            company.suspension_reason = CompanySuspensionReason.MANUAL
            company.save(update_fields=['status','suspension_reason','updated_at'])
            audit_service.log(
                module=AuditModule.COMPANY,
                action=AuditAction.UPDATE,
                entity='Company lifecycle',
                entity_id=str(company.id),
                company=company,
                user=request.user,
                old_value=old_state,
                new_value={
                    'status': company.status,
                    'suspension_reason': company.suspension_reason,
                },
            )
        
        return success_response(message='Company suspended successfully.', data={'id': str(company.id),'status':company.status})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        with transaction.atomic():
            company = Company.objects.select_for_update().get(pk=pk)
            if company.is_deleted:
                raise ValidationError(
                    {'detail': 'A deleted company must be restored before activation.'}
                )
            if not company_lifecycle_service.can_activate(company=company):
                raise ValidationError(
                    {
                        'detail': (
                            'Please assign a plan and complete its transaction '
                            'before activating this company.'
                        )
                    }
                )

            old_state = {
                'status': company.status,
                'suspension_reason': company.suspension_reason,
            }
            company.status = Company.Status.ACTIVE
            company.suspension_reason = CompanySuspensionReason.NONE
            company.save(
                update_fields=['status', 'suspension_reason', 'updated_at']
            )
            audit_service.log(
                module=AuditModule.COMPANY,
                action=AuditAction.UPDATE,
                entity='Company lifecycle',
                entity_id=str(company.id),
                company=company,
                user=request.user,
                old_value=old_state,
                new_value={
                    'status': company.status,
                    'suspension_reason': company.suspension_reason,
                },
            )

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
        return success_response(
            message='Company restored successfully.',
            data={
                'id': str(company.id),
                'status': company.status,
            },
        )

    @action(detail=True, methods=['post'], url_path='permanently-delete')
    def permanently_delete(self, request, pk=None):
        """Immediately hard-delete a company already in the recovery bin."""
        company = self.get_object()
        try:
            result = superadmin_service.permanently_delete_company(
                company_id=company.id,
                deleted_by=request.user,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})

        return success_response(
            message='Company permanently deleted successfully.',
            data=result,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='complete-transaction',
    )
    def complete_transaction(self, request, pk=None):
        company = self.get_object()

        transaction_id = request.data.get('transaction_id')

        if not transaction_id:
            raise ValidationError(
                {'transaction_id': 'Transaction ID is required.'}
            )

        try:
            transaction_record = (
                subscription_service.complete_plan_transaction(
                    company_id=company.id,
                    transaction_id=transaction_id,
                    request=request,
                )
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})

        return success_response(
            message='Transaction completed and plan assigned successfully.',
            data=TransactionSerializer(transaction_record).data,
        )

    @action(detail=True,methods=['post'],url_path='assign-plan-pending',)
    def assign_plan_pending(self, request, pk=None):
        company = self.get_object()

        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value', 0)

        if not plan_id:
            raise ValidationError(
                {'plan_id': 'Plan selection is required.'}
            )

        try:
            transaction_record = (
                subscription_service.create_pending_plan_transaction(
                    company_id=company.id,
                    plan_id=plan_id,
                    discount_type=discount_type,
                    discount_value=discount_value,
                    request=request,
                )
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})

        return success_response(
            message='Plan assignment transaction created successfully. Payment is pending.',
            data=TransactionSerializer(transaction_record).data,
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
    queryset = Plan.objects.filter(is_deleted=False)
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
        plan.status = PlanStatus.INACTIVE
        plan.save(
            update_fields=[
                'is_deleted',
                'deleted_at',
                'status',
            ]
        )
        return success_response(message='Plan deleted successfully.')

    def destroy(self, request, *args, **kwargs):
        plan = self.get_object()
    
        plan.is_deleted = True
        plan.deleted_at = timezone.now()
        plan.status = PlanStatus.INACTIVE
    
        plan.save(
            update_fields=[
                'is_deleted',
                'deleted_at',
                'status',
            ]
        )
    
        return success_response(
            message='Plan deleted successfully.'
        )


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('company').all()
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name', 'employee_id', 'designation', 'department']
    ordering_fields = ['first_name', 'last_name', 'created_at']
    ordering = ['first_name', 'last_name']
    # Super Admin employee administration deliberately has only the explicit
    # create/activate/deactivate/invitation actions below.  Keeping DRF's
    # default PATCH/PUT/DELETE routes exposed would bypass their validation,
    # company-lifecycle and audit services.
    http_method_names = ['get', 'post', 'head', 'options']

    def create(self, request, *args, **kwargs):
        """Block DRF's generic user creation route.

        Creation must go through ``create_employee`` so the invitation,
        lifecycle, field validation and Employee-only role policy are all
        applied together.
        """
        raise MethodNotAllowed('POST')

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
        page = list(queryset[offset:offset + limit])
        latest_invitation_by_email = {}
        if page:
            for invitation in (
                Invitation.objects.filter(
                    company__in=[employee.company for employee in page if employee.company_id],
                    email__in=[employee.email for employee in page],
                )
                .order_by('-created_at')
            ):
                latest_invitation_by_email.setdefault(invitation.email, invitation)
            
        return paginated_response(
            message='Employees fetched successfully.',
            results=SuperAdminEmployeeSerializer(
                page,
                many=True,
                context={'latest_invitation_by_email': latest_invitation_by_email},
            ).data,
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
        designation = request.data.get('designation', '')
        department = request.data.get('department', '')
        role = request.data.get("role")

        # Super Admin can make an initial Employee or Company Admin invite,
        # but cannot use this endpoint to alter an existing user's role.
        if role not in {"employee", "company_admin"}:
            raise ValidationError(
                "Select either the Employee or Company Admin role."
            )

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
                request=request,
                mobile_number=mobile_number,
                country=country,
                designation=designation,
                department=department,
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
            employee = superadmin_service.activate_employee(
                employee_id=pk,
                acting_user=request.user,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
            )
        return success_response(message='Employee activated successfully.', data=UserSerializer(employee).data)



class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsSuperAdmin]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        summary = superadmin_service.get_dashboard_summary()
        return success_response(message='Platform dashboard summary fetched successfully.', data=summary)
