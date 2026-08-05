from django.urls import path

from bi.views import (
    AlertsView,
    CustomerView,
    FinanceView,
    HealthView,
    InsightsView,
    InventoryView,
    PurchaseView,
    SalesView,
    SummaryView,
)

urlpatterns = [
    path('summary/', SummaryView.as_view(), name='bi-summary'),
    path('sales/', SalesView.as_view(), name='bi-sales'),
    path('purchase/', PurchaseView.as_view(), name='bi-purchase'),
    path('customer/', CustomerView.as_view(), name='bi-customer'),
    path('inventory/', InventoryView.as_view(), name='bi-inventory'),
    path('finance/', FinanceView.as_view(), name='bi-finance'),
    path('alerts/', AlertsView.as_view(), name='bi-alerts'),
    path('insights/', InsightsView.as_view(), name='bi-insights'),
    path('health/', HealthView.as_view(), name='bi-health'),
]
