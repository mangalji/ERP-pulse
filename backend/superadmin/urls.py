from django.urls import path, include
from rest_framework.routers import DefaultRouter

from superadmin.views import (
    CompanyPlanViewSet,
    CompanyViewSet,
    DashboardViewSet,
    EmployeeViewSet,
    PlanViewSet,
    SupportSessionViewSet,
)

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='superadmin-company')
router.register(r'plans', PlanViewSet, basename='superadmin-plan')
router.register(r'company-plans', CompanyPlanViewSet, basename='superadmin-company-plan')
router.register(r'support-sessions', SupportSessionViewSet, basename='superadmin-support-session')
router.register(r'employees', EmployeeViewSet, basename='superadmin-employee')
router.register(r'dashboard', DashboardViewSet, basename='superadmin-dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
