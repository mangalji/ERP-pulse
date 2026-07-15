from django.urls import path

from netsuite.views import (
    NetSuiteCallbackView,
    NetSuiteConnectView,
    NetSuiteCustomersView,
    NetSuiteEmployeesView,
    NetSuiteItemsView,
    NetSuiteVendorsView,
    NetSuiteInvoicesView,
    NetSuitePurchaseOrderView,
    NetSuiteSalesOrdersView,
)

urlpatterns = [
    path('connect/', NetSuiteConnectView.as_view(), name='netsuite-connect'),
    path('callback/', NetSuiteCallbackView.as_view(), name='netsuite-callback'),
    path('customers/', NetSuiteCustomersView.as_view(), name='netsuite-customers'),
    path('employees/', NetSuiteEmployeesView.as_view(), name='netsuite-employees'),
    path('vendors/', NetSuiteVendorsView.as_view(), name='netsuite-vendors'),
    path('items/', NetSuiteItemsView.as_view(), name='netsuite-items'),
    path('sales-orders/', NetSuiteSalesOrdersView.as_view(), name='netsuite-sales-orders'),
    path('purchase-orders/', NetSuitePurchaseOrderView.as_view(), name='netsuite-purchase-orders'),
    path('invoices/', NetSuiteInvoicesView.as_view(), name='netsuite-invoices'),
]
