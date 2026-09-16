from django.urls import path, include
from rest_framework.routers import DefaultRouter

from superadmin.views import (
    CompanyViewSet,
    DashboardViewSet,
    EmployeeViewSet,
    PlanViewSet,
)

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='superadmin-company')
router.register(r'plans', PlanViewSet, basename='superadmin-plan')
router.register(r'employees', EmployeeViewSet, basename='superadmin-employee')
router.register(r'dashboard', DashboardViewSet, basename='superadmin-dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
