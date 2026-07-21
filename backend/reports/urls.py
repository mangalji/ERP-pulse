from django.urls import path

from reports.views import SalesTrendView

urlpatterns = [
    path('sales-trend/', SalesTrendView.as_view(), name='reports-sales-trend'),
]