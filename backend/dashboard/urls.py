from django.urls import path

from dashboard.views import (
    DashboardSummaryView,
    RecentInvoicesView,
    ExecutiveSummaryView,
    ExecutiveChartsView,
    ActivityFeedView,
)
urlpatterns = [
    path('summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('recent-invoices/', RecentInvoicesView.as_view(), name='dashboard-recent-invoices'),
    path('executive-summary/', ExecutiveSummaryView.as_view(), name='dashboard-executive-summary'),
    path('executive-charts/', ExecutiveChartsView.as_view(), name='dashboard-executive-charts'),
    path('activity-feed/', ActivityFeedView.as_view(), name='dashboard-activity-feed'),
]
