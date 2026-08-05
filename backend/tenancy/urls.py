from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tenancy.views import (
    ClientMeView,
    ClientNotificationViewSet,
    ClientRoleListView,
    CompanyEmployeeViewSet,
    CompanySettingsView,
)

router = DefaultRouter()
router.register(r'employees', CompanyEmployeeViewSet, basename='client-employee')
router.register(r'notifications', ClientNotificationViewSet, basename='client-notification')

urlpatterns = [
    path('me/', ClientMeView.as_view(), name='client-me'),
    path('roles/', ClientRoleListView.as_view(), name='client-roles'),
    path('settings/', CompanySettingsView.as_view(), name='client-settings'),
    path('', include(router.urls)),
]
