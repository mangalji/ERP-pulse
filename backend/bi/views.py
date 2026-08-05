"""
BI API views.

Thin views: authenticate the user, parse common filter params (preset,
start_date, end_date), delegate to the appropriate BI service, and return
the standard success envelope. No business logic lives here.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from bi.services import (
    AlertService,
    CustomerService,
    FinanceService,
    HealthService,
    InsightService,
    InventoryService,
    PurchaseService,
    SalesService,
    SummaryService,
)
from common.utils.response import success_response


class BaseBIView(APIView):
    """Shared filter parsing for all BI endpoints."""

    permission_classes = [IsAuthenticated]

    def filters(self, request) -> dict:
        return {
            'preset': request.query_params.get('preset'),
            'start_date': request.query_params.get('start_date'),
            'end_date': request.query_params.get('end_date'),
        }


class SummaryView(BaseBIView):
    """GET /api/v1/bi/summary/?preset=last_30_days"""

    def get(self, request):
        data = SummaryService().get_summary(user=request.user, **self.filters(request))
        return success_response(message='Executive summary fetched successfully.', data=data)


class SalesView(BaseBIView):
    """GET /api/v1/bi/sales/?preset=this_month"""

    def get(self, request):
        data = SalesService().get_sales(user=request.user, **self.filters(request))
        return success_response(message='Sales analytics fetched successfully.', data=data)


class PurchaseView(BaseBIView):
    """GET /api/v1/bi/purchase/?preset=last_30_days"""

    def get(self, request):
        data = PurchaseService().get_purchase(user=request.user, **self.filters(request))
        return success_response(message='Purchase analytics fetched successfully.', data=data)


class CustomerView(BaseBIView):
    """GET /api/v1/bi/customer/?preset=last_30_days"""

    def get(self, request):
        data = CustomerService().get_customers(user=request.user, **self.filters(request))
        return success_response(message='Customer analytics fetched successfully.', data=data)


class InventoryView(BaseBIView):
    """GET /api/v1/bi/inventory/?preset=last_30_days"""

    def get(self, request):
        data = InventoryService().get_inventory(user=request.user, **self.filters(request))
        return success_response(message='Inventory analytics fetched successfully.', data=data)


class FinanceView(BaseBIView):
    """GET /api/v1/bi/finance/?preset=last_30_days"""

    def get(self, request):
        data = FinanceService().get_finance(user=request.user, **self.filters(request))
        return success_response(message='Finance analytics fetched successfully.', data=data)


class AlertsView(BaseBIView):
    """GET /api/v1/bi/alerts/?preset=last_30_days"""

    def get(self, request):
        data = AlertService().get_alerts(user=request.user, **self.filters(request))
        return success_response(message='Executive alerts fetched successfully.', data=data)


class InsightsView(BaseBIView):
    """GET /api/v1/bi/insights/?preset=last_30_days — AI-generated executive insight."""

    def get(self, request):
        data = InsightService().get_insights(user=request.user, **self.filters(request))
        return success_response(message='Executive insights generated successfully.', data=data)


class HealthView(BaseBIView):
    """GET /api/v1/bi/health/ — executive system health."""

    def get(self, request):
        data = HealthService().get_health(user=request.user)
        return success_response(message='System health fetched successfully.', data=data)
