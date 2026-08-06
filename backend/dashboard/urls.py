from django.urls import path

from dashboard.views import (
    DashboardSummaryView,
    RecentCustomersView,
    RecentInvoicesView,
    RecentSalesOrdersView,
    ExecutiveSummaryView,
    ExecutiveChartsView,
    ActivityFeedView,
)

urlpatterns = [
    path('summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('recent-sales-orders/', RecentSalesOrdersView.as_view(), name='dashboard-recent-sales-orders'),
    path('recent-invoices/', RecentInvoicesView.as_view(), name='dashboard-recent-invoices'),
    path('recent-customers/', RecentCustomersView.as_view(), name='dashboard-recent-customers'),
    path('executive-summary/', ExecutiveSummaryView.as_view(), name='dashboard-executive-summary'),
    path('executive-charts/', ExecutiveChartsView.as_view(), name='dashboard-executive-charts'),
    path('activity-feed/', ActivityFeedView.as_view(), name='dashboard-activity-feed'),
]
