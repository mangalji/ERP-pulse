from django.urls import path

from dashboard.views import (
    ExecutiveSummaryView,
    ActivityFeedView,
)
urlpatterns = [
    path('executive-summary/', ExecutiveSummaryView.as_view(), name='dashboard-executive-summary'),
    path('activity-feed/', ActivityFeedView.as_view(), name='dashboard-activity-feed'),
]
