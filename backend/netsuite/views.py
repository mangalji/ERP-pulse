"""
NetSuite OAuth connect/callback views.

View responsibilities only: authenticate (connect) or not (callback —
see NetSuiteConnectionService.handle_callback docstring for why),
validate request shape, call NetSuiteConnectionService, return a
response. No NetSuite HTTP calls or token handling happen here.
"""

from django.conf import settings
from django.shortcuts import redirect
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from common.utils.response import success_response
from common.throttles import NetSuiteSyncThrottle
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import NetSuiteAuthorizationDeniedException
from netsuite.serializers import (
    NetSuiteCallbackSerializer, 
    NetSuiteConnectionCreateSerializer,
    NetSuiteConnectionListSerializer,
    NetSuiteConnectionRenameSerializer,
    NetSuiteConnectionSwitchSerializer)
from netsuite.services import NetSuiteConnectionService, NetSuiteDataService


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

        return redirect(
    f'{settings.FRONTEND_URL}/settings?netsuite=connected'
)


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
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request):
        customers = NetSuiteDataService().get_customers(user=request.user)

        return success_response(
            message='NetSuite customers fetched successfully.',
            data=customers,
        )


class NetSuiteCustomerDetailView(APIView):
    """
    GET /api/v1/netsuite/customers/<record_id>/

    Reuses the generic NetSuiteDataService.get_record() — no per-resource
    service method needed for a straight pass-through single-record read.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        customer = NetSuiteDataService().get_record(
            record_type=NetSuiteRecordType.CUSTOMER, record_id=record_id, user=request.user,
        )
        return success_response(
            message='NetSuite customer fetched successfully.',
            data=customer,
        )


class NetSuiteEmployeesView(APIView):
    """
    GET /api/v1/netsuite/employees/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request):
        employees = NetSuiteDataService().get_employees(user=request.user)
        return success_response(
            message='NetSuite employees fetched successfully.',
            data=employees,
        )


class NetSuiteEmployeeDetailView(APIView):
    """
    GET /api/v1/netsuite/employees/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        employee = NetSuiteDataService().get_record(
            record_type=NetSuiteRecordType.EMPLOYEE, record_id=record_id, user=request.user,
        )
        return success_response(
            message='NetSuite employee fetched successfully.',
            data=employee,
        )


class NetSuiteVendorsView(APIView):
    """
    GET /api/v1/netsuite/vendors/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request):
        vendors = NetSuiteDataService().get_vendors(user=request.user)
        return success_response(
            message='NetSuite vendors fetched successfully.',
            data=vendors,
        )


class NetSuiteVendorDetailView(APIView):
    """
    GET /api/v1/netsuite/vendors/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        vendor = NetSuiteDataService().get_record(
            record_type=NetSuiteRecordType.VENDOR, record_id=record_id, user=request.user,
        )
        return success_response(
            message='NetSuite vendor fetched successfully.',
            data=vendor,
        )


class NetSuiteItemsView(APIView):
    """
    GET /api/v1/netsuite/items/
    Supports query parameter ?type= to specify the item subtype (e.g. inventoryItem).
    Defaults to inventoryItem if not provided.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request):
        item_type = request.query_params.get('type', 'inventoryItem')
        
        try:
            items = NetSuiteDataService().get_items(user=request.user, item_type=item_type)
        except ValueError as e:
            raise ValidationError(str(e))
            
        return success_response(
            message=f'NetSuite items ({item_type}) fetched successfully.',
            data=items,
        )


class NetSuiteItemDetailView(APIView):
    """
    GET /api/v1/netsuite/items/<record_id>/
    Same ?type= convention as NetSuiteItemsView, since NetSuite requires
    the specific item subtype in the path — defaults to inventoryItem.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        item_type = request.query_params.get('type', NetSuiteRecordType.INVENTORY_ITEM)

        if not NetSuiteRecordType.is_valid(item_type):
            raise ValidationError(f'Invalid NetSuite item type: {item_type}')

        item = NetSuiteDataService().get_record(
            record_type=item_type, record_id=record_id, user=request.user,
        )
        return success_response(
            message=f'NetSuite item ({item_type}) fetched successfully.',
            data=item,
        )

class NetSuiteSalesOrdersView(APIView):
    """
    GET /api/v1/netsuite/sales-orders/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request):
        sales_orders = NetSuiteDataService().get_sales_orders(user=request.user)
        return success_response(
            message='NetSuite sales orders fetched successfully.',
            data=sales_orders,
        )


class NetSuiteSalesOrderDetailView(APIView):
    """
    GET /api/v1/netsuite/sales-orders/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        sales_order = NetSuiteDataService().get_record(
            record_type=NetSuiteRecordType.SALES_ORDER, record_id=record_id, user=request.user,
        )
        return success_response(
            message='NetSuite sales order fetched successfully.',
            data=sales_order,
        )

class NetSuitePurchaseOrderView(APIView):
    """
    GET /api/v1/netsuite/purchase-orders/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self,request):
        purchase_orders = NetSuiteDataService().get_purchase_orders(user=request.user)
        return success_response(
            message='NetSuite Purchase orders fetched successfully.',
            data=purchase_orders,
        )


class NetSuitePurchaseOrderDetailView(APIView):
    """
    GET /api/v1/netsuite/purchase-orders/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        purchase_order = NetSuiteDataService().get_record(
            record_type=NetSuiteRecordType.PURCHASE_ORDER, record_id=record_id, user=request.user,
        )
        return success_response(
            message='NetSuite purchase order fetched successfully.',
            data=purchase_order,
        )
    
class NetSuiteInvoicesView(APIView):
    """
    GET /api/v1/netsuite/invoices/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self,request):
        invoices = NetSuiteDataService().get_invoices(user=request.user)
        return success_response(
            message='NetSuite Invoices fetched successfully.',
            data=invoices,
        )


class NetSuiteInvoiceDetailView(APIView):
    """
    GET /api/v1/netsuite/invoices/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        invoice = NetSuiteDataService().get_record(
            record_type=NetSuiteRecordType.INVOICE, record_id=record_id, user=request.user,
        )
        return success_response(
            message='NetSuite invoice fetched successfully.',
            data=invoice,
        )
    
class NetSuiteConnectionListCreateView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self,request):
        service = NetSuiteConnectionService()
        connections = service.list_connections(user=request.user,)
        serializer = NetSuiteConnectionListSerializer(
            connections,many=True
        )

        return success_response(
            message="NetSuite connections fetched successfully.",
            data=serializer.data,
        )

    def post(self,request):
        serializer = NetSuiteConnectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = NetSuiteConnectionService().create_connection(
            user=request.user,**serializer.validated_data,
        )
        return success_response(
            message="Connection created successfully.",
            data={
                "connection":NetSuiteConnectionListSerializer(result["connection"]).data,
                "authorization_url":result["authorization_url"],
            },
        )

class NetSuiteConnectionDetailView(APIView):
    
    permission_classes = [IsAuthenticated]
    
    def patch(self,request,connection_id):
        serializer = NetSuiteConnectionRenameSerializer(
            data=request.data
        )    
        serializer.is_valid(raise_exception=True)
        connection = NetSuiteConnectionService().rename_connection(
            user=request.user,connection_id=connection_id,
            client_name=serializer.validated_data["client_name"],
        )
        return success_response(
            message="connections renamed successfully.",
            data=NetSuiteConnectionListSerializer(
                connection
            ).data,
        )

    def delete(self,request,connection_id):
        NetSuiteConnectionService().delete_connection(
            user=request.user,
            connection_id=connection_id,
            )
        return success_response(message="Connection deleted successfully.")

class NetSuiteConnectionSwitchView(APIView):
    
    permission_classes = [IsAuthenticated]

    def post(self,request,connection_id):   
        connection = NetSuiteConnectionService().switch_connection(
            user=request.user,
            connection_id=connection_id,
        )
        return success_response(
            message="Active connection switched successfully.",
            data=NetSuiteConnectionListSerializer(
                connection
            ).data,
        )