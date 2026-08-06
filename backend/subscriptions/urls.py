from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SubscriptionViewSet, ModuleManagementViewSet

router = DefaultRouter()
router.register(r'', SubscriptionViewSet, basename='subscription')

urlpatterns = [
    path('modules/', ModuleManagementViewSet.as_view({'get': 'list_modules'})),
    path('modules/enable/', ModuleManagementViewSet.as_view({'post': 'enable'})),
    path('modules/disable/', ModuleManagementViewSet.as_view({'post': 'disable'})),
    path('', include(router.urls)),
]
