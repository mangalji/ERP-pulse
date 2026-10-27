from django.urls import path

from transactions.views import TransactionsView, TransactionDetailView

urlpatterns = [
    path("", TransactionsView.as_view(), name="transactions"),
    path("<int:pk>/", TransactionDetailView.as_view(), name="transaction-detail"),
]
