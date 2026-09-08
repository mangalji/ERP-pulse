from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.throttles import NetSuiteSyncThrottle
from common.utils.pagination import paginated_response
from netsuite.services import NetSuiteDataService


TRANSACTION_VIEW_METHODS = {
    "sales_orders": "list_sales_orders",
    "sales_invoices": "list_invoices",
    "cash_sales": "list_cash_sales",
    "purchase_orders": "list_purchase_orders",
    "vendor_bills": "list_vendor_bills",
    "vendor_payments": "list_vendor_payments",
}


class NetSuiteTransactionsView(APIView):
    """
    GET /api/v1/netsuite/transactions/?view=<transaction-menu-key>

    One endpoint backs the single Transactions page. The DB-driven menu
    supplies the `view` key; the backend resolves that key to an existing
    NetSuiteDataService method and always uses the authenticated user's
    current authorized NetSuite connection.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request):
        view = (request.query_params.get("view") or "").strip()
        if view not in TRANSACTION_VIEW_METHODS:
            raise ValidationError({
                "view": [
                    "Unsupported transaction view.",
                    {"supported": list(TRANSACTION_VIEW_METHODS.keys())},
                ]
            })

        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
            limit = int(request.query_params.get("limit", 20))
        except (TypeError, ValueError):
            raise ValidationError({"offset": "offset and limit must be integers."})

        limit = max(1, min(limit, 100))

        service = NetSuiteDataService()
        method = getattr(service, TRANSACTION_VIEW_METHODS[view])
        payload = method(user=request.user, limit=limit, offset=offset)
        items = payload.get("items", [])
        total = payload.get("totalResults", len(items))

        return paginated_response(
            message="NetSuite transactions fetched successfully.",
            results=items,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
        )
