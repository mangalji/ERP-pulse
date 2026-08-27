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
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
from netsuite.repositories import NetSuiteConnectionRepository
from common.utils.pagination import paginated_response
from common.utils.response import success_response
from common.throttles import NetSuiteSyncThrottle
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import NetSuiteAuthorizationDeniedException, NetSuiteConnectionNotFoundException, NetSuiteRecordFetchException
from celery.result import AsyncResult
from netsuite.models import EmployeeConnection, NetSuiteConnection, NetSuiteCustomField, NetSuiteOCRPosting
from accounts.models import User
from netsuite.serializers import (
    NetSuiteCallbackSerializer, 
    NetSuiteConnectionCreateSerializer,
    NetSuiteConnectionListSerializer,
    NetSuiteConnectionRenameSerializer,
    NetSuiteConnectionSwitchSerializer,
    EmployeeConnectionSerializer,
    AssignEmployeeSerializer,
    NetSuiteFieldCatalogueSerializer,
    MappingSuggestionSerializer,
    MappingSuggestionRequestSerializer,
    SaveMappingRequestSerializer,
    OCRNetSuiteFieldMappingSerializer,
    OCRValidationResultSerializer,
    ValidateDocumentRequestSerializer,
    CheckOCRReferencesRequestSerializer,
    CreateCustomFieldRequestSerializer,
    NetSuiteCustomFieldSerializer,
    NetSuiteConnectionTestSerializer,
)
from netsuite.services import (
    NetSuiteConnectionService,
    NetSuiteDataService,
    NetSuiteVendorBillPostingService,
    NetSuiteFieldMappingService,
    NetSuiteValidationService,
    NetSuiteCustomFieldService,
)
from ocr.models import OCRDocument, OCRDocumentVersion, OCRNetSuiteFieldMapping, OCRValidationResult
from tenancy.services import company_lifecycle_service
from netsuite.tasks import (
    BATCH_MAX_DOCUMENTS,
    _store_batch_job_owner,
    get_batch_job_owner,
    batch_validate_documents_task,
    batch_post_documents_task,
)

logger = logging.getLogger(__name__)


def _is_company_admin(user) -> bool:
    try:
        if getattr(user, "is_superuser", False):
            return True

        if not getattr(user, "company_id", None):
            return False

        return user.user_roles.filter(
            role__name__iexact="Company Admin",
        ).exists()

    except Exception:
        logger.exception(
            "Failed to determine Company Admin role — user=%s",
            getattr(user, "id", None),
        )
        return False

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

        if params.get("error"):
            NetSuiteConnectionService().mark_oauth_failed(
                state=params["state"],
                error_message=(
                    params.get("error_description")
                    or params.get("error")
                    or "NetSuite authorization was not granted."
                ),
            )
        
            return redirect(
                f"{settings.FRONTEND_URL}/settings?netsuite=failed"
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
        if not _is_company_admin(request.user):
            raise PermissionDenied(
            "Only Company Admin can view NetSuite connection management."
            )
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
        if not _is_company_admin(request.user):
            raise PermissionDenied(
                "Only Company Admin can create NetSuite connections."
            )
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
        if not _is_company_admin(request.user):
            raise PermissionDenied(
                "Only Company Admin can manage NetSuite connections."
            )
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
        if not _is_company_admin(request.user):
            raise PermissionDenied(
                "Only Company Admin can create NetSuite connections."
            )
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
        if not _is_company_admin(request.user):
            raise PermissionDenied(
                "Only Company Admin can assign NetSuite access."
            )
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
                user=request.user,
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
        if not _is_company_admin(request.user):
            raise PermissionDenied(
                "Only Company Admin can assign NetSuite access."
            )
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            connection = NetSuiteConnection.objects.get(pk=connection_id, company=company)
        except NetSuiteConnection.DoesNotExist:
            return Response({'detail': 'Connection not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            NetSuiteConnectionService().remove_employee(
                user=request.user,
                connection_id=connection_id,
                employee_id=employee_id,
            )
            return success_response(message='Employee removed successfully.')
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

class NetSuiteCheckOCRReferencesView(APIView):
    """
    Lightweight preflight check for Vendor + Item master data.

    This does NOT create OCRValidationResult.
    It only checks whether Vendor and Item records exist
    in the explicitly selected NetSuite connection.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckOCRReferencesRequestSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        document_id = serializer.validated_data['document_id']
        connection_id = serializer.validated_data['connection_id']

        try:
            service = NetSuiteValidationService()

            result = service.check_references(
                document_id=document_id,
                connection_id=connection_id,
                user=request.user,
            )

            return success_response(
                message="NetSuite reference check completed.",
                data=result,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class NetSuiteTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, connection_id):
        if not _is_company_admin(request.user):
            raise PermissionDenied(
                "Only Company Admin can assign NetSuite access."
            )
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
        # connection = NetSuiteConnectionService().get_employee_connection(employee_id=request.user.id)
        connection = NetSuiteConnectionRepository().get_for_user(request.user)
        if not connection:
            return Response({'detail': 'No NetSuite connection assigned.'}, status=status.HTTP_404_NOT_FOUND)

        return success_response(
            message='Your NetSuite connection fetched successfully.',
            data=NetSuiteConnectionListSerializer(connection).data,
        )

class NetSuiteMyConnectionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        service = NetSuiteConnectionService()

        connections = service.list_available_for_user(
            request.user,
        )

        current = service.get_current_connection(
            user=request.user,
        )

        current_id = (
            str(current.id)
            if current
            else None
        )

        data = {
            "connections": NetSuiteConnectionListSerializer(
                connections,
                many=True,
            ).data,
            "current_connection_id": current_id,
        }

        return success_response(
            message="Available NetSuite connections fetched successfully.",
            data=data,
        )



class NetSuitePostOCRVendorBillView(APIView):
    """Post a saved/reviewed OCR document as a NetSuite Vendor Bill."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            document_id = request.data.get("document_id")
            connection_id = request.data.get("connection_id")
            if not document_id:
                return Response(
                    {"detail": "document_id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = NetSuiteVendorBillPostingService().post_vendor_bill(
                document_id=document_id,
                user=request.user,
                connection_id=connection_id,
            )

            return success_response(
                message="Vendor Bill created in NetSuite.",
                data=result,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected OCR-to-NetSuite Vendor Bill failure — user=%s",
                getattr(request.user, "id", None),
            )
            return Response(
                {
                    "detail": (
                        "The Vendor Bill could not be created in NetSuite. "
                        "Please check the OCR values and NetSuite master-data sync."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NetSuiteFieldCatalogueView(APIView):
    """Return available NetSuite fields for a record type."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connection_id = request.query_params.get('connection_id')
        record_type = request.query_params.get('record_type', 'vendorBill')
        force_refresh = str(
            request.query_params.get('force_refresh', 'false')
        ).strip().lower() in {'1', 'true', 'yes', 'on'}

        if not connection_id:
            return Response(
                {"detail": "connection_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            company = getattr(request.user, "company", None)
            if company is None:
                return Response(
                    {"detail": "User is not associated with a company."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            service = NetSuiteFieldMappingService()
            catalogue = service.get_field_catalogue(
                company=company,
                connection_id=connection_id,
                record_type=record_type,
                force_refresh=force_refresh,
            )
            serializer = NetSuiteFieldCatalogueSerializer(catalogue)
            return success_response(
                message=(
                    'NetSuite Vendor Bill field catalogue refreshed successfully.'
                    if force_refresh and catalogue.get('source') == 'netsuite'
                    else 'NetSuite field catalogue loaded successfully.'
                ),
                data=serializer.data,
            )
        except NetSuiteConnectionNotFoundException as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.exception(
                "Failed to load NetSuite field catalogue — user=%s",
                getattr(request.user, "id", None),
            )
            return success_response(
                message='NetSuite field catalogue is temporarily unavailable.',
                data={
                    'record_type': record_type,
                    'fields': {'body': [], 'column': []},
                    'custom_fields': [],
                    'fetched_at': None,
                    'source': 'error',
                    'stale': False,
                    'available': False,
                    'error': str(exc)[:500],
                },
            )


class NetSuiteSuggestMappingView(APIView):
    """Return safe field-mapping suggestions from the authorized Vendor Bill catalogue."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MappingSuggestionRequestSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        company = getattr(request.user, "company", None)
        if company is None:
            return Response(
                {"detail": "User is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = NetSuiteFieldMappingService()
            suggestions = service.suggest_mappings(
                company=company,
                connection_id=payload["connection_id"],
                record_type=payload["record_type"],
                source_fields=payload["source_fields"],
            )
            output = MappingSuggestionSerializer(
                suggestions,
                many=True,
            ).data
            return success_response(
                message="NetSuite field mapping suggestions fetched successfully.",
                data=output,
            )
        except NetSuiteConnectionNotFoundException as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Failed to generate mapping suggestions — user=%s",
                getattr(request.user, "id", None),
            )
            return success_response(
                message='Field mapping suggestions are temporarily unavailable.',
                data=[],
            )


class NetSuiteFieldMappingListCreateView(APIView):
    """List or save OCR → NetSuite Vendor Bill field mappings."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connection_id = request.query_params.get("connection_id")
        record_type = request.query_params.get("record_type", "vendorBill")

        if not connection_id:
            return Response(
                {"detail": "connection_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = getattr(request.user, "company", None)
        if company is None:
            return Response(
                {"detail": "User is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = NetSuiteFieldMappingService()
            mappings = service.get_mappings(
                company=company,
                connection_id=connection_id,
                record_type=record_type,
            )
            return success_response(
                message="Saved NetSuite field mappings fetched successfully.",
                data=OCRNetSuiteFieldMappingSerializer(
                    mappings,
                    many=True,
                ).data,
            )
        except NetSuiteConnectionNotFoundException as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Failed to load field mappings — user=%s",
                getattr(request.user, "id", None),
            )
            return success_response(
                message='No saved field mappings are currently available.',
                data=[],
            )

    def post(self, request):
        serializer = SaveMappingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        company = getattr(request.user, "company", None)
        if company is None:
            return Response(
                {"detail": "User is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = NetSuiteFieldMappingService()
            saved = service.save_mappings(
                company=company,
                connection_id=payload["connection_id"],
                record_type=payload["record_type"],
                mappings=payload["mappings"],
            )
            return success_response(
                data=OCRNetSuiteFieldMappingSerializer(
                    saved,
                    many=True,
                ).data,
                message="Mappings saved successfully.",
            )
        except NetSuiteConnectionNotFoundException as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Failed to save field mappings — user=%s",
                getattr(request.user, "id", None),
            )
            return Response(
                {"detail": "Failed to save field mappings."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NetSuiteValidateDocumentView(APIView):
    """Validate an OCR document against NetSuite reference data."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def post(self, request):
        serializer = ValidateDocumentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_id = serializer.validated_data['document_id']
        connection_id = serializer.validated_data['connection_id']

        try:
            service = NetSuiteValidationService()
            result = service.validate_document(
                document_id=document_id,
                connection_id=connection_id,
                user=request.user,
            )
            return success_response(
                message='NetSuite document validation completed.',
                data=result,
            )
        except NetSuiteRecordFetchException as exc:
            logger.exception(
                "NetSuite provider validation failed — document=%s connection=%s user=%s",
                document_id,
                connection_id,
                getattr(request.user, "id", None),
            )
            return Response(
                {
                    "detail": str(exc),
                    "code": "NETSUITE_VALIDATION_UNAVAILABLE",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Document validation failed — document=%s user=%s",
                document_id,
                getattr(request.user, "id", None),
            )
            return Response(
                {"detail": "Document validation failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NetSuiteCreateCustomFieldView(APIView):
    """Create a NetSuite custom field for an OCR custom field."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateCustomFieldRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        company = getattr(request.user, 'company', None)
        if company is None:
            return Response(
                {"detail": "User is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection_id = request.data.get('connection_id')
        if not connection_id:
            return Response(
                {"detail": "connection_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = NetSuiteCustomFieldService()
            custom_field = service.create_custom_field(
                company=company,
                connection_id=connection_id,
                record_type=payload['record_type'],
                scope=payload['scope'],
                field_label=payload['field_label'],
                datatype=payload['datatype'],
                source_field_key=payload['source_field_key'],
                source_field_label=payload['source_field_label'],
            )
            data = NetSuiteCustomFieldSerializer(custom_field).data
            return success_response(data=data, message="Custom field created successfully.")
        except NetSuiteConnectionNotFoundException as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.exception(
                "Failed to create NetSuite custom field — user=%s",
                getattr(request.user, "id", None),
            )
            return Response(
                {"detail": "Failed to create NetSuite custom field."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class NetSuiteBatchBaseView(APIView):
    """Shared validation for large OCR validation/posting jobs."""
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _parse_document_ids(request):
        document_ids = request.data.get("document_ids")

        if not isinstance(document_ids, list) or not document_ids:
            raise ValidationError(
                {"document_ids": "document_ids must be a non-empty list."}
            )

        if len(document_ids) > BATCH_MAX_DOCUMENTS:
            raise ValidationError(
                {
                    "document_ids": (
                        f"A maximum of {BATCH_MAX_DOCUMENTS} documents "
                        "can be processed per batch."
                    )
                }
            )

        normalized = []
        for value in document_ids:
            try:
                normalized.append(str(value))
            except Exception:
                raise ValidationError(
                    {"document_ids": "Every document ID must be valid."}
                )

        return normalized

    @staticmethod
    def _visible_document_ids(request, document_ids):
        company_id = getattr(request.user, "company_id", None)
        if not company_id:
            raise ValidationError(
                {"detail": "User is not associated with a company."}
            )

        queryset = OCRDocument.objects.filter(
            pk__in=document_ids,
            company_id=company_id,
        )

        if not _is_company_admin(request.user):
            queryset = queryset.filter(user=request.user)

        visible = {str(pk) for pk in queryset.values_list("pk", flat=True)}
        missing = [doc_id for doc_id in document_ids if doc_id not in visible]

        if missing:
            raise PermissionDenied(
                "One or more selected documents are not accessible."
            )

        return document_ids


class NetSuiteBatchValidateView(NetSuiteBatchBaseView):
    """Queue up to 100 OCR document validations in Celery."""

    def post(self, request):
        document_ids = self._parse_document_ids(request)
        document_ids = self._visible_document_ids(request, document_ids)
        connection_id = request.data.get("connection_id")

        if not connection_id:
            return Response(
                {
                    "detail": "connection_id is required for batch validation."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        task = batch_validate_documents_task.delay(
            document_ids,
            str(request.user.id),
            str(connection_id)
        )
        _store_batch_job_owner(
            task.id,
            str(request.user.id),
            "validate",
        )

        return success_response(
            message="Batch validation queued successfully.",
            data={
                "job_id": task.id,
                "action": "validate",
                "total": len(document_ids),
                "status": "PENDING",
            },
        )


class NetSuiteBatchPostView(NetSuiteBatchBaseView):
    """Queue up to 100 OCR document postings in Celery."""

    def post(self, request):
        document_ids = self._parse_document_ids(request)
        document_ids = self._visible_document_ids(request, document_ids)

        connection_id = request.data.get("connection_id")

        task = batch_post_documents_task.delay(
            document_ids,
            str(request.user.id),
            str(connection_id) if connection_id else None,
        )
        _store_batch_job_owner(
            task.id,
            str(request.user.id),
            "post",
        )

        return success_response(
            message="Batch posting queued successfully.",
            data={
                "job_id": task.id,
                "action": "post",
                "total": len(document_ids),
                "status": "PENDING",
            },
        )


class NetSuiteBatchJobStatusView(APIView):
    """Return progress for an authorized Celery NetSuite batch job."""
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        owner = get_batch_job_owner(str(job_id))
        if owner is None:
            return Response(
                {"detail": "Batch job not found or expired."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if owner["user_id"] != str(request.user.id):
            raise PermissionDenied("You cannot access this batch job.")

        task_result = AsyncResult(str(job_id))
        meta = task_result.info if isinstance(task_result.info, dict) else {}

        data = {
            "job_id": str(job_id),
            "action": owner["action"],
            "status": task_result.status,
            "total": meta.get("total"),
            "completed": meta.get("completed", 0),
            "succeeded": meta.get("succeeded", 0),
            "failed": meta.get("failed", 0),
            "results": meta.get("results", []),
        }

        if task_result.successful():
            result = task_result.result if isinstance(task_result.result, dict) else {}
            data.update(
                {
                    "total": result.get("total", data["total"]),
                    "completed": result.get("completed", data["completed"]),
                    "succeeded": result.get("succeeded", data["succeeded"]),
                    "failed": result.get("failed", data["failed"]),
                    "results": result.get("results", []),
                }
            )
        elif task_result.failed():
            data["error"] = str(task_result.result)[:2000]

        return success_response(
            message="Batch job status retrieved successfully.",
            data=data)