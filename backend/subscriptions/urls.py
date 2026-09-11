from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SubscriptionViewSet

router = DefaultRouter()
router.register(r'', SubscriptionViewSet, basename='subscription')

urlpatterns = [
    path('', include(router.urls)),
]
