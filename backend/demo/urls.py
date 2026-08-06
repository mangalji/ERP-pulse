from rest_framework.routers import DefaultRouter

from .views import DemoRequestViewSet

router = DefaultRouter()
router.register(r"", DemoRequestViewSet, basename="demo-request")

urlpatterns = router.urls
