"""
NetSuite OAuth connect/callback views.

View responsibilities only: authenticate (connect) or not (callback —
see NetSuiteConnectionService.handle_callback docstring for why),
validate request shape, call NetSuiteConnectionService, return a
response. No NetSuite HTTP calls or token handling happen here.
"""

from django.conf import settings
from django.shortcuts import redirect
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from common.utils.response import success_response
from netsuite.exceptions import NetSuiteAuthorizationDeniedException
from netsuite.serializers import NetSuiteCallbackSerializer
from netsuite.services import NetSuiteConnectionService, NetSuiteDataService


class NetSuiteConnectView(APIView):
    """
    GET /api/v1/netsuite/connect/

    Returns the NetSuite OAuth authorization URL for the logged-in user.
    The frontend redirects the browser to this URL itself; ERP Pulse
    never initiates the redirect server-side, since the user must
    interact with NetSuite's own login/consent screen.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        authorization_url = NetSuiteConnectionService().get_authorization_url(
            user=request.user
        )

        return success_response(
            message='NetSuite authorization URL generated.',
            data={'authorization_url': authorization_url},
        )


class NetSuiteCallbackView(APIView):
    """
    GET /api/v1/netsuite/callback/

    Receives NetSuite's redirect after the user approves or denies
    access. This request comes directly from the user's browser being
    redirected by NetSuite — it carries no JWT — so the user is
    identified from the signed `state` parameter instead
    (see netsuite/oauth.py:resolve_user_id_from_state). On success,
    redirects the browser back to the frontend rather than returning
    JSON, since a human — not an API client — lands on this URL.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        serializer = NetSuiteCallbackSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data

        if params.get('error'):
            raise NetSuiteAuthorizationDeniedException(
                'NetSuite authorization was not granted.'
            )

        if not params.get('code'):
            raise NetSuiteAuthorizationDeniedException(
                'NetSuite did not return an authorization code.'
            )

        NetSuiteConnectionService().handle_callback(
            code=params['code'], state=params['state']
        )

        return redirect(f'{settings.FRONTEND_URL}/settings/integrations?netsuite=connected')


class NetSuiteCustomersView(APIView):
    """
    GET /api/v1/netsuite/customers/

    First real (non-OAuth) NetSuite data endpoint: proves the stored
    access token actually works by calling NetSuite's REST Record API
    for the logged-in user's connected account and returning it as-is.
    No request body to validate (parameterless GET), so there's no input
    serializer step — NetSuite's own JSON is the response, unmodified,
    per this task's "Return JSON. Nothing else."

    No local storage/sync/mapping here — that's explicitly a later task
    (NETSUITE_CONTEXT.md's Sync/Mapper/Repository layers).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        customers = NetSuiteDataService().get_customers(user=request.user)

        return success_response(
            message='NetSuite customers fetched successfully.',
            data=customers,
        )


class NetSuiteEmployeesView(APIView):
    """
    GET /api/v1/netsuite/employees/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employees = NetSuiteDataService().get_employees(user=request.user)
        return success_response(
            message='NetSuite employees fetched successfully.',
            data=employees,
        )


class NetSuiteVendorsView(APIView):
    """
    GET /api/v1/netsuite/vendors/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendors = NetSuiteDataService().get_vendors(user=request.user)
        return success_response(
            message='NetSuite vendors fetched successfully.',
            data=vendors,
        )


class NetSuiteItemsView(APIView):
    """
    GET /api/v1/netsuite/items/
    Supports query parameter ?type= to specify the item subtype (e.g. inventoryItem).
    Defaults to inventoryItem if not provided.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        item_type = request.query_params.get('type', 'inventoryItem')
        
        try:
            items = NetSuiteDataService().get_items(user=request.user, item_type=item_type)
        except ValueError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(str(e))
            
        return success_response(
            message=f'NetSuite items ({item_type}) fetched successfully.',
            data=items,
        )

class NetSuiteSalesOrdersView(APIView):
    """
    GET /api/v1/netsuite/sales-orders/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sales_orders = NetSuiteDataService().get_sales_orders(user=request.user)
        return success_response(
            message='NetSuite sales orders fetched successfully.',
            data=sales_orders,
        )

class NetSuitePurchaseOrderView(APIView):
    """
    GET /api/v1/netsuite/purchase-orders/
    """

    permission_classes = [IsAuthenticated]

    def get(self,request):
        purchase_orders = NetSuiteDataService().get_purchase_orders(user=request.user)
        return success_response(
            message='NetSuite Purchase orders fetched successfully.',
            data=purchase_orders,
        )
    
class NetSuiteInvoicesView(APIView):
    """
    GET /api/v1/netsuite/invoices/
    """

    permission_classes = [IsAuthenticated]

    def get(self,request):
        invoices = NetSuiteDataService().get_invoices(user=request.user)
        return success_response(
            message='NetSuite Invoices fetched successfully.',
            data=invoices,
        )