from django.urls import path

from netsuite.views import NetSuiteCallbackView, NetSuiteConnectView, NetSuiteCustomersView

urlpatterns = [
    path('connect/', NetSuiteConnectView.as_view(), name='netsuite-connect'),
    path('callback/', NetSuiteCallbackView.as_view(), name='netsuite-callback'),
    path('customers/', NetSuiteCustomersView.as_view(), name='netsuite-customers'),
]
