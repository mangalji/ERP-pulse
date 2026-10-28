from django.urls import path

from audit.views import CompanyActivityLogView


urlpatterns = [
    path("events/", CompanyActivityLogView.as_view(), name="company-activity-log"),
]
