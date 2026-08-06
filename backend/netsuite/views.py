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

from common.utils.pagination import paginated_response
from common.utils.response import success_response
from common.throttles import NetSuiteSyncThrottle
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import NetSuiteAuthorizationDeniedException
from netsuite.models import EmployeeConnection, NetSuiteConnection
from netsuite.serializers import (
    NetSuiteCallbackSerializer, 
    NetSuiteConnectionCreateSerializer,
    NetSuiteConnectionListSerializer,
    NetSuiteConnectionRenameSerializer,
    NetSuiteConnectionSwitchSerializer,
    EmployeeConnectionSerializer,
    AssignEmployeeSerializer,
)
from netsuite.services import NetSuiteConnectionService, NetSuiteDataService

def _validate_record_id(record_id: str) -> None:
    """
    NetSuite internal record IDs (REST Record API) are always numeric
    strings. record_id comes straight from the URL path (<str:record_id>,
    which accepts any non-slash string) with nothing else validating its
    shape before this — reject non-numeric values here with a clean 400
    instead of forwarding arbitrary path segments into a live NetSuite
    API call.
    """
    if not record_id.isdigit():
        raise ValidationError({'record_id': 'record_id must be numeric.'})

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
        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        customers = NetSuiteDataService().list_customers(user=request.user, offset=offset, limit=limit)
        items = customers.get('items', [])
        total = customers.get('totalResults', len(items))

        return paginated_response(
            message='NetSuite customers fetched successfully.',
            results=items,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
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
        _validate_record_id(record_id)
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
        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        employees = NetSuiteDataService().list_employees(user=request.user, offset=offset, limit=limit)
        items = employees.get('items', [])
        total = employees.get('totalResults', len(items))

        return paginated_response(
            message='NetSuite employees fetched successfully.',
            results=items,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
        )


class NetSuiteEmployeeDetailView(APIView):
    """
    GET /api/v1/netsuite/employees/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        _validate_record_id(record_id)
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
        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        vendors = NetSuiteDataService().list_vendors(user=request.user, offset=offset, limit=limit)
        items = vendors.get('items', [])
        total = vendors.get('totalResults', len(items))

        return paginated_response(
            message='NetSuite vendors fetched successfully.',
            results=items,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
        )


class NetSuiteVendorDetailView(APIView):
    """
    GET /api/v1/netsuite/vendors/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        _validate_record_id(record_id)
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
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        try:
            if item_type == NetSuiteRecordType.INVENTORY_ITEM:
                items = NetSuiteDataService().list_inventory_items(user=request.user, offset=offset, limit=limit)
            else:
                items = NetSuiteDataService().get_items(user=request.user, item_type=item_type, offset=offset, limit=limit)
        except ValueError as e:
            raise ValidationError(str(e))

        items_list = items.get('items', [])
        total = items.get('totalResults', len(items_list))

        return paginated_response(
            message=f'NetSuite items ({item_type}) fetched successfully.',
            results=items_list,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
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
        _validate_record_id(record_id)
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
        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        sales_orders = NetSuiteDataService().list_sales_orders(user=request.user, offset=offset, limit=limit)
        items = sales_orders.get('items', [])
        total = sales_orders.get('totalResults', len(items))

        return paginated_response(
            message='NetSuite sales orders fetched successfully.',
            results=items,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
        )


class NetSuiteSalesOrderDetailView(APIView):
    """
    GET /api/v1/netsuite/sales-orders/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        _validate_record_id(record_id)
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
        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        purchase_orders = NetSuiteDataService().list_purchase_orders(user=request.user, offset=offset, limit=limit)
        items = purchase_orders.get('items', [])
        total = purchase_orders.get('totalResults', len(items))

        return paginated_response(
            message='NetSuite Purchase orders fetched successfully.',
            results=items,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
        )


class NetSuitePurchaseOrderDetailView(APIView):
    """
    GET /api/v1/netsuite/purchase-orders/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        _validate_record_id(record_id)
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
        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        invoices = NetSuiteDataService().list_invoices(user=request.user, offset=offset, limit=limit)
        items = invoices.get('items', [])
        total = invoices.get('totalResults', len(items))

        return paginated_response(
            message='NetSuite Invoices fetched successfully.',
            results=items,
            count=total,
            request=request,
            offset=offset,
            limit=limit,
        )


class NetSuiteInvoiceDetailView(APIView):
    """
    GET /api/v1/netsuite/invoices/<record_id>/
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request, record_id):
        _validate_record_id(record_id)
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
        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        service = NetSuiteConnectionService()
        connections = service.list_connections(user=request.user,)
        count = len(connections)
        page = connections[offset:offset + limit]
        serializer = NetSuiteConnectionListSerializer(page, many=True)

        return paginated_response(
            message="NetSuite connections fetched successfully.",
            results=serializer.data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
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


class NetSuiteCompanyConnectionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        connections = NetSuiteConnectionService().get_company_connections(company_id=company.id)
        serializer = NetSuiteConnectionListSerializer(connections, many=True)
        return success_response(
            message='Company connections fetched successfully.',
            data=serializer.data,
        )

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = NetSuiteConnectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = NetSuiteConnectionService().create_connection(
                user=request.user,
                company_id=company.id,
                **serializer.validated_data,
            )
            return success_response(
                message="Connection created successfully.",
                data={
                    "connection": NetSuiteConnectionListSerializer(result["connection"]).data,
                    "authorization_url": result["authorization_url"],
                },
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class NetSuiteAssignEmployeeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, connection_id):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            connection = NetSuiteConnection.objects.get(pk=connection_id, company=company)
        except NetSuiteConnection.DoesNotExist:
            return Response({'detail': 'Connection not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AssignEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assignment = NetSuiteConnectionService().assign_employee(
                connection_id=connection_id,
                employee_id=serializer.validated_data['employee_id'],
            )
            return success_response(
                message='Employee assigned successfully.',
                data=EmployeeConnectionSerializer(assignment).data,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'detail': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)


class NetSuiteRemoveEmployeeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, connection_id, employee_id):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            connection = NetSuiteConnection.objects.get(pk=connection_id, company=company)
        except NetSuiteConnection.DoesNotExist:
            return Response({'detail': 'Connection not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            NetSuiteConnectionService().remove_employee(
                connection_id=connection_id,
                employee_id=employee_id,
            )
            return success_response(message='Employee removed successfully.')
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class NetSuiteTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, connection_id):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            connection = NetSuiteConnection.objects.get(pk=connection_id, company=company)
        except NetSuiteConnection.DoesNotExist:
            return Response({'detail': 'Connection not found.'}, status=status.HTTP_404_NOT_FOUND)

        result = NetSuiteConnectionService().test_connection(connection_id=connection_id)
        status_code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)


class NetSuiteMyConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connection = NetSuiteConnectionService().get_employee_connection(employee_id=request.user.id)
        if not connection:
            return Response({'detail': 'No NetSuite connection assigned.'}, status=status.HTTP_404_NOT_FOUND)

        return success_response(
            message='Your NetSuite connection fetched successfully.',
            data=NetSuiteConnectionListSerializer(connection).data,
        )