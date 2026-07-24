from django.urls import path

from monitoring.views import ApiUsageView, ErrorLogListView, HealthCheckView, ReadinessView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="monitoring-health"),
    path("readiness/", ReadinessView.as_view(), name="monitoring-readiness"),
    path("errors/", ErrorLogListView.as_view(), name="monitoring-errors"),
    path("api-usage/", ApiUsageView.as_view(), name="monitoring-api-usage"),
]
