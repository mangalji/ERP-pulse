from django.urls import path

from transactions.views import TransactionsView

urlpatterns = [
    path("", TransactionsView.as_view(), name="transactions"),
]
