from django.urls import path, include
from rest_framework.routers import DefaultRouter

from superadmin.views import (
    CompanyModuleViewSet,
    CompanyPlanViewSet,
    CompanyViewSet,
    DashboardViewSet,
    EmployeeViewSet,
    ModuleViewSet,
    NotificationViewSet,
    PlanViewSet,
    SupportSessionViewSet,
)

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='superadmin-company')
router.register(r'plans', PlanViewSet, basename='superadmin-plan')
router.register(r'company-plans', CompanyPlanViewSet, basename='superadmin-company-plan')
router.register(r'support-sessions', SupportSessionViewSet, basename='superadmin-support-session')
router.register(r'modules', ModuleViewSet, basename='superadmin-module')
router.register(r'company-modules', CompanyModuleViewSet, basename='superadmin-company-module')
router.register(r'employees', EmployeeViewSet, basename='superadmin-employee')
router.register(r'dashboard', DashboardViewSet, basename='superadmin-dashboard')
router.register(r'notifications', NotificationViewSet, basename='superadmin-notification')

urlpatterns = [
    path('', include(router.urls)),
]
