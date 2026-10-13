"""
API views for NetSuite OAuth, connection management, data reads, and OCR workflows.

Views validate requests and delegate business logic to the NetSuite service layer.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
from netsuite.repositories import NetSuiteConnectionRepository
from common.pagination import paginated_response
from common.common_utils import success_response
from common.throttles import NetSuiteSyncThrottle
from netsuite.exceptions import (
    NetSuiteAuthorizationDeniedException, 
    NetSuiteConnectionNotFoundException, 
    NetSuiteRecordFetchException, 
    NetSuiteTokenExchangeException,
)
from ocr.ai.providers import AIProviderError
from netsuite.diagnostics_service import net_suite_diagnostics_service
from netsuite.models import NetSuiteConnection, NetSuiteBatchJob
from accounts.models import User
from netsuite.serializers import (
    NetSuiteCallbackSerializer, 
    NetSuiteConnectionCreateSerializer,
    NetSuiteConnectionListSerializer,
    NetSuiteConnectionRenameSerializer,
    EmployeeConnectionSerializer,
    AssignEmployeeSerializer,
    SaveMappingRequestSerializer,
    OCRNetSuiteFieldMappingSerializer,
    ValidateDocumentRequestSerializer,
)
from netsuite.services import (
    NetSuiteConnectionService,
    NetSuiteVendorBillPostingService,
    NetSuiteFieldMappingService,
    NetSuiteValidationService,
)
from netsuite.oauth import resolve_post_connect_redirect_url_from_state
from ocr.models import OCRDocument
from netsuite.jobs import create_job, dispatch_job, recover_jobs
from netsuite.tasks import BATCH_MAX_DOCUMENTS
logger = logging.getLogger(__name__)


def _is_company_admin(user) -> bool:
    try:
        if getattr(user, "is_superuser", False):
            return True

        if not getattr(user, "company_id", None):
            return False

        role = getattr(user, "role", None)

        return role is not None and role.name.lower() == "company admin"

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
                f"{settings.FRONTEND_URL.rstrip('/')}/#/settings?netsuite=failed"
            )

        if not params.get('code'):
            raise NetSuiteAuthorizationDeniedException(
                'NetSuite did not return an authorization code.'
            )
        post_connect_redirect_url = resolve_post_connect_redirect_url_from_state(
            params['state']
        )
        NetSuiteConnectionService().handle_callback(
            code=params['code'], state=params['state']
        )

        return redirect(
            post_connect_redirect_url or
            f'{settings.FRONTEND_URL.rstrip('/')}/#/app/integrations/netsuite?netsuite=connected'
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

        except NetSuiteTokenExchangeException:
            return _reauth_required_response()
        except NetSuiteRecordFetchException as exc:
            logger.exception(
                "NetSuite verification unavailable during Vendor Bill posting.",
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


def _reauth_required_response(http_status=status.HTTP_401_UNAUTHORIZED):
    """Single shape for "NetSuite connection needs reconnecting"."""
    return Response(
        {
            "detail": (
                "Your NetSuite connection needs to be reconnected. "
                "The authorization has expired or is no longer valid. "
                "Please reconnect your NetSuite account and try again."
            ),
            "code": "NETSUITE_REAUTH_REQUIRED",
        },
        status=http_status,
    )


class NetSuiteReconnectView(APIView):
    """
    POST /company/connections/<id>/reconnect/
    Returns a fresh NetSuite authorize URL for an existing connection.
    Company Admin only (they own the client credentials / consent).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, connection_id):
        if not _is_company_admin(request.user):
            raise PermissionDenied(
                "Only Company Admin can reconnect NetSuite."
            )
        try:
            url = NetSuiteConnectionService().get_reconnect_url(
                user=request.user,
                connection_id=connection_id,
            )
        except NetSuiteConnectionNotFoundException as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        return success_response(
            message="Reconnect URL generated.",
            data={"authorization_url": url},
        )


class NetSuiteFieldCatalogueView(APIView):
    """Read saved catalogue; refresh only through an admin action."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # GET is strictly read-only, even if a legacy client sends
        # ?force_refresh=true.
        return self._serve_catalogue(
            request,
            connection_id=request.query_params.get('connection_id'),
            record_type=request.query_params.get(
                'record_type',
                'vendorBill',
            ),
            force_refresh=False,
        )

    def post(self, request):
        # Enforce Company Admin permission server-side.
        if not _is_company_admin(request.user):
            return Response(
                {'detail': 'Only Company Admin can refresh NetSuite fields.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return self._serve_catalogue(
            request,
            connection_id=request.data.get('connection_id'),
            record_type=request.data.get('record_type', 'vendorBill'),
            force_refresh=True,
        )

    def _serve_catalogue(
        self,
        request,
        *,
        connection_id,
        record_type,
        force_refresh,
    ):
        if force_refresh and not _is_company_admin(request.user):
            return Response(
                {'detail': 'Only Company Admin can refresh NetSuite fields.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not connection_id:
            return Response(
                {'detail': 'connection_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(record_type, str) or not record_type.strip():
            return Response(
                {'detail': 'record_type must be a non-empty string.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record_type = record_type.strip()

        try:
            company = getattr(request.user, 'company', None)

            if company is None:
                return Response(
                    {'detail': 'User is not associated with a company.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            catalogue = NetSuiteFieldMappingService().get_field_catalogue(
                company=company,
                connection_id=connection_id,
                record_type=record_type,
                force_refresh=force_refresh,
            )

            serialized = dict(
                catalogue
            )

            for key in (
                'record_type',
                'fields',
                'custom_fields',
                'fetched_at',
                'source',
                'stale',
                'available',
                'error',
            ):
                if key in catalogue:
                    serialized[key] = catalogue[key]

            live_refresh_succeeded = (
                force_refresh
                and catalogue.get('source') == 'netsuite'
            )

            serialized['refresh_failed'] = bool(
                force_refresh and not live_refresh_succeeded
            )
            serialized['added_fields_count'] = int(
                catalogue.get('added_fields_count') or 0
            )

            if live_refresh_succeeded:
                message = 'NetSuite field catalogue refreshed successfully.'
            elif force_refresh:
                message = (
                    'NetSuite refresh failed; the saved catalogue was preserved.'
                )
            elif catalogue.get('source') == 'fallback':
                message = (
                    'No saved NetSuite catalogue exists yet; '
                    'showing standard fields.'
                )
            else:
                message = 'NetSuite field catalogue loaded successfully.'

            return success_response(
                message=message,
                data=serialized,
            )

        except NetSuiteTokenExchangeException:
            return _reauth_required_response()

        except NetSuiteConnectionNotFoundException as exc:
            if 'not active' in str(exc).lower():
                return _reauth_required_response()

            return Response(
                {'detail': str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception:
            logger.exception(
                'Failed to %s NetSuite field catalogue — user=%s',
                'refresh' if force_refresh else 'load',
                getattr(request.user, 'id', None),
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
                    'refresh_failed': bool(force_refresh),
                    'added_fields_count': 0,
                    'error': 'The field catalogue could not be loaded.',
                },
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
            message = str(exc)

            if "not active" in message.lower():
                return _reauth_required_response()

            return Response(
                {"detail": message},
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
            message = str(exc)
            if "not active" in message.lower():
                return _reauth_required_response()
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
        except NetSuiteTokenExchangeException:
            return _reauth_required_response()
        except NetSuiteRecordFetchException as exc:
            token_error = self._find_exception(
                exc,
                NetSuiteTokenExchangeException,
            )
            if token_error is not None:
                return _reauth_required_response()
            logger.exception(
                "NetSuite provider validation failed — document=%s connection=%s user=%s",
                document_id,
                connection_id,
                getattr(request.user, "id", None),
            )
            return Response(
                {
                    "detail": (
                        "We could not connect to NetSuite right now. "
                        "Please check your NetSuite connection and try again."
                    ),
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

    @staticmethod
    def _find_exception(exc, exception_type):
        current = exc

        while current is not None:
            if isinstance(current, exception_type):
                return current
            current = current.__cause__ or current.__context__

        return None


class NetSuiteValidationDiagnosticsView(APIView):
    """Generate AI explanations for persisted NetSuite validation errors."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def post(self, request):
        company = getattr(request.user, "company", None)

        if company is None:
            return Response(
                {
                    "detail": (
                        "No company is associated with this user."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validation_ids = request.data.get(
            "validation_ids"
        )

        connection_id = request.data.get(
            "connection_id"
        )

        if not isinstance(validation_ids, list):
            return Response(
                {
                    "detail": (
                        "validation_ids must be a list."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not connection_id:
            return Response(
                {
                    "detail": (
                        "A NetSuite connection is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = net_suite_diagnostics_service.diagnose(
                company=company,
                connection_id=connection_id,
                validation_ids=validation_ids,
            )

        except AIProviderError as exc:
            return Response(
                {"detail": str(exc)},
                status=(
                    status.HTTP_429_TOO_MANY_REQUESTS
                    if exc.status_code == 429
                    else status.HTTP_503_SERVICE_UNAVAILABLE
                ),
            )
        
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception(
                "Failed to generate NetSuite validation diagnostics "
                "— user=%s connection=%s",
                getattr(request.user, "id", None),
                connection_id,
            )

            return Response(
                {
                    "detail": (
                        "We could not prepare AI resolution guidance right now."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return success_response(
            message=(
                "NetSuite validation diagnostics generated "
                "successfully."
            ),
            data=result,
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
        job = create_job(
            user=request.user,
            action="validate",
            document_ids=document_ids,
            connection_id=connection_id,
        )
        dispatch_job(job.id)

        return success_response(
            message="Batch validation queued successfully.",
            data={
                "job_id": str(job.id),
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

        job = create_job(
            user=request.user,
            action="post",
            document_ids=document_ids,
            connection_id=connection_id,
        )
        dispatch_job(job.id)

        return success_response(
            message="Batch posting queued successfully.",
            data={
                "job_id": str(job.id),
                "action": "post",
                "total": len(document_ids),
                "status": "PENDING",
            },
        )


class NetSuiteBatchJobStatusView(APIView):
    """Return progress for an authorized NetSuite batch job (PostgreSQL-backed)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        try:
            job = NetSuiteBatchJob.objects.filter(pk=str(job_id)).first()
        except (ValueError, DjangoValidationError):
            job = None

        if job is None:
             return Response(
                 {"detail": "Batch job not found or expired."},
                 status=status.HTTP_404_NOT_FOUND,
             )
            

        if str(job.user_id) != str(request.user.id):
             raise PermissionDenied("You cannot access this batch job.")

        # Self-healing: resume jobs whose worker died. Triggered by the
        # client's polling; must never break the status response.
        try:
            if recover_jobs(job.user_id):
                job.refresh_from_db()
        except Exception as exc:  # noqa: BLE001
            logger.warning("NetSuite batch recovery skipped: %s", exc)

        finished = job.status == NetSuiteBatchJob.STATUS_SUCCESS

        data = {
            "job_id": str(job.id),
            "action": job.action,
            "status": job.status,
            "total": job.total,
            "completed": job.completed,
            "succeeded": job.succeeded,
            "failed": job.failed,
            # progress responses carry the latest items; a finished job all of them
            "results": job.results if finished else (job.results or [])[-25:],
        }

        if job.status == NetSuiteBatchJob.STATUS_FAILURE:
            data["error"] = job.error or "The batch job failed."

        return success_response(
            message="Batch job status retrieved successfully.",
            data=data)