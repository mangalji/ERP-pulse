from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta
from .models import Plan, CompanyPlan, SupportSession
from .serializers import (
    PlanSerializer,
    CompanyPlanSerializer,
    SupportSessionSerializer,
    CompanySerializer,
    ModuleSerializer,
    CompanyModuleSerializer,
    UserSerializer,
)
from .permissions import IsSuperAdmin
from tenancy.models import Company, Module
from django.contrib.auth import get_user_model
from audit.services import audit_service
from audit.models import AuditAction, AuditModule

User = get_user_model()


class CompanyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing companies (Super Admin only).
    """
    queryset = Company.objects.all().select_related('settings').prefetch_related('company_modules__module')
    serializer_class = CompanySerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'country']
    search_fields = ['name', 'code', 'contact_email']
    ordering_fields = ['name', 'created_at', 'status']
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        # Annotate with extra counts for efficiency in list view
        queryset = queryset.annotate(
            user_count=Count('users'),
            module_count=Count('company_modules'),
        )
        return queryset

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        company = self.get_object()
        company.status = Company.Status.SUSPENDED
        company.save()
        audit_service.log(
            module=AuditModule.TENANCY,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company=company,
            user=request.user,
            old_value={'status': company.status},
            new_value={'status': company.status},
        )
        return Response({'status': 'Company suspended'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        company = self.get_object()
        company.status = Company.Status.ACTIVE
        company.save()
        audit_service.log(
            module=AuditModule.TENANCY,
            action=AuditAction.UPDATE,
            entity='Company',
            entity_id=str(company.id),
            company=company,
            user=request.user,
            old_value={'status': company.status},
            new_value={'status': company.status},
        )
        return Response({'status': 'Company activated'}, status=status.HTTP_200_OK)

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
        return Response({'status': 'Company soft deleted'}, status=status.HTTP_204_NO_CONTENT)

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
        return Response({'status': 'Company restored'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        total_companies = Company.objects.count()
        active_companies = Company.objects.filter(status=Company.Status.ACTIVE).count()
        trial_companies = Company.objects.filter(status=Company.Status.TRIAL).count()
        suspended_companies = Company.objects.filter(status=Company.Status.SUSPENDED).count()
        expired_companies = Company.objects.filter(status=Company.Status.EXPIRED).count()

        total_users = User.objects.count()
        ag_suite_users = User.objects.filter(company__isnull=True).count()
        company_users = User.objects.filter(company__isnull=False).count()

        return Response({
            'total_companies': total_companies,
            'active_companies': active_companies,
            'trial_companies': trial_companies,
            'suspended_companies': suspended_companies,
            'expired_companies': expired_companies,
            'total_users': total_users,
            'ag_suite_users': ag_suite_users,
            'company_users': company_users,
        }, status=status.HTTP_200.OK)


class PlanViewSet(viewsets.ModelViewSet):
    pass


class CompanyPlanViewSet(viewsets.ModelViewSet):
    pass


class SupportSessionViewSet(viewsets.ModelViewSet):
    pass


class ModuleViewSet(viewsets.ReadOnlyModelViewSet):
    pass


class CompanyModuleViewSet(viewsets.ViewSet):
    pass


class EmployeeViewSet(viewsets.ModelViewSet):
    pass


class DashboardViewSet(viewsets.ViewSet):
    pass


class NotificationViewSet(viewsets.ViewSet):
    pass