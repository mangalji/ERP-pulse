"""
Business logic for connecting an AGSuite ERP user's NetSuite account.

Orchestrates oauth.py (URL/state), NetSuiteAuthClient (token exchange),
and NetSuiteConnectionRepository (persistence) — the view layer never
touches any of those directly, mirroring how AuthenticationService
orchestrates UserRepository/OTPService for the accounts app.
"""

import logging
from difflib import SequenceMatcher
import hashlib
import json
import re
import requests
from accounts.models import User
from django.db import transaction
from django.conf import settings
from netsuite.client import NetSuiteAuthClient
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import (
    NetSuiteStateMismatchException, 
    NetSuiteConnectionNotFoundException, 
    NetSuiteConnectionAlreadyExistsException,
    NetSuiteRecordFetchException,
    NetSuiteTokenExchangeException,
)
from netsuite.models import EmployeeConnection, NetSuiteConnection, NetSuiteCustomField, NetSuiteOCRPosting, NetSuiteReferenceRecord, NetSuiteFieldCatalogue, NetSuiteUserConnectionPreference
from netsuite.oauth import build_authorization_url, resolve_user_id_from_state
from netsuite.repositories import NetSuiteConnectionAuditLogRepository, NetSuiteConnectionRepository
from netsuite.token_manager import NetSuiteTokenManager
from netsuite.vendor_bill_baseline import VENDOR_BILL_BASELINE_FIELDS
from tenancy.services import company_lifecycle_service
from ocr.models import OCRNetSuiteFieldMapping, OCRValidationResult, MappingStatus, ValidationStatus

logger = logging.getLogger(__name__)

class NetSuiteConnectionService:    
    """
    Business logic for the NetSuite OAuth connect/callback flow.

    Data-fetching methods (SuiteQL, REST Records) are intentionally not
    implemented yet — this service currently only completes and persists
    the OAuth handshake.
    """

    def __init__(
        self,
        repository: NetSuiteConnectionRepository | None = None,
        client: NetSuiteAuthClient | None = None,
        audit_log_repository: NetSuiteConnectionAuditLogRepository | None = None,
        token_manager: NetSuiteTokenManager | None=None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()
        self.audit_log_repository = audit_log_repository or NetSuiteConnectionAuditLogRepository()
        self.token_manager = token_manager or NetSuiteTokenManager(repository=self.repository)

    def _ensure_user_company_operational(self, *, user: User) -> None:
        company = getattr(user, 'company', None)

        if company is not None:
            company_lifecycle_service.ensure_operational(
                company=company
            )
    
    def get_authorization_url(self, *, user: User, connection) -> str:
        """Step 1: build the URL the frontend should redirect the browser to."""
        self._ensure_user_company_operational(user=user)
        return build_authorization_url(user_id=str(user.id),connection_id=str(connection.id),account_id=connection.netsuite_account_id,
        client_id=connection.client_id,)

    def handle_callback(self, *, code: str, state: str) -> User:
        """
        Step 2: verify `state`, exchange `code` for tokens, and persist
        the connection. Returns the User the connection belongs to (the
        view uses this to decide where to redirect the browser next).
        """
        user_id, connection_id = resolve_user_id_from_state(state)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            # Only reachable if the user was deleted between /connect/ and
            # NetSuite's redirect back — the signature itself already
            # proved the state wasn't tampered with.
            raise NetSuiteStateMismatchException('Invalid OAuth state parameter.') from exc
        self._ensure_user_company_operational(user=user)

        connection = self.repository.get_by_id(
            user=user,
            connection_id=connection_id,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")
        try:
            client = NetSuiteAuthClient(
                account_id=connection.netsuite_account_id,
                client_id=connection.client_id,
                client_secret=connection.client_secret,
            )
            token_set = client.exchange_code_for_tokens(code=code)

            self.repository.complete_OAuth(
                connection,
                access_token=token_set.access_token,
                refresh_token=token_set.refresh_token,
                access_token_expires_at=token_set.access_token_expires_at,
            )
            from netsuite.models import NetSuiteUserConnectionPreference

            preference, _ = (NetSuiteUserConnectionPreference.objects.get_or_create(user=user))
            
            if preference.connection_id is None:
                preference.connection = connection
                preference.save(
                    update_fields=[
                        "connection",
                        "updated_at",
                    ]
                )
            self.audit_log_repository.log(action='oauth_completed', connection=connection)

            # Reference/master data is synchronized asynchronously. OAuth
            # callback must remain fast and must not block on a large account.
            try:
                from netsuite.tasks import sync_netsuite_reference_data

                if hasattr(sync_netsuite_reference_data, "delay"):
                    sync_netsuite_reference_data.delay(str(connection.id))
                else:
                    logger.warning(
                        "Celery task dispatch unavailable; reference sync not queued — connection=%s",
                        connection.id,
                    )
            except Exception:
                logger.exception(
                    "Failed to queue NetSuite reference sync — connection=%s",
                    connection.id,
                )

        except Exception as exc:

            logger.exception(
                "NetSuite OAuth token exchange failed — connection=%s",
                connection.id,
            )

            connection.status = "error"
            connection.is_active = False
            connection.last_error = str(exc)[:2000]
            connection.save(
                update_fields=[
                    "status",
                    "is_active",
                    "last_error",
                    "updated_at",
                ]
            )

            self.audit_log_repository.log(
                action="oauth_failed",
                connection=connection,
                detail=str(exc)[:1000],
            )
            raise


    def list_connections(self,*,user:User):
        self._ensure_user_company_operational(user=user)
        return self.repository.list_by_user(user)
    
    def create_connection(
            self,*,
            user:User,
            client_name:str,
            environment:str,
            client_id:str,
            client_secret:str,
            netsuite_account_id:str,
            company_id=None):
        self._ensure_user_company_operational(user=user)

        existing = self.repository.get_existing_for_account(
            company_id=user.company_id,
            netsuite_account_id=netsuite_account_id,
        )

        if existing:
            if (
                existing.status == 'connected' 
                and existing.is_active
                and not settings.DEBUG
                ):
                raise NetSuiteConnectionAlreadyExistsException(
                    "This NetSuite account is already connected."
                )

            connection = self.repository.prepare_for_oauth_retry(
                existing,
                user=user,
                company_id=company_id,
                client_name=client_name,
                environment=environment,
                client_id=client_id,
                client_secret=client_secret,
                # netsuite_account_id=netsuite_account_id,
            )

            self.audit_log_repository.log(
                action="oauth_retry_started",
                connection=connection,
            )

        else:

            connection = self.repository.create(
                user=user,
                client_name=client_name,
                client_id=client_id,
                environment=environment,
                client_secret=client_secret,
                netsuite_account_id=netsuite_account_id,
                company_id=company_id,
            )

            self.audit_log_repository.log(
                action="created",
                connection=connection,
            )

        authorization_url = self.get_authorization_url(user=user,connection=connection)

        return {
            "connection":connection,
            "authorization_url":authorization_url,
        }
    
    def rename_connection(
            self,*,
            user:User,
            connection_id,
            client_name:str,
            ):
        self._ensure_user_company_operational(user=user)
        connection = self.repository.get_by_id(user,connection_id)

        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")

        old_name = connection.client_name
        renamed = self.repository.rename(
            connection,client_name
        )
        self.audit_log_repository.log(
            action='renamed', connection=renamed,
            detail=f'"{old_name}" -> "{client_name}"',
        )
        return renamed
    
    def delete_connection(
            self,*,
            user:User,
            connection_id,
    ):

        self._ensure_user_company_operational(user=user)

        if not self._is_company_admin(user):
            raise PermissionError(
            "Only Company Admin can delete NetSuite connections."
        )
        connection = self.repository.get_by_id(
            user,
            connection_id,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException(
            "NetSuite connection not found."
        )

        self.audit_log_repository.log(
            action="deleted",
            connection=connection,
            user=user,
        )

        self.repository.delete(connection)
    
    def switch_connection(
            self,*,
            user:User,
            connection_id):

        self._ensure_user_company_operational(user=user)

        connection = self.repository.get_authorized_for_user(
            user=user,
            connection_id=connection_id,
        )

        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection is not available to this user."
            )
            
        preference, _ = (
            NetSuiteUserConnectionPreference.objects
            .select_for_update()
            .get_or_create(user=user)
            )
        preference.connection = connection
        preference.save(
            update_fields=[
                'connection',
                'updated_at',
            ]
        )
        self.audit_log_repository.log(
        action='switched_active',
        connection=connection,
        )
        return connection

    def get_current_connection( self, *, user: User):
        self._ensure_user_company_operational(
            user=user,
        )

        return self.repository.get_for_user(user)

    def list_available_for_user(self, user: User):
        self._ensure_user_company_operational(
            user=user,
        )

        return self.repository.list_available_for_user(
            user,
        )

    def get_company_connections(self, *, company_id):
        return (
            NetSuiteConnection.objects
            .filter(
                company_id=company_id,
                is_active=True,
            ).prefetch_related(
                'employee_assignments__employee',
            )
            .order_by("-connected_at")
        )

    @staticmethod
    def _is_company_admin(user):
        if getattr(user, "is_superuser", False):
            return True

        if not getattr(user, "company_id", None):
            return False

        return user.user_roles.filter(
            role__name__iexact="Company Admin",
        ).exists()

    def assign_employee(self, *, user:User, connection_id, employee_id):

        self._ensure_user_company_operational(user=user)

        if not self._is_company_admin(user):
            raise PermissionError(
                "Only Company Admin can assign NetSuite connections."
            )
        connection = (
            NetSuiteConnection.objects
            .filter(
                id=connection_id,
                company_id=user.company_id,
                is_active=True,
            )
            .first()
        )

        if connection is None:
            raise NetSuiteConnectionNotFoundException(
            "NetSuite connection not found."
        )

        employee = (
        User.objects
        .filter(
            id=employee_id,
            company_id=user.company_id,
            ).first()
        )

        if employee is None:
            raise ValueError(
            "Employee does not belong to this company."
            )

        if self._is_company_admin(employee):
            raise ValueError(
                'Company Admin does not need employee assignment.'
            )


        assignment, _ = EmployeeConnection.objects.get_or_create(
            employee=employee,
            connection=connection,
        )
        return assignment

    def remove_employee(self, *, user:User, connection_id, employee_id):

        self._ensure_user_company_operational(user=user)

        if not self._is_company_admin(user):
            raise PermissionError(
                "Only Company Admin can remove NetSuite assignments."
            )
        connection = (
        NetSuiteConnection.objects
        .filter(
            id=connection_id,
            company_id=user.company_id,
        )
        .first()
    )

        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection not found."
            )
        deleted, _ = EmployeeConnection.objects.filter(
            connection=connection,
            employee_id=employee_id,
        ).delete()

        if deleted == 0:
            raise ValueError(
                "Employee is not assigned to this connection."
            )
        

    def get_employee_connection(self, *, employee_id):

        user = User.objects.select_related("company").get(pk=employee_id)

        return self.repository.get_for_user(user)

    def test_connection(self, *, connection_id):
        connection = NetSuiteConnection.objects.select_related('company').get(pk=connection_id)
        if connection.company is not None:
            company_lifecycle_service.ensure_operational(
                company=connection.company
            )

        try:
            access_token = self.token_manager.get_valid_access_token(connection)

        except NetSuiteTokenExchangeException as exc:
            message = str(exc)

            if message.startswith("NETSUITE_INVALID_GRANT:"):
                return {
                    'success': False,
                    'message': (
                        'NetSuite authorization has expired. '
                        'Please reconnect this account.'
                    ),
                }
            connection.status = 'error'
            connection.last_error = message[:2000]
            connection.consecutive_failures += 1
            connection.save(update_fields=['status','last_error','consecutive_failures','updated_at'])
            return {'success':False,'message':message}

        except Exception as exc:
            connection.status = 'error'
            connection.last_error = str(exc)[:2000]
            connection.consecutive_failures += 1

            connection.save(
                update_fields=[
                    'status',
                    'last_error',
                    'consecutive_failures',
                    'updated_at'
                ]
            )

            return {
                'success': False,
                'message': str(exc),
            }
        
        client = NetSuiteAuthClient(
            account_id=connection.netsuite_account_id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
            access_token=access_token,
        )
        try:
            client.get_records(record_type='customer', limit=1)
            connection.status = 'connected'
            connection.last_error = None
            connection.consecutive_failures = 0
            connection.save(update_fields=['status', 'last_error', 'consecutive_failures', 'updated_at'])
            return {'success': True, 'message': 'Connection test successful.'}
        except Exception as exc:
            connection.status = 'error'
            connection.last_error = str(exc)[:2000]
            connection.consecutive_failures += 1
            connection.save(update_fields=['status', 'last_error', 'consecutive_failures', 'updated_at'])
            return {'success': False, 'message': str(exc)}

    def mark_oauth_failed(
        self,
        *,
        state: str,
        error_message: str,
    ):
        user_id, connection_id = resolve_user_id_from_state(state)

        connection = self.repository.get_by_id(
            user=User.objects.get(id=user_id),
            connection_id=connection_id,
        )

        if connection:
            connection.status = "error"
            connection.is_active = False
            connection.last_error = error_message[:2000]
            connection.save(
                update_fields=[
                    "status",
                    "is_active",
                    "last_error",
                    "updated_at",
                ]
            )

            self.audit_log_repository.log(
                action="oauth_failed",
                connection=connection,
                detail=error_message[:1000],
            )

        return connection
    

class NetSuiteDataService:
    """
    Fetches live NetSuite record data for an already-connected user.

    Owns the one piece of business logic a plain pass-through read still
    needs: making sure the access token is valid — refreshing it first
    via the existing NetSuiteAuthClient.refresh_access_token() /
    NetSuiteConnectionRepository.update_tokens() if it's expired or about
    to be — before handing off to the Client. No NetSuite response
    shaping happens here; the raw record data is returned as-is.
    """

    def __init__(
        self,
        repository: NetSuiteConnectionRepository | None = None,
        token_manager: NetSuiteTokenManager | None = None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()
        self.token_manager = token_manager or NetSuiteTokenManager(repository=self.repository)

    def _get_authenticated_client(self, user: User) -> NetSuiteAuthClient:
        company = getattr(user, 'company', None)

        if company is not None:
            company_lifecycle_service.ensure_operational(
                company=company
            )

        connection = self._require_connection(user)
        access_token = self.token_manager.get_valid_access_token(connection)

        client = NetSuiteAuthClient(
            account_id=connection.netsuite_account_id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
            access_token=access_token,
        )

        return client, connection

    def get_records(
        self,
        *,
        record_type: str,
        user: User,
        limit: int | None = None,
        offset: int | None = None,
        params: dict | None = None,
    ) -> dict:
        client, connection = self._get_authenticated_client(user)
        return self._call_and_track_health(
            connection,
            client.get_records,
            record_type=record_type,
            limit=limit,
            offset=offset,
            params=params,
        )

    def get_record(
        self,
        *,
        record_type: str,
        record_id: str,
        user: User,
        params: dict | None = None,
    ) -> dict:
        client, connection = self._get_authenticated_client(user)
        return self._call_and_track_health(
            connection,
            client.get_record,
            record_type=record_type,
            record_id=record_id,
            params=params,
        )

    def execute_suiteql(self, *, query: str, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        """
        Run a SuiteQL query for `user`'s connected NetSuite account.

        Reuses _get_authenticated_client() — the same connection lookup
        and token-refresh path get_records()/get_record() already use —
        so authentication logic isn't duplicated for SuiteQL. The Client
        (netsuite.client.NetSuiteAuthClient.execute_suiteql) is the only
        thing that actually talks to NetSuite.
        """
        client, connection = self._get_authenticated_client(user)
        return self._call_and_track_health(
            connection, client.execute_suiteql, query=query, limit=limit, offset=offset,
        )

    def _call_and_track_health(self, connection, client_method, **kwargs) -> dict:
        """
        Runs a NetSuite client call and records the outcome on the
        connection — last_synced_at/last_error/consecutive_failures —
        so connection health is visible without a separate sync/health
        job. Re-raises whatever the client raises; this only observes.
        """
        try:
            result = client_method(**kwargs)
        except Exception as exc:
            self.repository.record_sync_failure(connection, error_message=str(exc))
            raise
        self.repository.record_sync_success(connection)
        self.repository.touch_last_used(connection)
        return result

    def get_customers(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=user, limit=limit, offset=offset)

    def get_employees(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.EMPLOYEE, user=user, limit=limit, offset=offset)

    def get_vendors(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.VENDOR, user=user, limit=limit, offset=offset)

    def get_sales_orders(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.SALES_ORDER, user=user, limit=limit, offset=offset)
    
    def get_purchase_orders(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.PURCHASE_ORDER, user=user, limit=limit, offset=offset)
    
    def get_invoices(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.INVOICE, user=user, limit=limit, offset=offset)

    def get_items(self, *, user: User, item_type: str = NetSuiteRecordType.INVENTORY_ITEM, limit: int | None = None, offset: int | None = None) -> dict:
        if not NetSuiteRecordType.is_valid(item_type):
            raise ValueError(f"Invalid NetSuite item type: {item_type}")
        return self.get_records(record_type=item_type, user=user, limit=limit, offset=offset)

    # -----------------------------------------------------------------
    # SuiteQL-based list methods
    #
    # The plain REST record collection endpoint (get_customers() etc.
    # above, via get_records()) returns only {id, links} per item —
    # no business fields at all. This is documented NetSuite behavior,
    # not a bug in this client: see "Listing All Record Instances" in
    # Oracle's NetSuite REST API docs, which shows exactly this shape.
    # Getting field data out of the plain collection endpoint requires
    # fetching every record individually (N+1 — slow, and not what we
    # want), so list pages use SuiteQL instead: one call, exact fields,
    # no extra round trips.
    #
    # Field verification status:
    # - customer/vendor id/entityid/companyname/email fields: already
    #   verified against a live NetSuite sandbox (see analytics/services.py).
    # - transaction id/tranid/entity/foreigntotal/trandate/type fields:
    #   same — already verified in analytics/services.py.
    # - employee, inventoryitem fields and BUILTIN.DF() usage below:
    #   NOT yet verified against this project's NetSuite sandbox —
    #   sourced from Oracle's official SuiteQL documentation and
    #   confirmed community examples, but should be tested against a
    #   real account and adjusted if any field name doesn't match.
    # -----------------------------------------------------------------

    def _list_via_suiteql(self, *, user: User, query: str, limit: int, offset: int) -> dict:
        response = self.execute_suiteql(query=query, user=user, limit=limit, offset=offset)
        return {
            'items': response.get('items', []),
            'totalResults': response.get('totalResults', 0),
        }

    def list_customers(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
        raw = self._list_via_suiteql(
            user=user, limit=limit, offset=offset,
            query="""
                SELECT id, entityid, companyname, email, phone, isinactive
                FROM customer
                ORDER BY id
            """,
        )
        raw['items'] = [
            {
                'id': row.get('id'),
                'entityId': row.get('entityid'),
                'companyName': row.get('companyname'),
                'email': row.get('email'),
                'phone': row.get('phone'),
                'status': 'Inactive' if row.get('isinactive') == 'T' else 'Active',
            }
            for row in raw['items']
        ]
        return raw

    def list_vendors(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
        raw = self._list_via_suiteql(
            user=user, limit=limit, offset=offset,
            query="""
                SELECT id, entityid, companyname, email, phone, isinactive
                FROM vendor
                ORDER BY id
            """,
        )
        raw['items'] = [
            {
                'id': row.get('id'),
                'entityId': row.get('entityid'),
                'companyName': row.get('companyname'),
                'email': row.get('email'),
                'phone': row.get('phone'),
                'status': 'Inactive' if row.get('isinactive') == 'T' else 'Active',
            }
            for row in raw['items']
        ]
        return raw

    def list_employees(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
        raw = self._list_via_suiteql(
            user=user, limit=limit, offset=offset,
            query="""
                SELECT id, entityid, firstname, lastname, email, title,
                       BUILTIN.DF(department) AS department
                FROM employee
                ORDER BY id
            """,
        )
        raw['items'] = [
            {
                'id': row.get('id'),
                'entityId': row.get('entityid'),
                'firstName': row.get('firstname'),
                'lastName': row.get('lastname'),
                'email': row.get('email'),
                'title': row.get('title'),
                'department': row.get('department'),
            }
            for row in raw['items']
        ]
        return raw

    def list_inventory_items(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
        """
        List inventory items via SuiteQL, falling back to the REST Record
        API if SuiteQL fails (e.g. the inventoryitem table isn't accessible
        for this account).

        SuiteQL is preferred because it returns business fields
        (displayname, cost, vendor) in a single call. The REST Record
        collection endpoint only returns {id, links} per item — no usable
        fields — so it's only used for the totalResults count.
        """
        try:
            raw = self._list_via_suiteql(
                user=user, limit=limit, offset=offset,
                query="""
                    SELECT id, itemid, displayname, cost,
                           BUILTIN.DF(vendor) AS vendorname
                    FROM inventoryitem
                    ORDER BY id
                """,
            )
            raw['items'] = [
                {
                    'id': row.get('id'),
                    'itemId': row.get('itemid'),
                    'displayName': row.get('displayname'),
                    'vendorName': row.get('vendorname'),
                    'cost': row.get('cost'),
                    'type': 'Inventory Item',
                }
                for row in raw['items']
            ]
            return raw
        except Exception as exc:
            logger.warning(
                'list_inventory_items SuiteQL failed for user %s — '
                'falling back to REST API. Error: %s', user.id, exc,
            )
            # Fallback: REST Record collection endpoint — only {id, links}
            # per item, but gives a valid totalResults count.
            response = self.get_records(
                record_type=NetSuiteRecordType.INVENTORY_ITEM,
                user=user, limit=limit, offset=offset,
            )
            items = response.get('items', [])
            return {
                'items': [
                    {
                        'id': item.get('id'),
                        'itemId': None,
                        'displayName': None,
                        'vendorName': None,
                        'cost': None,
                        'type': 'Inventory Item',
                    }
                    for item in items
                ],
                'totalResults': response.get('totalResults', len(items)),
            }

    def _list_transactions_via_suiteql(self, *, user: User, transaction_type: str, limit: int, offset: int) -> dict:
        """Shared by sales orders/purchase orders/invoices — all live in NetSuite's single `transaction` table, discriminated by `type`."""
        raw = self._list_via_suiteql(
            user=user, limit=limit, offset=offset,
            query=f"""
                SELECT id, tranid, entity, BUILTIN.DF(entity) AS entityname,
                       BUILTIN.DF(status) AS status, foreigntotal, trandate
                FROM transaction
                WHERE type = '{transaction_type}'
                ORDER BY id
            """,
        )
        raw['items'] = [
            {
                'id': row.get('id'),
                'tranId': row.get('tranid'),
                'entity': {'id': row.get('entity'), 'name': row.get('entityname')},
                'status': row.get('status'),
                'total': row.get('foreigntotal'),
                'createdDate': row.get('trandate'),
            }
            for row in raw['items']
        ]
        return raw

    def list_sales_orders(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
        return self._list_transactions_via_suiteql(user=user, transaction_type='SalesOrd', limit=limit, offset=offset)

    def list_purchase_orders(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
        return self._list_transactions_via_suiteql(user=user, transaction_type='PurchOrd', limit=limit, offset=offset)

    def list_invoices(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
        return self._list_transactions_via_suiteql(user=user, transaction_type='CustInvc', limit=limit, offset=offset)

    def _require_connection(self, user: User):  

        connection = self.repository.get_for_user(user)

        if connection is None or not connection.is_active or connection.status != "connected":
            raise NetSuiteConnectionNotFoundException(
                'No active NetSuite connection found. Please connect your NetSuite account first.'
            )
        return connection

class NetSuiteReferenceSyncService:
    """Synchronize NetSuite master/reference IDs into AGSuite ERP."""

    PAGE_SIZE = 1000

    def __init__(self, repository=None):
        self.repository = repository or NetSuiteConnectionRepository()
        self.data_service = NetSuiteDataService(repository=self.repository)

    def _sync_id_collection(self, *, connection, user, record_type: str) -> int:
        offset = 0
        total_synced = 0

        while True:
            response = self.data_service.get_records(
                record_type=record_type,
                user=user,
                limit=self.PAGE_SIZE,
                offset=offset,
            )
            items = response.get("items", []) if isinstance(response, dict) else []
            if not items:
                break

            cached = []
            for row in items:
                internal_id = row.get("id")
                if internal_id is None:
                    continue
                cached.append({
                    "connection_id": connection.id,
                    "record_type": record_type,
                    "internal_id": str(internal_id),
                    "data": {"links": row.get("links", [])},
                })

            total_synced += self.repository.upsert_reference_records(cached)

            if not response.get("hasMore") and len(items) < self.PAGE_SIZE:
                break
            offset += len(items)

        return total_synced

    def _sync_vendors(self, *, connection, user) -> int:
        offset = 0
        total_synced = 0

        while True:
            raw = self.data_service.list_vendors(
                user=user,
                limit=self.PAGE_SIZE,
                offset=offset,
            )
            items = raw.get("items", []) if isinstance(raw, dict) else []
            if not items:
                break

            records = []
            for row in items:
                name = row.get("companyName") or row.get("entityId") or ""
                records.append({
                    "connection_id": connection.id,
                    "record_type": NetSuiteRecordType.VENDOR,
                    "internal_id": row.get("id"),
                    "external_id": row.get("entityId"),
                    "name": name,
                    "search_name": str(name).strip().lower(),
                    "is_inactive": row.get("status") == "Inactive",
                    "data": row,
                })

            total_synced += self.repository.upsert_reference_records(records)

            if len(items) < self.PAGE_SIZE:
                break
            offset += len(items)

    def _sync_inventory_items(self, *, connection, user) -> int:
        offset = 0
        total_synced = 0
        while True:
            raw = self.data_service.list_inventory_items(
                user=user,
                limit=self.PAGE_SIZE,
                offset=offset,
            )
            items = raw.get("items", []) if isinstance(raw, dict) else []
            if not items:
                break

            records = []
            for row in items:
                name = row.get("displayName") or row.get("itemId") or ""
                records.append({
                    "connection_id": connection.id,
                    "record_type": NetSuiteRecordType.INVENTORY_ITEM,
                    "internal_id": row.get("id"),
                    "external_id": row.get("itemId"),
                    "name": name,
                    "search_name": str(name).strip().lower(),
                    "item_type": row.get("type") or "Inventory Item",
                    "is_inactive": False,
                    "data": row,
                })

            total_synced += self.repository.upsert_reference_records(records)

            if not raw.get("hasMore") and len(items) < self.PAGE_SIZE:
                break
            offset += len(items)

        return total_synced

    def sync_connection(self, *, connection_id) -> dict:

        connection = NetSuiteConnection.objects.select_related('user__company').get(pk=connection_id)

        if connection.status != "connected" or not connection.is_active:
            raise ValueError("NetSuite connection is not active.")

        user = connection.user
        if user.company is not None:
            company_lifecycle_service.ensure_operational(
                company=user.company
            )
        counts = {}
        errors_found = []

        # Cache IDs for all NetSuite record types currently supported by
        # this application, except Vendor Bill itself (created by posting).
        id_only_types = (
            NetSuiteRecordType.CUSTOMER,
            NetSuiteRecordType.EMPLOYEE,
            NetSuiteRecordType.SALES_ORDER,
            NetSuiteRecordType.PURCHASE_ORDER,
            NetSuiteRecordType.INVOICE,
            NetSuiteRecordType.NON_INVENTORY_SALE_ITEM,
            NetSuiteRecordType.NON_INVENTORY_RESALE_ITEM,
            NetSuiteRecordType.NON_INVENTORY_PURCHASE_ITEM,
            NetSuiteRecordType.SERVICE_SALE_ITEM,
            NetSuiteRecordType.SERVICE_RESALE_ITEM,
            NetSuiteRecordType.SERVICE_PURCHASE_ITEM,
            NetSuiteRecordType.DESCRIPTION_ITEM,
            NetSuiteRecordType.DISCOUNT_ITEM,
            NetSuiteRecordType.KIT_ITEM,
            NetSuiteRecordType.ASSEMBLY_ITEM,
            NetSuiteRecordType.MARKUP_ITEM,
            NetSuiteRecordType.PAYMENT_ITEM,
            NetSuiteRecordType.SUBTOTAL_ITEM,
            NetSuiteRecordType.ITEM_GROUP,
        )

        for record_type in id_only_types:
            try:
                counts[record_type] = self._sync_id_collection(
                    connection=connection,
                    user=user,
                    record_type=record_type,
                )
            except Exception as exc:
                logger.exception(
                    "NetSuite reference sync failed for %s — connection=%s",
                    record_type,
                    connection.id,
                )
                errors_found.append(f"{record_type}: {exc}")

        try:
            counts[NetSuiteRecordType.VENDOR] = self._sync_vendors(
                connection=connection,
                user=user,
            )
        except Exception as exc:
            logger.exception(
                "NetSuite vendor sync failed — connection=%s",
                connection.id,
            )
            errors_found.append(f"vendor: {exc}")

        try:
            counts[NetSuiteRecordType.INVENTORY_ITEM] = self._sync_inventory_items(
                connection=connection,
                user=user,
            )
        except Exception as exc:
            logger.exception(
                "NetSuite inventory item sync failed — connection=%s",
                connection.id,
            )
            errors_found.append(f"inventoryItem: {exc}")

        from django.utils import timezone
        connection.last_synced_at = timezone.now()
        connection.last_error = "; ".join(errors_found)[:5000] or None
        connection.save(
            update_fields=["last_synced_at", "last_error", "updated_at"]
        )

        return {
            "connection_id": str(connection.id),
            "counts": counts,
            "errors": errors_found,
        }


class NetSuiteVendorBillPostingService:
    """Create a NetSuite Vendor Bill from an approved OCR version."""

    def __init__(self, repository=None):
        self.repository = repository or NetSuiteConnectionRepository()
        self.data_service = NetSuiteDataService(repository=self.repository)

    @staticmethod
    def _is_company_admin(user) -> bool:
        try:
            if getattr(user, "is_superuser", False):
                return True
            return user.user_roles.filter(
                role__name__iexact="Company Admin",
            ).exists()
        except Exception:
            logger.exception(
                "Failed to resolve Company Admin role for OCR posting — user=%s",
                getattr(user, "id", None),
            )
            return False


    @staticmethod
    def _reviewed_data(version) -> dict:
        data = (
            version.reviewed_json
            if isinstance(version.reviewed_json, dict) and version.reviewed_json
            else version.normalized_json
        )
        if not isinstance(data, dict):
            raise ValueError("OCR data is not a valid JSON object.")
        return data

    @staticmethod
    def _normalization_key(value) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _resolve_posting_location_id(self, *, connection) -> str:
        """
        Resolve the temporary/default Vendor Bill posting Location.

        Current development rule:
            Use the active NetSuite Location named "Pune".

        IMPORTANT:
            We do NOT hardcode the NetSuite internal ID because internal IDs
            are account-specific. We resolve "Pune" against the selected
            NetSuite connection and use the returned internal ID.

        Production:
            Replace only this method's selection strategy with the actual
            company/connection/user business rule. The rest of the posting
            flow should remain unchanged.
        """
        location_name = "Pune"

        query_literal = NetSuiteValidationService._suiteql_literal(
            location_name
        )

        query = f"""
            SELECT
                id,
                name,
                isinactive
            FROM location
            WHERE
                LOWER(name) = LOWER({query_literal})
                AND isinactive = 'F'
            ORDER BY id
        """

        try:
            response = NetSuiteValidationService()._execute_live_suiteql(
                connection=connection,
                query=query,
                limit=50,
            )
        except Exception as exc:
            logger.exception(
                "Failed to resolve posting Location — "
                "connection=%s location=%r",
                connection.id,
                location_name,
            )
            raise NetSuiteRecordFetchException(
                f'Unable to resolve NetSuite Location "{location_name}" '
                "in the selected account."
            ) from exc

        rows = (
            response.get("items", [])
            if isinstance(response, dict)
            else []
        )

        active_matches = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            if str(row.get("isinactive", "F")).upper() == "T":
                continue

            location_id = row.get("id")
            if location_id is None:
                continue

            active_matches.append(str(location_id))

        if not active_matches:
            raise ValueError(
                f'NetSuite Location "{location_name}" does not exist '
                "or is inactive in the selected account."
            )

        # Temporary development rule:
        # use the first active Pune record if the account somehow contains
        # duplicate Location names.
        location_id = active_matches[0]

        if len(active_matches) > 1:
            logger.warning(
                "Multiple active NetSuite Locations matched %r; "
                "using first match — id=%s candidates=%s connection=%s",
                location_name,
                location_id,
                len(active_matches),
                connection.id,
            )

        return location_id


    def _resolve_unique_reference(
        self,
        *,
        connection_id,
        record_type: str,
        value: str,
        label: str,
    ):
        matches = self.repository.find_reference_records(
            connection_id=connection_id,
            record_type=record_type,
            search_name=self._normalization_key(value),
        )

        if not matches:
            raise ValueError(
                f'No active NetSuite {label} matched "{value}". '
                "Run the NetSuite reference sync or correct the OCR value."
            )

        if len(matches) > 1:
            raise ValueError(
                f'Multiple NetSuite {label}s matched "{value}". '
                "Posting was stopped to prevent selecting the wrong record."
            )

        return matches[0]

    @staticmethod
    def _apply_custom_fields(*, company, connection, record_type, data):
        """
        Apply saved custom field mappings to the NetSuite payload.

        Returns a list of custom field dicts suitable for NetSuite's
        customFieldList, or None if no custom fields are mapped.
        """
        mappings = OCRNetSuiteFieldMapping.objects.filter(
            company=company,
            connection=connection,
            record_type=record_type,
            is_custom=True,
            mapping_status='MAPPED',
        )

        custom_fields = []
        for mapping in mappings:
            source_key = mapping.source_field_key
            value = data.get(source_key)
            if value is None or value == '':
                continue

            custom_fields.append({
                'scriptId': mapping.target_field_id,
                'value': value,
            })

        return custom_fields or None

    def post_vendor_bill(self, *, document_id, user: User, connection_id=None) -> dict:
        """
        Post the latest validated OCR version as a NetSuite Vendor Bill.

        Posting is fail-closed:
        - the document must belong to the caller's company and be visible;
        - the target NetSuite connection must belong to that company;
        - the latest OCR version must have a VALIDATED validation result;
        - the validated result must belong to the same connection used to post;
        - the OCR version is validated again through the persisted validation
          record before constructing the Vendor Bill payload.
        """
        from ocr.models import (
            OCRDocumentVersion,
            OCRDocument,
            OCRValidationResult,
        )

        company = getattr(user, "company", None)
        if company is None:
            raise ValueError(
                "Your account is not associated with a company."
            )

        company_lifecycle_service.ensure_operational(company=company)

        if self._is_company_admin(user):
            document = (
                OCRDocument.objects
                .filter(
                    pk=document_id,
                    company_id=user.company_id,
                )
                .first()
            )
        else:
            document = (
                OCRDocument.objects
                .filter(
                    pk=document_id,
                    company_id=user.company_id,
                    user=user,
                )
                .first()
            )

        if document is None:
            raise ValueError(
                "OCR document not found or access is not allowed."
            )

        version = (
            OCRDocumentVersion.objects
            .filter(document=document)
            .order_by("-version_number")
            .first()
        )
        if version is None:
            raise ValueError(
                "No saved OCR version exists for this document."
            )

        # A document can be manually revalidated multiple times. Only the
        # latest validation result for the exact version is authoritative.
        validation = (
            OCRValidationResult.objects
            .filter(
                document=document,
                version=version,
            )
            .order_by("-created_at")
            .first()
        )

        if validation is None:
            raise ValueError(
                "This document has not been validated against NetSuite yet."
            )

        if validation.status != ValidationStatus.VALIDATED:
            raise ValueError(
                "This document is not validated. "
                "Validate the document successfully before posting."
            )

        # Posting must use the exact NetSuite connection against which
        # this OCR version was validated.
        #
        # Authorization is checked separately from connection health:
        # - Company Admin can use any active company connection.
        # - Employee can use only an assigned active connection.
        # - Token validity/status is handled by NetSuiteTokenManager.

        validated_connection_id = validation.connection_id

        if validated_connection_id is None:
            raise ValueError(
                "The validation result is missing its NetSuite connection."
            )

        connection = self.repository.get_posting_authorized_connection(
            user=user,
            connection_id=validated_connection_id,
        )

        if connection is None:
            raise ValueError(
                "The validated NetSuite connection is not available to this user."
            )

        if validation.connection_id != connection.id:
            raise ValueError(
                "The selected NetSuite connection does not match the "
                "connection used for validation."
            )


        data = self._reviewed_data(version)
        line_items = data.get("line_items") or []


        # Vendor presence is already enforced during NetSuite reference validation.
        # Posting uses the exact validated NetSuite vendor ID.

        existing = self.repository.get_ocr_posting(
            document_id=document.id,
            version_id=version.id,
        )
        if existing and existing.status == "posted" and existing.netsuite_record_id:
            return {
                "posting_id": str(existing.id),
                "netsuite_record_id": existing.netsuite_record_id,
                "already_posted": True,
            }

        # Reuse the exact vendor/item IDs selected by the successful
        # validation result. Do not run a looser second lookup during posting.
        validated_vendor_id = validation.vendor_netsuite_id
        if not validated_vendor_id:
            raise ValueError(
                "Validated result does not contain a NetSuite vendor ID."
            )

        item_validation_results = validation.items or []

        item_mapping = (
            OCRNetSuiteFieldMapping.objects
            .filter(
                company=company,
                connection=connection,
                record_type="vendorBill",
                mapping_status="MAPPED",
                target_field_id__iexact="item",
            )
            .filter(
                source_scope__iexact="line",
            )
            .order_by("created_at")
            .first()
        )

        vendor = {
            "internal_id": str(validated_vendor_id),
        }

        posting_location_id = self._resolve_posting_location_id(
            connection=connection,
        )

        payload_items = []


        # Same NetSuite item matched by multiple OCR line rows (e.g. OCR
        # extracted "Laptop" 3 times for one line, or several rows
        # string-matched to the same item) would otherwise post as
        # duplicate lines on the Vendor Bill. For now, keep only the
        # first occurrence of a given NetSuite item ID and skip the
        # rest — one real line per item until we have a proper reason
        # to treat repeats as intentional (e.g. distinct rate/quantity
        # combinations).
        seen_item_ids = set()

        if line_items:
            posting_item_source_key = (
                item_mapping.source_field_key
                if item_mapping is not None
                else None
            )

            for index, line in enumerate(line_items, start=1):
                if not isinstance(line, dict):
                    # continue
                    raise ValueError(
                f"Line {index}: OCR line item is invalid."
            )
                if posting_item_source_key:
                    item_name = line.get(posting_item_source_key)

                else:
                    item_name = (
                        line.get("item") or line.get("item_name") or line.get("itemName") or line.get("description")
                    )

                if isinstance(item_name, str):
                    item_name = item_name.strip()

                if not item_name:
                    raise ValueError(
                        f"Line {index}: item value is missing."
                    )
                item_result = NetSuiteValidationService().resolve_item_for_posting(
                    # connection_id=str(connection.id),
                    connection=connection,
                    item_name=item_name,
                    line_index=index,
                )

                if not item_result.get("matched"):
                    if item_result.get("ambiguous"):
                        raise ValueError(
                            f'Line {index}: multiple NetSuite items matched '
                            f'"{item_name}". Please correct the item.'
                        )

                    raise ValueError(
                        f'Line {index}: NetSuite item '
                        f'"{item_name}" does not exist in the selected account.'
                    )

                item_id = item_result.get("netsuite_id")

                if not item_id:
                    raise ValueError(
                        f'Line {index}: NetSuite item ID could not be resolved.'
                    )

                if item_id in seen_item_ids:
                    logger.warning("Skipping line %s ('%s') on Vendor Bill posting — "
                        "NetSuite item %s already used by an earlier line "
                        "on this bill (keeping the first occurrence only) "
                        "— connection=%s",
                        index,
                        item_name,
                        item_id,
                        connection.id,
                    )
                    continue
                seen_item_ids.add(item_id)
                description = line.get("description")
                quantity = line.get("quantity")
                rate = line.get("unit_price")

                # A line with a matched NetSuite item ID but no quantity
                # and no rate isn't a real purchased line — it's usually
                # OCR text (a GL account name, a tax/TDS/GST breakdown
                # row, etc.) that happened to string-match some NetSuite
                # item record. NetSuite itself rejects a Vendor Bill line
                # with neither quantity nor rate (400 INVALID_CONTENT on
                # the whole request, not a per-line error), and posting
                # it even if NetSuite allowed it would be a fake/wrong
                # line item on the bill. So skip it here instead of
                # sending it — only lines with at least a quantity or a
                # rate are treated as real items and go to NetSuite.

                if quantity in (None, "") and rate in (None, ""):
                    logger.warning(
                        "Skipping line %s ('%s') on Vendor Bill posting — "
                        "matched NetSuite item %s but has no quantity or "
                        "rate, so it isn't a real line item — connection=%s",
                        index,
                        description or item_name,
                        item_id,
                        connection.id,
                    )
                    continue

                item_payload = {
                    "item":{
                        "id":str(item_id)
                    },
                    "location":{
                        "id":str(posting_location_id),
                    },
                }

                if quantity not in (None, ""):
                    item_payload["quantity"] = quantity

                if rate not in (None, ""):
                    item_payload["rate"] = rate

                if description not in (None, ""):
                    item_payload["description"] = description

                payload_items.append(item_payload)

        payload = {
            "entity": {"id": vendor["internal_id"]},
            "location":{
                "id":str(posting_location_id),
            },
        }

        if payload_items:
            payload["item"] = {
                "items": payload_items,
            }

        # Apply every other saved, MAPPED, non-custom BODY field mapping
        # (subsidiary, currency, memo, location, department, class,
        # terms, tranid/trandate/duedate if explicitly mapped, etc.) —
        # not just the two hardcoded date fields below. Without this,
        # any account that requires fields NetSuite itself marks
        # required on Vendor Bill (subsidiary and currency on every
        # OneWorld/multi-subsidiary account) will have every single
        # post rejected regardless of vendor/item correctness, since
        # those fields were previously never sent at all.
        standard_field_mappings = (
            OCRNetSuiteFieldMapping.objects
            .filter(
                company=company,
                connection=connection,
                record_type="vendorBill",
                mapping_status="MAPPED",
                is_custom=False,
                target_scope__iexact="body",
            )
            .exclude(target_field_id__iexact="entity")
            .order_by("created_at")
        )

        validation_service = NetSuiteValidationService()

        # NetSuite computes these Vendor Bill fields itself from the line
        # items / tax details sublist — they're read-only on the record,
        # not something the REST API accepts as direct input. If a field
        # mapping (configured on the Field Mapping page) ever targets one
        # of these, sending it crashes the whole post with a generic 400
        # INVALID_CONTENT that gives no indication which field caused it.
        # Skip them here unconditionally so a bad mapping can't silently
        # break posting for every document — NetSuite calculates the
        # real value regardless of what we'd have sent.
        NETSUITE_COMPUTED_READONLY_FIELDS = {
            "taxtotal",
            "total",
            "subtotal",
            "balance",
            "amountremaining",
            "amountpaid",
        }

        for mapping in standard_field_mappings:
            target_field_id = mapping.target_field_id
            if not target_field_id or target_field_id in payload:
                # Already set explicitly above (entity/item), or a
                # duplicate mapping row — first mapping wins.
                continue

            if target_field_id.strip().lower() in NETSUITE_COMPUTED_READONLY_FIELDS:
                logger.warning(
                    "Skipping NetSuite-computed read-only field mapping "
                    "on Vendor Bill posting — field=%s connection=%s. "
                    "NetSuite calculates this from line items/tax details; "
                    "it cannot be set directly. Consider removing this "
                    "mapping on the Field Mapping page.",
                    target_field_id,
                    connection.id,
                )
                continue

            raw_value = data.get(mapping.source_field_key)
            if isinstance(raw_value, str):
                raw_value = raw_value.strip()
            if raw_value in (None, ""):
                continue

            table_config = validation_service.SELECT_FIELD_SUITEQL_TABLES.get(
                target_field_id.strip().lower()
            )

            if table_config is not None:
                resolved_id = validation_service._resolve_select_field_live(
                    connection=connection,
                    target_field_id=target_field_id,
                    value=raw_value,
                )
                if resolved_id:
                    payload[target_field_id] = {"id": resolved_id}
                    continue

                if mapping.is_required:
                    raise ValueError(
                        f'"{raw_value}" could not be matched to an active '
                        f'NetSuite {mapping.target_field_label or target_field_id} '
                        "record. Create or correct it in NetSuite, then "
                        "validate and post again."
                    )

                logger.warning(
                    "Skipping unresolved optional NetSuite select field "
                    "on Vendor Bill posting — field=%s value=%r "
                    "connection=%s",
                    target_field_id,
                    raw_value,
                    connection.id,
                )
                continue

            if (mapping.target_datatype or "").strip().lower() == "select":
                # A select/reference field we don't know how to resolve
                # (no SuiteQL table mapping above). Sending raw OCR text
                # for a reference field would be rejected by NetSuite,
                # so skip rather than guess — required ones will still
                # surface as a clear NetSuite-side rejection.
                logger.warning(
                    "Skipping NetSuite select field with no known "
                    "SuiteQL lookup table — field=%s connection=%s",
                    target_field_id,
                    connection.id,
                )
                continue

            payload[target_field_id] = raw_value

        # Fallback defaults for the most common header fields, only if
        # not already supplied by an explicit field mapping above.
        payload_keys_lower = {key.lower() for key in payload}

        if "tranid" not in payload_keys_lower and data.get("invoice_number"):
            payload["tranid"] = data["invoice_number"]

        if "trandate" not in payload_keys_lower and data.get("invoice_date"):
            payload["trandate"] = data["invoice_date"]

        if "duedate" not in payload_keys_lower and data.get("due_date"):
            payload["duedate"] = data["due_date"]

        custom_fields = self._apply_custom_fields(
            company=company,
            connection=connection,
            record_type="vendorBill",
            data=data,
        )
        if custom_fields:
            payload["customFieldList"] = {
                "customField": custom_fields
            }

        posting = self.repository.save_ocr_posting(
            document=document,
            version=version,
            connection=connection,
            user=user,
            status="pending",
            request_payload=payload,
        )

        try:
            # Use the exact validated connection, not the user's default
            # connection. This prevents posting into a different NetSuite
            # account than the one against which validation succeeded.
            access_token = self.data_service.token_manager.get_valid_access_token(
                connection
            )
            client = NetSuiteAuthClient(
                account_id=connection.netsuite_account_id,
                client_id=connection.client_id,
                client_secret=connection.client_secret,
                access_token=access_token,
            )

            response = self.data_service._call_and_track_health(
                connection,
                client.create_record,
                record_type=NetSuiteRecordType.VENDOR_BILL,
                data=payload,
            )

            record_id = self._extract_record_id(response)
            if not record_id:
                raise ValueError(
                    "NetSuite created a response, but no Vendor Bill "
                    "record ID was returned."
                )

            posting.status = "posted"
            posting.netsuite_record_id = str(record_id)
            posting.response_payload = (
                response if isinstance(response, dict) else {}
            )
            posting.error_message = None
            posting.save(
                update_fields=[
                    "status",
                    "netsuite_record_id",
                    "response_payload",
                    "error_message",
                    "updated_at",
                ]
            )

            return {
                "posting_id": str(posting.id),
                "netsuite_record_id": str(record_id),
                "already_posted": False,
            }

        except Exception as exc:
            logger.exception(
                "Vendor Bill posting failed — document=%s version=%s connection=%s",
                document.id,
                version.id,
                connection.id,
            )
            posting.status = "error"
            posting.error_message = str(exc)[:5000]
            posting.save(
                update_fields=[
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )
            raise

    @staticmethod
    def _extract_record_id(response: dict | None) -> str | None:
        if not isinstance(response, dict):
            return None

        if response.get("id") is not None:
            return str(response["id"])

        for link in response.get("links", []) or []:
            if link.get("rel") == "self" and link.get("href"):
                tail = str(link["href"]).rstrip("/").split("/")
                if tail and tail[-1].isdigit():
                    return tail[-1]

        return None

    
class NetSuiteFieldMappingService:
    """Manage OCR -> NetSuite field mappings and AI-assisted suggestions."""

    MAX_AI_MAPPING_ATTEMPTS = 2
    METADATA_TIMEOUT_SECONDS = 30

    def __init__(self, repository=None, token_manager=None):
        self.repository = repository or NetSuiteConnectionRepository()
        self.token_manager = token_manager or NetSuiteTokenManager(repository=self.repository)

    def _get_connection(self, *, company, connection_id):
        connection = self.repository.get_for_company(
            connection_id=connection_id,
            company=company,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection not found or not accessible."
            )
        if connection.status != "connected" or not connection.is_active:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection is not active."
            )
        return connection

    @staticmethod
    def _merge_baseline_fields(normalized):
        """
        Merge the static AGSuite Vendor Bill baseline with live NetSuite
        metadata.

        Rules:
        - Baseline fields are always available as dropdown targets.
        - Live metadata wins for duplicate field_id + scope.
        - Live metadata supplies account-specific required/custom/reference info.
        - Baseline fields remain optional unless live metadata says required.
        """
        live_body = list(normalized.get("body_fields") or [])
        live_column = list(normalized.get("line_fields") or [])

        live_fields = {}

        for field in [*live_body, *live_column]:
            field_id = str(field.get("field_id") or "").strip()
            if not field_id:
                continue

            scope = (
                "column"
                if str(field.get("scope") or "").lower() in {"line", "column", "sublist"}
                else "body"
            )

            live_fields[(field_id, scope)] = {
                **field,
                "field_id": field_id,
                "scope": scope,
            }

        merged = {}

        for field in VENDOR_BILL_BASELINE_FIELDS:
            field_id = str(field["field_id"])
            scope = (
                "column"
                if str(field.get("scope") or "").lower()
                in {"line", "column", "sublist"}
                else "body"
            )

            baseline_field = {
                **field,
                "field_id": field_id,
                "scope": scope,
                "is_required": False,
                "baseline": True,
            }

            live_field = live_fields.pop(
                (field_id, scope),
                None,
            )

            merged[(field_id, scope)] = (
                {
                    **baseline_field,
                    **live_field,
                    "baseline": True,
                }
                if live_field
                else baseline_field
            )

        # Preserve every account-specific/live field that was not in baseline.
        for key, field in live_fields.items():
            merged[key] = field

        body_fields = [
            field
            for (field_id, scope), field in merged.items()
            if scope == "body"
        ]

        column_fields = [
            field
            for (field_id, scope), field in merged.items()
            if scope == "column"
        ]

        custom_fields = [
            field
            for field in [*body_fields, *column_fields]
            if field.get("is_custom")
        ]

        return {
            "body_fields": body_fields,
            "line_fields": column_fields,
            "custom_fields": custom_fields,
        }

    @staticmethod
    def _account_domain(connection):
        """Build the account-specific SuiteTalk domain from the stored account ID."""
        account_id = str(connection.netsuite_account_id or "").strip()
        if not account_id:
            raise ValueError("NetSuite account ID is missing from the connection.")

        # Sandbox account IDs are commonly stored as 1234567_SB2; the
        # account-specific REST hostname uses 1234567-sb2.
        domain_account = account_id.lower().replace("_", "-")
        domain_account = re.sub(r"[^a-z0-9-]", "", domain_account)
        return f"{domain_account}.suitetalk.api.netsuite.com"

    def _fetch_live_metadata(self, *, connection, record_type):
        """Fetch record metadata directly from NetSuite's REST Metadata Catalog."""
        access_token = self.token_manager.get_valid_access_token(connection)
        base_url = f"https://{self._account_domain(connection)}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/schema+json",
        }

        # NetSuite exposes a record-specific metadata resource. This gives us
        # the actual Vendor Bill schema, including account customizations,
        # instead of only the catalog index.
        direct_url = (
            f"{base_url}/services/rest/record/v1/metadata-catalog/"
            f"{record_type}"
        )
        response = requests.get(
            direct_url,
            headers=headers,
            timeout=self.METADATA_TIMEOUT_SECONDS,
        )

        # Some NetSuite environments expose the selected-record catalog form
        # more readily than the record-specific resource. Fall back to it.
        if response.status_code == 404:
            response = requests.get(
                f"{base_url}/services/rest/record/v1/metadata-catalog/",
                params={"select": record_type},
                headers=headers,
                timeout=self.METADATA_TIMEOUT_SECONDS,
            )

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("NetSuite metadata catalogue returned an invalid response.")
        return payload

    @staticmethod
    def _title_for(field_id, schema):
        if not isinstance(schema, dict):
            return field_id
        return (
            schema.get("title")
            or schema.get("label")
            or schema.get("displayName")
            or schema.get("name")
            or field_id
        )

    @staticmethod
    def _normalise_datatype(schema):
        if not isinstance(schema, dict):
            return "text"
        value = str(
            schema.get("type")
            or schema.get("datatype")
            or schema.get("dataType")
            or "text"
        ).lower()
        fmt = str(schema.get("format") or "").lower()
        if value in {"integer", "number", "decimal"}:
            if "currency" in fmt:
                return "currency"
            return "number"
        if value in {"boolean", "bool"}:
            return "boolean"
        if value in {"date", "datetime"} or fmt in {"date", "date-time"}:
            return "date"
        if value in {"reference", "select", "object"}:
            return "select"
        return "text"

    @staticmethod
    def _reference_type(schema):
        if not isinstance(schema, dict):
            return None
        for key in ("reference", "referenceType", "referenceRecordType", "recordType", "refType"):
            value = schema.get(key)
            if isinstance(value, str) and value.strip():
                value = value.rsplit("/", 1)[-1]
                return value
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.strip():
            return ref.rstrip("/").rsplit("/", 1)[-1]
        return None

    @staticmethod
    def _is_custom_field(field_id, schema):
        if not isinstance(schema, dict):
            schema = {}
        return bool(
            schema.get("custom")
            or schema.get("isCustom")
            or str(field_id).lower().startswith(("custbody_", "custcol_", "custitem_"))
        )

    @classmethod
    def _schema_for_record(cls, raw, record_type):
        """Best-effort extraction of the Vendor Bill schema across metadata shapes."""
        if not isinstance(raw, dict):
            return {}

        if isinstance(raw.get("properties"), dict):
            return raw

        definitions = raw.get("definitions")
        if isinstance(definitions, dict):
            candidate = definitions.get(record_type) or definitions.get("vendorBill")
            if isinstance(candidate, dict):
                return candidate

        components = raw.get("components")
        if isinstance(components, dict):
            schemas = components.get("schemas")
            if isinstance(schemas, dict):
                candidate = schemas.get(record_type) or schemas.get("vendorBill")
                if isinstance(candidate, dict):
                    return candidate

        direct = raw.get(record_type)
        if isinstance(direct, dict):
            return direct

        # Search recursively for a node representing the requested record type.
        stack = [raw]
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            for key, value in node.items():
                if key == record_type and isinstance(value, dict):
                    if isinstance(value.get("properties"), dict):
                        return value
                    stack.append(value)
                elif isinstance(value, dict):
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(item for item in value if isinstance(item, dict))
        return {}

    @classmethod
    def _normalise_metadata(cls, raw, record_type):
        schema = cls._schema_for_record(raw, record_type)
        properties = schema.get("properties") if isinstance(schema, dict) else None
        if not isinstance(properties, dict):
            return {
                "body_fields": [],
                "line_fields": [],
                "custom_fields": [],
                "raw_metadata": raw,
            }

        required = set(schema.get("required", [])) if isinstance(schema.get("required"), list) else set()
        body_fields = []
        line_fields = []
        custom_fields = []

        def append_field(field_id, field_schema, scope, required_set):
            if not isinstance(field_schema, dict):
                field_schema = {}

            # Vendor Bill item sublist: skip the sublist wrapper itself and
            # expose its item properties as line-level fields.
            nested = field_schema.get("properties")
            items_schema = field_schema.get("items")
            if scope == "body" and isinstance(items_schema, dict):
                item_props = items_schema.get("properties")
                if isinstance(item_props, dict):
                    for nested_id, nested_schema in item_props.items():
                        append_field(nested_id, nested_schema, "column", set(items_schema.get("required", []) or []))
                    return
            if isinstance(nested, dict) and scope == "body" and field_id in {"item", "items", "expense"}:
                for nested_id, nested_schema in nested.items():
                    append_field(nested_id, nested_schema, "column", set(field_schema.get("required", []) or []))
                return

            item = {
                "field_id": str(field_id),
                "label": cls._title_for(str(field_id), field_schema),
                "datatype": cls._normalise_datatype(field_schema),
                "scope": scope,
                "is_required": str(field_id) in required_set,
                "is_custom": cls._is_custom_field(str(field_id), field_schema),
                "reference_type": cls._reference_type(field_schema),
            }
            target = line_fields if scope == "column" else body_fields
            target.append(item)
            if item["is_custom"]:
                custom_fields.append(item)

        for field_id, field_schema in properties.items():
            # Sublist containers become line-level field collections.
            lower_id = str(field_id).lower()
            if lower_id in {"item", "expense", "items"}:
                append_field(field_id, field_schema, "body", required)
            else:
                append_field(field_id, field_schema, "body", required)

        def dedupe(fields):
            seen = set()
            out = []
            for field in fields:
                key = (field.get("scope"), field.get("field_id"))
                if key in seen:
                    continue
                seen.add(key)
                out.append(field)
            return out

        body_fields = dedupe(body_fields)
        line_fields = dedupe(line_fields)
        custom_fields = [
            field for field in dedupe(body_fields + line_fields)
            if field.get("is_custom")
        ]
        return {
            "body_fields": body_fields,
            "line_fields": line_fields,
            "custom_fields": custom_fields,
            "raw_metadata": raw,
        }

    def _catalogue_payload(self, catalogue, *, source="database", stale=False, available=True, error=None):

        merged = self._merge_baseline_fields(
                {
                "body_fields": catalogue.body_fields or [],
                "line_fields": catalogue.line_fields or [],
                "custom_fields": catalogue.custom_fields or [],
            }
        )

        return {
            "record_type": catalogue.record_type,
            "fields": {
                "body": merged["body_fields"],
                "column": merged["line_fields"],
            },
            "custom_fields": merged["custom_fields"],
            "fetched_at": catalogue.fetched_at.isoformat() if catalogue.fetched_at else None,
            "source": source,
            "stale": stale,
            "available": available,
            "error": error,
        }

    def get_field_catalogue(
        self,
        *,
        company,
        connection_id,
        record_type="vendorBill",
        force_refresh=False,
    ):
        connection = self._get_connection(
            company=company,
            connection_id=connection_id,
        )

        existing = NetSuiteFieldCatalogue.objects.filter(
            connection=connection,
            record_type=record_type,
        ).first()

        if existing and not force_refresh:
            # Keep AGSuite-created custom fields visible even if a stale/live
            # metadata snapshot predates their creation.
            return self._catalogue_payload(existing, source="database")

        try:
            raw = self._fetch_live_metadata(
                connection=connection,
                record_type=record_type,
            )
            # normalized = self._normalise_metadata(raw, record_type)
            normalized = self._merge_baseline_fields(
                self._normalise_metadata(
                    raw,record_type,
                )
            )

            # Merge fields created by AGSuite if NetSuite metadata has not yet
            # surfaced them in the selected record schema.
            local_custom = list(
                NetSuiteCustomField.objects.filter(
                    company=connection.company,
                    connection=connection,
                    record_type=record_type,
                    status__in=["created", "pending"],
                ).values(
                    "field_id",
                    "field_label",
                    "datatype",
                    "scope",
                    "source_field_key",
                    "source_field_label",
                    "status",
                )
            )
            existing_ids = {
                field.get("field_id")
                for field in (normalized["body_fields"] + normalized["line_fields"])
            }
            for field in local_custom:
                mapped = {
                    "field_id": str(field["field_id"]),
                    "label": field["field_label"],
                    "datatype": field["datatype"],
                    "scope": "column" if field["scope"] == "column" else "body",
                    "is_required": False,
                    "is_custom": True,
                    "reference_type": None,
                }
                if mapped["field_id"] not in existing_ids:
                    if mapped["scope"] == "column":
                        normalized["line_fields"].append(mapped)
                    else:
                        normalized["body_fields"].append(mapped)
                    normalized["custom_fields"].append(mapped)

            metadata_hash = hashlib.sha256(
                json.dumps(raw, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()

            catalogue, _ = NetSuiteFieldCatalogue.objects.update_or_create(
                connection=connection,
                record_type=record_type,
                defaults={
                    "body_fields": normalized["body_fields"],
                    "line_fields": normalized["line_fields"],
                    "custom_fields": normalized["custom_fields"],
                    "raw_metadata": raw,
                    "metadata_hash": metadata_hash,
                },
            )
            return self._catalogue_payload(catalogue, source="netsuite", stale=False)

        except Exception as exc:
            logger.exception(
                "Failed to fetch NetSuite metadata catalogue — connection=%s record_type=%s",
                connection.id,
                record_type,
            )
            if existing:
                return self._catalogue_payload(
                    existing,
                    source="database",
                    stale=True,
                    available=True,
                    error=str(exc),
                )

            # Development-safe fallback: retain the current hardcoded baseline
            # so the mapping screen still works while the live API is repaired.
            # fields = self._build_standard_catalogue(record_type)
            fields = self._merge_baseline_fields(
                {
                    "body_fields": [],
                    "line_fields": [],
                    "custom_fields": [],
                }
            )
            custom_fields = list(
                NetSuiteCustomField.objects.filter(
                    company=connection.company,
                    connection=connection,
                    record_type=record_type,
                ).values(
                    'field_id', 'field_label', 'datatype', 'scope',
                    'source_field_key', 'source_field_label', 'status',
                )
            )
            return {
                "record_type": record_type,
                "fields": fields,
                "custom_fields": custom_fields,
                "source": "fallback",
                "stale": False,
                "available": False,
                "error": str(exc),
                "fetched_at": None,
            }

    def _build_standard_catalogue(self, record_type):
        """Development fallback catalogue only; live metadata is preferred."""
        body_fields = [
            {'field_id': 'entity', 'label': 'Vendor', 'datatype': 'select', 'scope': 'body', 'is_required': True, 'is_custom': False, 'reference_type': 'vendor'},
            {'field_id': 'tranid', 'label': 'Transaction ID / Reference', 'datatype': 'text', 'scope': 'body', 'is_required': False, 'is_custom': False},
            {'field_id': 'trandate', 'label': 'Transaction Date', 'datatype': 'date', 'scope': 'body', 'is_required': True, 'is_custom': False},
            {'field_id': 'duedate', 'label': 'Due Date', 'datatype': 'date', 'scope': 'body', 'is_required': False, 'is_custom': False},
            {'field_id': 'currency', 'label': 'Currency', 'datatype': 'select', 'scope': 'body', 'is_required': True, 'is_custom': False},
            {'field_id': 'memo', 'label': 'Memo', 'datatype': 'text', 'scope': 'body', 'is_required': False, 'is_custom': False},
            {'field_id': 'otherrefnum', 'label': 'Other Reference Number', 'datatype': 'text', 'scope': 'body', 'is_required': False, 'is_custom': False},
            {'field_id': 'subsidiary', 'label': 'Subsidiary', 'datatype': 'select', 'scope': 'body', 'is_required': True, 'is_custom': False},
            {'field_id': 'location', 'label': 'Location', 'datatype': 'select', 'scope': 'body', 'is_required': False, 'is_custom': False},
            {'field_id': 'department', 'label': 'Department', 'datatype': 'select', 'scope': 'body', 'is_required': False, 'is_custom': False},
            {'field_id': 'class', 'label': 'Class', 'datatype': 'select', 'scope': 'body', 'is_required': False, 'is_custom': False},
        ]
        item_fields = [
            {'field_id': 'item', 'label': 'Item', 'datatype': 'select', 'scope': 'column', 'is_required': True, 'is_custom': False, 'reference_type': 'item'},
            {'field_id': 'description', 'label': 'Item Description', 'datatype': 'text', 'scope': 'column', 'is_required': False, 'is_custom': False},
            {'field_id': 'quantity', 'label': 'Quantity', 'datatype': 'decimal', 'scope': 'column', 'is_required': True, 'is_custom': False},
            {'field_id': 'rate', 'label': 'Rate', 'datatype': 'currency', 'scope': 'column', 'is_required': True, 'is_custom': False},
            {'field_id': 'amount', 'label': 'Amount', 'datatype': 'currency', 'scope': 'column', 'is_required': False, 'is_custom': False},
            {'field_id': 'custcol_hsnsac', 'label': 'HSN/SAC', 'datatype': 'text', 'scope': 'column', 'is_required': False, 'is_custom': True},
        ]
        return {'body': body_fields, 'column': item_fields}

    def suggest_mappings(
        self,
        *,
        company,
        connection_id,
        record_type,
        source_fields,
    ):
        """Generate safe AI mappings with at most two targeted attempts."""
        catalogue = self.get_field_catalogue(
            company=company,
            connection_id=connection_id,
            record_type=record_type,
        )

        # One authoritative target collection. Custom fields are already
        # contained in body/column, so do not append custom_fields again.
        all_targets = (
            catalogue.get("fields", {}).get("body", [])
            + catalogue.get("fields", {}).get("column", [])
        )

        target_by_key = {}
        for target in all_targets:
            field_id = str(target.get("field_id") or "").strip()
            if not field_id:
                continue
            target_scope = (
                "column"
                if str(target.get("scope") or "").lower()
                in {"line", "column", "sublist"}
                else "body"
            )
            target_by_key[(field_id.casefold(), target_scope)] = target

        all_targets = list(target_by_key.values())
        original_sources = list(source_fields or [])

        if not original_sources:
            return []

        locked_mappings = {}
        latest_unresolved = {}
        pending_sources = original_sources
        last_error = None
        attempts_used = 0

        for attempt in range(1, self.MAX_AI_MAPPING_ATTEMPTS + 1):
            if not pending_sources:
                break

            attempts_used = attempt

            try:
                # Previous successful mappings are LOCKED. The second attempt
                # receives only the still unresolved source fields.
                previous_attempt = list(locked_mappings.values())

                result = self._ai_suggest_mappings(
                    source_fields=pending_sources,
                    targets=all_targets,
                    record_type=record_type,
                    previous_attempt=previous_attempt,
                )

                validated = self._validate_ai_mappings(
                    result,
                    source_fields=pending_sources,
                    targets=all_targets,
                )

                for item in validated:
                    source_key = item["source_field_key"]
                    if item["status"] == "MAPPED":
                        locked_mappings[source_key] = item
                        latest_unresolved.pop(source_key, None)
                    else:
                        latest_unresolved[source_key] = item

                pending_keys = {
                    item["source_field_key"]
                    for item in validated
                    if item["status"] in {"AMBIGUOUS", "UNRESOLVED"}
                }

                pending_sources = [
                    source
                    for source in pending_sources
                    if str(
                        source.get("key")
                        or source.get("field_key")
                        or ""
                    ) in pending_keys
                ]

            except Exception as exc:
                last_error = exc
                logger.exception(
                    "AI field mapping attempt failed — attempt=%s/%s connection=%s",
                    attempt,
                    self.MAX_AI_MAPPING_ATTEMPTS,
                    connection_id,
                )

                # If the first call failed before producing a usable response,
                # the second call is a genuine retry of the full remaining set.
                if attempt == 1:
                    pending_sources = [
                        source
                        for source in original_sources
                        if str(
                            source.get("key")
                            or source.get("field_key")
                            or ""
                        ) not in locked_mappings
                    ]

        final_results = []
        for source in original_sources:
            source_key = str(
                source.get("key")
                or source.get("field_key")
                or ""
            )

            item = locked_mappings.get(source_key)
            if item is None:
                item = latest_unresolved.get(source_key)

            if item is None:
                item = {
                    "source_field_key": source_key,
                    "source_field_label": source.get("label") or source_key,
                    "source_scope": source.get("scope") or "header",
                    "source_datatype": source.get("datatype") or "text",
                    "target_field_id": None,
                    "target_field_label": None,
                    "target_scope": None,
                    "target_datatype": None,
                    "is_required": False,
                    "is_custom": False,
                    "reference_type": None,
                    "status": "UNRESOLVED",
                    "confidence": None,
                    "suggested_target": None,
                    "candidates": [],
                }

            item = dict(item)
            metadata = dict(item.get("metadata") or {})
            metadata["ai_attempts_used"] = attempts_used
            item["metadata"] = metadata
            final_results.append(item)

        # Deterministic matching is used only when Gemini itself was unavailable
        # or returned an unusable response. A valid AI response with unresolved
        # fields remains unresolved rather than being silently guessed.
        if last_error and not locked_mappings:
            fallback = self._rule_based_suggestions(
                source_fields=original_sources,
                all_targets=all_targets,
            )
            for item in fallback:
                metadata = dict(item.get("metadata") or {})
                metadata.update(
                    {
                        "ai_fallback": True,
                        "ai_error": str(last_error)[:500],
                        "ai_attempts_used": attempts_used,
                    }
                )
                item["metadata"] = metadata
            return fallback

        return final_results

    @staticmethod
    def _parse_ai_json(response_text):
        text = str(response_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("mappings"), list):
            return parsed["mappings"]
        if isinstance(parsed, list):
            return parsed
        raise ValueError("AI mapping response did not contain a mappings list.")

    def _ai_suggest_mappings(
        self,
        *,
        source_fields,
        targets,
        record_type,
        previous_attempt=None,
    ):
        from google import genai
        from google.genai import types

        model = (
            getattr(settings, "GEMINI_MAPPING_MODEL", None)
            or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        )

        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise RuntimeError(
                "Gemini API key is not configured for AI field mapping."
            )

        client = genai.Client(api_key=api_key)

        prompt = {
            "record_type": record_type,
            "instructions": [
                "Map AGSuite OCR application fields to NetSuite Vendor Bill fields.",
                "Return exactly one mapping object for every supplied application field.",
                "Use ONLY exact NetSuite field IDs present in the supplied catalogue.",
                "Never invent, rename, shorten, normalize, or fabricate a NetSuite field ID.",
                "Match by semantic meaning, not just word overlap.",
                "Use these Vendor Bill semantic priors when applicable, but always verify the exact target against the supplied account catalogue:",
                "vendor_name normally maps to the Vendor/entity reference.",
                "invoice_date normally maps to trandate/transaction date.",
                "due_date normally maps to duedate.",
                "subsidiary normally maps to subsidiary.",
                "currency normally maps to currency.",
                "quantity normally maps to the item-line quantity field.",
                "unit_price normally maps to the item-line rate field.",
                "amount normally maps to the item-line amount field.",
                "line description normally maps to the item-line description field; do not map a line description to the body memo unless no safe line field exists.",
                "invoice_number is a transaction/reference concept; prefer an exact account field labelled for invoice/reference number over an unrelated custom field.",
                "customer_name must not be treated as vendor_name; map it only when the account catalogue contains a semantically correct customer target.",
                "A body/header application field may map only to a body NetSuite target.",
                "A line application field may map only to a column/line NetSuite target.",
                "Respect datatype compatibility and reference_type whenever provided.",
                "Never map a field merely because the target is required.",
                "For MAPPED, target_field_id must be an exact catalogue field ID.",
                "For AMBIGUOUS, do not guess; leave target_field_id empty and return candidate target IDs when useful.",
                "For UNRESOLVED, leave target_field_id empty.",
                "On attempt 2, previous MAPPED mappings are locked and must not be changed.",
                "On attempt 2, focus only on the currently supplied unresolved/ambiguous fields.",
                "If the semantic match is not safe, prefer UNRESOLVED over an unsafe guess.",
            ],
            "output_format": {
                "status_values": ["MAPPED", "AMBIGUOUS", "UNRESOLVED"],
                "fields": [
                    "source_field_key",
                    "status",
                    "target_field_id",
                    "confidence",
                ],
                "rule": "Return target_field_id as an empty string when status is AMBIGUOUS or UNRESOLVED.",
            },
            "application_fields": source_fields,
            "netsuite_fields": targets,
            "previous_attempt": previous_attempt or [],
        }

        response = client.models.generate_content(
            model=model,
            contents=json.dumps(
                prompt,
                ensure_ascii=False,
                default=str,
            ),
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema={
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "source_field_key": {"type": "STRING"},
                            "status": {
                                "type": "STRING",
                                "enum": [
                                    "MAPPED",
                                    "AMBIGUOUS",
                                    "UNRESOLVED",
                                ],
                            },
                            "target_field_id": {"type": "STRING"},
                            "confidence": {"type": "NUMBER"},
                        },
                        "required": [
                            "source_field_key",
                            "status",
                            "target_field_id",
                            "confidence",
                        ],
                    },
                },
            ),
        )

        return self._parse_ai_json(response.text)

    @staticmethod
    def _validate_ai_mappings(result, *, source_fields, targets):
        if not isinstance(result, list):
            raise ValueError(
                "AI mapping response must be a list."
            )

        def normalize_scope(scope):
            value = str(scope or "").strip().lower()
            return "column" if value in {"line", "column", "sublist"} else "body"

        source_map = {
            str(
                source.get("key")
                or source.get("field_key")
            ): source
            for source in source_fields
            if source.get("key") or source.get("field_key")
        }

        target_map = {}
        for target in targets:
            field_id = str(target.get("field_id") or "").strip()
            if not field_id:
                continue
            scope = normalize_scope(target.get("scope"))
            target_map[(field_id.casefold(), scope)] = target

        normalized = []
        seen_sources = set()

        for item in result:
            if not isinstance(item, dict):
                continue

            source_key = (
                item.get("source_field_key")
                or item.get("source_key")
                or item.get("source_field")
            )
            if not source_key:
                continue

            source_key = str(source_key)
            if source_key not in source_map:
                # Ignore hallucinated source fields, but do not invalidate
                # otherwise useful mappings.
                continue

            seen_sources.add(source_key)

            source = source_map[source_key]
            source_scope_raw = source.get("scope") or "header"
            expected_target_scope = normalize_scope(source_scope_raw)

            status = str(
                item.get("status")
                or item.get("mapping_status")
                or "UNRESOLVED"
            ).upper()
            if status not in {"MAPPED", "AMBIGUOUS", "UNRESOLVED"}:
                status = "UNRESOLVED"

            confidence = item.get("confidence")
            candidates = item.get("candidates") or []

            target_id = (
                item.get("target_field_id")
                or item.get("suggested_target_id")
                or item.get("target_field")
            )

            nested_target = (
                item.get("suggested_target")
                or item.get("target")
            )

            if isinstance(target_id, dict):
                target_id = (
                    target_id.get("field_id")
                    or target_id.get("id")
                    or target_id.get("internal_id")
                )

            if not target_id and isinstance(nested_target, dict):
                target_id = (
                    nested_target.get("field_id")
                    or nested_target.get("id")
                    or nested_target.get("internal_id")
                )

            if isinstance(target_id, str):
                target_id = target_id.strip()

            target = None
            if target_id:
                target = target_map.get(
                    (
                        str(target_id).casefold(),
                        expected_target_scope,
                    )
                )

            base = {
                "source_field_key": source_key,
                "source_field_label": (
                    item.get("source_field_label")
                    or source.get("label")
                    or source_key
                ),
                "source_scope": source_scope_raw,
                "source_datatype": (
                    source.get("datatype")
                    or "text"
                ),
                "target_field_id": None,
                "target_field_label": None,
                "target_scope": None,
                "target_datatype": None,
                "is_required": False,
                "is_custom": False,
                "reference_type": None,
                "status": "UNRESOLVED",
                "confidence": confidence,
                "suggested_target": None,
                "candidates": candidates,
            }

            if status == "MAPPED" and target is not None:
                base.update(
                    {
                        "target_field_id": str(target["field_id"]),
                        "target_field_label": (
                            target.get("label")
                            or target.get("field_id")
                        ),
                        "target_scope": target.get("scope") or expected_target_scope,
                        "target_datatype": target.get("datatype") or "text",
                        "is_required": bool(target.get("is_required")),
                        "is_custom": bool(target.get("is_custom")),
                        "reference_type": target.get("reference_type"),
                        "status": "MAPPED",
                        "suggested_target": target,
                    }
                )
            elif status == "AMBIGUOUS":
                base["status"] = "AMBIGUOUS"

            normalized.append(base)

        # AI is allowed to omit a source field; surface that as unresolved so
        # the next attempt can explicitly retry it.
        for source_key, source in source_map.items():
            if source_key in seen_sources:
                continue
            normalized.append(
                {
                    "source_field_key": source_key,
                    "source_field_label": source.get("label") or source_key,
                    "source_scope": source.get("scope") or "header",
                    "source_datatype": source.get("datatype") or "text",
                    "target_field_id": None,
                    "target_field_label": None,
                    "target_scope": None,
                    "target_datatype": None,
                    "is_required": False,
                    "is_custom": False,
                    "reference_type": None,
                    "status": "UNRESOLVED",
                    "confidence": None,
                    "suggested_target": None,
                    "candidates": [],
                }
            )

        order = {
            key: index
            for index, key in enumerate(source_map)
        }
        normalized.sort(
            key=lambda item: order.get(
                item["source_field_key"],
                len(order),
            )
        )
        return normalized

    def _rule_based_suggestions(self, *, source_fields, all_targets):
        suggestions = []
        for source in source_fields:
            source_key = source.get('key') or source.get('field_key')
            source_label = source.get('label') or source.get('field_label', source_key)
            source_scope = source.get('scope', 'header')
            source_datatype = source.get('datatype', 'text')
            candidates = self._rank_candidates(
                source_label=source_label,
                source_scope=source_scope,
                source_datatype=source_datatype,
                targets=all_targets,
            )
            if not candidates:
                status = 'UNRESOLVED'
                best = None
            elif len(candidates) == 1 or candidates[0].get('score', 0) >= 0.8:
                status = 'MAPPED'
                best = candidates[0]
            else:
                status = 'AMBIGUOUS'
                best = candidates[0]
            suggestions.append({
                'source_field_key': source_key,
                'source_field_label': source_label,
                'source_scope': source_scope,
                'source_datatype': source_datatype,
                'status': status,
                'suggested_target': best,
                'candidates': candidates[:5],
            })
        return suggestions

    def _rank_candidates(self, *, source_label, source_scope, source_datatype, targets):
        ranked = []
        source_lower = source_label.lower().strip()
        scope_map = {'header': 'body', 'line': 'column'}
        expected_scope = scope_map.get(source_scope, source_scope)
        for target in targets:
            target_scope = target.get('scope', 'body')
            if expected_scope != target_scope:
                continue
            target_label = target.get('label', '').lower().strip()
            target_id = target.get('field_id', '').lower()
            target_dtype = target.get('datatype', 'text').lower()
            score = 0.0
            if source_lower == target_label or source_lower == target_id:
                score = 1.0
            elif source_lower in target_label or target_label in source_lower:
                score = 0.9
            elif self._semantic_similarity(source_lower, target_label) > 0.7:
                score = 0.8
            elif source_lower in target_id or target_id in source_lower:
                score = 0.7
            if not self._datatype_compatible(source_datatype, target_dtype):
                score = max(0.0, score - 0.5)
            if score > 0:
                ranked.append({**target, 'score': score})
        ranked.sort(key=lambda x: x.get('score', 0), reverse=True)
        return ranked

    @staticmethod
    def _semantic_similarity(a, b):
        """Rough word-overlap similarity for short labels."""
        a_words = set(a.split())
        b_words = set(b.split())
        if not a_words or not b_words:
            return 0.0
        intersection = a_words & b_words
        return len(intersection) / max(len(a_words | b_words), 1)

    @staticmethod
    def _datatype_compatible(source_dtype, target_dtype):
        compatible = {
            'text': {'text', 'select'},
            'number': {'decimal', 'integer', 'number', 'currency'},
            'date': {'date'},
            'boolean': {'checkbox', 'boolean'},
            'currency': {'currency', 'decimal', 'number'},
        }
        allowed = compatible.get(str(source_dtype).lower(), set())
        return str(target_dtype).lower() in allowed or str(target_dtype).lower() == 'text'

    @transaction.atomic
    def save_mappings(self, *, company, connection_id, record_type, mappings):
        """Persist only valid, connection-specific mappings."""
        connection = self._get_connection(
            company=company,
            connection_id=connection_id,
        )

        # Validate all target IDs against the same account that owns the mapping.
        catalogue = self.get_field_catalogue(
            company=company,
            connection_id=connection.id,
            record_type=record_type,
        )
        catalogue_fields = (
            catalogue.get("fields", {}).get("body", [])
            + catalogue.get("fields", {}).get("column", [])
        )

        def normalize_source_scope(scope):
            return "line" if str(scope or "").lower() in {"line", "column", "sublist"} else "header"

        def normalize_target_scope(scope):
            return "column" if str(scope or "").lower() in {"line", "column", "sublist"} else "body"

        target_map = {
            (
                str(field.get("field_id")).casefold(),
                normalize_target_scope(field.get("scope")),
            ): field
            for field in catalogue_fields
            if field.get("field_id")
        }

        saved = []

        for mapping in mappings:
            source_key = str(
                mapping.get("source_field_key") or ""
            ).strip()
            if not source_key:
                continue

            target_field_id = str(
                mapping.get("target_field_id") or ""
            ).strip()

            # Unresolved fields are intentionally not persisted because the DB
            # requires a non-null target_field_id. Remove stale mappings instead.
            if not target_field_id:
                (
                    OCRNetSuiteFieldMapping.objects
                    .filter(
                        company=company,
                        connection=connection,
                        record_type=record_type,
                        source_field_key=source_key,
                    )
                    .delete()
                )
                continue

            source_scope = normalize_source_scope(
                mapping.get("source_scope")
            )
            target_scope = normalize_target_scope(
                mapping.get("target_scope")
            )

            # The line/header relationship is authoritative: a line source must
            # never be saved against a body target, and vice versa.
            if target_scope == "column" and source_scope != "line":
                raise ValueError(
                    f"Invalid mapping scope for '{source_key}': a line NetSuite field requires a line application field."
                )

            if target_scope == "body" and source_scope == "line":
                raise ValueError(
                    f"Invalid mapping scope for '{source_key}': a line application field cannot map to a body NetSuite field."
                )

            target = target_map.get(
                (target_field_id.casefold(), target_scope)
            )
            if target is None:
                raise ValueError(
                    f"NetSuite field '{target_field_id}' is not available in the selected connection."
                )

            obj, _ = OCRNetSuiteFieldMapping.objects.update_or_create(
                company=company,
                connection=connection,
                record_type=record_type,
                source_field_key=source_key,
                defaults={
                    "source_field_label": (
                        mapping.get("source_field_label")
                        or source_key
                    ),
                    "source_scope": source_scope,
                    "source_datatype": (
                        mapping.get("source_datatype")
                        or "text"
                    ),
                    "target_field_id": str(target["field_id"]),
                    "target_field_label": (
                        target.get("label")
                        or target["field_id"]
                    ),
                    "target_scope": target_scope,
                    "target_datatype": (
                        target.get("datatype")
                        or "text"
                    ),
                    # Account-specific metadata is authoritative.
                    "is_required": bool(
                        target.get("is_required")
                    ),
                    "is_custom": bool(
                        target.get("is_custom")
                    ),
                    "reference_type": target.get(
                        "reference_type"
                    ),
                    "mapping_status": "MAPPED",
                    "confidence": mapping.get(
                        "confidence"
                    ),
                    "metadata": mapping.get(
                        "metadata"
                    ) or {},
                },
            )
            saved.append(obj)

        return saved

    def get_mappings(self, *, company, connection_id, record_type):
        connection = self.repository.get_for_company(
            connection_id=connection_id,
            company=company,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection not found."
            )

        return (
            OCRNetSuiteFieldMapping.objects
            .filter(
                company=company,
                connection=connection,
                record_type=record_type,
            )
            .select_related("company", "connection")
            .order_by("updated_at", "source_field_key")
        )

class NetSuiteValidationService:
    """
    Validate extracted OCR data against NetSuite reference data.

    Matching is deliberately fail-closed for financial posting:

    ROUND 1
        Exact normalized name match.
        Exactly one candidate -> MATCHED.
        Multiple exact candidates -> AMBIGUOUS.

    ROUND 2
        Similar-name matching is considered only when round 1 has zero
        candidates. A candidate must clear the similarity threshold.
        Multiple candidates that are too close to the best score -> AMBIGUOUS.
        No safe candidate -> NOT_FOUND.

    A guessed vendor/item is never accepted as a valid match.
    """

    SIMILARITY_THRESHOLD = 0.86
    AMBIGUITY_SCORE_GAP = 0.03
    MAX_SIMILAR_CANDIDATES = 5

    ITEM_RECORD_TYPES = (
        NetSuiteRecordType.INVENTORY_ITEM,
        NetSuiteRecordType.NON_INVENTORY_SALE_ITEM,
        NetSuiteRecordType.NON_INVENTORY_RESALE_ITEM,
        NetSuiteRecordType.NON_INVENTORY_PURCHASE_ITEM,
        NetSuiteRecordType.SERVICE_SALE_ITEM,
        NetSuiteRecordType.SERVICE_RESALE_ITEM,
        NetSuiteRecordType.SERVICE_PURCHASE_ITEM,
        NetSuiteRecordType.DESCRIPTION_ITEM,
        NetSuiteRecordType.DISCOUNT_ITEM,
        NetSuiteRecordType.KIT_ITEM,
        NetSuiteRecordType.ASSEMBLY_ITEM,
        NetSuiteRecordType.MARKUP_ITEM,
        NetSuiteRecordType.PAYMENT_ITEM,
        NetSuiteRecordType.SUBTOTAL_ITEM,
        NetSuiteRecordType.ITEM_GROUP,
    )
    ITEM_SUITEQL_TABLES = {
        NetSuiteRecordType.INVENTORY_ITEM: "inventoryitem",
        NetSuiteRecordType.NON_INVENTORY_SALE_ITEM: "noninventoryitem",
        NetSuiteRecordType.NON_INVENTORY_RESALE_ITEM: "noninventoryitem",
        NetSuiteRecordType.NON_INVENTORY_PURCHASE_ITEM: "noninventoryitem",
        NetSuiteRecordType.SERVICE_SALE_ITEM: "serviceitem",
        NetSuiteRecordType.SERVICE_RESALE_ITEM: "serviceitem",
        NetSuiteRecordType.SERVICE_PURCHASE_ITEM: "serviceitem",
        NetSuiteRecordType.DESCRIPTION_ITEM: "descriptionitem",
        NetSuiteRecordType.DISCOUNT_ITEM: "discountitem",
        NetSuiteRecordType.KIT_ITEM: "kititem",
        NetSuiteRecordType.ASSEMBLY_ITEM: "assemblyitem",
        NetSuiteRecordType.MARKUP_ITEM: "markupitem",
        NetSuiteRecordType.PAYMENT_ITEM: "paymentitem",
        NetSuiteRecordType.SUBTOTAL_ITEM: "subtotalitem",
        NetSuiteRecordType.ITEM_GROUP: "itemgroup",
    }

    def __init__(self, repository=None, token_manager=None):
        self.repository = repository or NetSuiteConnectionRepository()
        self.token_manager = token_manager or NetSuiteTokenManager(
            repository=self.repository,
        )
    
    @staticmethod
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
        
    @staticmethod
    def _suiteql_literal(value):
        value = str(value or "").strip()

        if not value:
            return None

        # Escape SQL single quotes safely.
        # OCR/user supplied values must never be interpolated raw.
        return "'" + value.replace("'", "''") + "'"

    def _execute_live_suiteql(
        self,
        *,
        connection,
        query,
        limit=100,
    ):
        try:
            access_token = self.token_manager.get_valid_access_token(
                connection,
            )

            client = NetSuiteAuthClient(
                account_id=connection.netsuite_account_id,
                client_id=connection.client_id,
                client_secret=connection.client_secret,
                access_token=access_token,
            )

            return client.execute_suiteql(
                query=query,
                limit=limit,
                offset=0,
            )

        except Exception as exc:
            logger.exception(
                "Live NetSuite SuiteQL validation failed — connection=%s",
                connection.id,
            )
            raise NetSuiteRecordFetchException(
                "Unable to validate OCR data against NetSuite."
            ) from exc

    # NetSuite "select"/reference body fields commonly mapped on a Vendor
    # Bill. Each entry is (SuiteQL table name, columns to match the OCR
    # text value against). Required on OneWorld (multi-subsidiary)
    # accounts: creating ANY transaction record without a valid
    # `subsidiary` reference is rejected by NetSuite, and `currency` is
    # very often required too — this table lets us resolve the mapped
    # OCR text value into the internal ID NetSuite's REST API expects
    # ({"id": "<internal id>"}), the same way vendor/item are already
    # resolved live via SuiteQL rather than the (currently unpopulated)
    # NetSuiteReferenceRecord cache.
    SELECT_FIELD_SUITEQL_TABLES = {
        "subsidiary": ("subsidiary", ("name",)),
        "currency": ("currency", ("name", "symbol")),
        "location": ("location", ("name",)),
        "department": ("department", ("name",)),
        "class": ("classification", ("name",)),
        "terms": ("term", ("name",)),
        "term": ("term", ("name",)),
    }

    def _resolve_select_field_live(
        self,
        *,
        connection,
        target_field_id,
        value,
    ):
        """
        Resolve a mapped NetSuite "select" body field (Subsidiary,
        Currency, Location, Department, Class, Terms) from its OCR text
        value to a NetSuite internal ID.

        Returns the internal ID string on a single unambiguous match,
        None if the field isn't a recognized reference field or no
        active match was found, and raises NetSuiteRecordFetchException
        only on an actual NetSuite/network failure (never on "not
        found" — that is a data problem for the caller to report
        clearly, not a transport error).
        """
        table_config = self.SELECT_FIELD_SUITEQL_TABLES.get(
            str(target_field_id or "").strip().lower()
        )
        if table_config is None:
            return None

        table, match_columns = table_config

        raw_value = str(value or "").strip()
        if not raw_value:
            return None

        literal = self._suiteql_literal(raw_value)
        if literal is None:
            return None

        where_clause = " OR ".join(
            f"LOWER({column}) = LOWER({literal})"
            for column in match_columns
        )

        query = f"""
            SELECT id, {", ".join(match_columns)}, isinactive
            FROM {table}
            WHERE {where_clause}
            ORDER BY id
        """

        try:
            response = self._execute_live_suiteql(
                connection=connection,
                query=query,
                limit=10,
            )
        except Exception as exc:
            logger.exception(
                "Live NetSuite %s lookup failed — connection=%s value=%r",
                table,
                connection.id,
                raw_value,
            )
            raise NetSuiteRecordFetchException(
                f'Unable to look up NetSuite {table} "{raw_value}" '
                "in the selected account."
            ) from exc

        rows = (
            response.get("items", [])
            if isinstance(response, dict)
            else []
        )

        matches = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("isinactive", "F")).upper() == "T":
                continue
            record_id = row.get("id")
            if record_id is None:
                continue
            matches.append(str(record_id))

        # Same internal ID can appear once per matched column; dedupe.
        matches = list(dict.fromkeys(matches))

        if not matches:
            logger.info(
                "No active NetSuite %s match found — connection=%s value=%r",
                table,
                connection.id,
                raw_value,
            )
            return None

        if len(matches) > 1:
            logger.warning(
                "Multiple NetSuite %s matches found; using first — "
                "value=%r ids=%s connection=%s",
                table,
                raw_value,
                matches,
                connection.id,
            )

        return matches[0]

    @staticmethod
    def _normalize_match_name(value):
        """
        Normalize a business name for conservative matching.

        Keeps alphanumeric content, collapses whitespace, and removes
        punctuation differences without inventing abbreviations or synonyms.
        """
        if value is None:
            return ""

        normalized = str(value).strip().casefold()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return " ".join(normalized.split())

    @classmethod
    def _similarity_score(cls, left, right):
        left_normalized = cls._normalize_match_name(left)
        right_normalized = cls._normalize_match_name(right)

        if not left_normalized or not right_normalized:
            return 0.0

        if left_normalized == right_normalized:
            return 1.0

        sequence_score = SequenceMatcher(
            None,
            left_normalized,
            right_normalized,
        ).ratio()

        left_words = set(left_normalized.split())
        right_words = set(right_normalized.split())

        if not left_words or not right_words:
            return sequence_score

        overlap_score = len(left_words & right_words) / max(
            len(left_words),
            len(right_words),
        )

        # Keep exact-ish sequence similarity dominant while allowing common
        # word-order/spacing variations to participate safely.
        return max(
            sequence_score,
            (sequence_score * 0.7) + (overlap_score * 0.3),
        )

    @classmethod
    def _rank_similar_records(cls, records, extracted_name):
        scored = []

        for record in records:
            record_name = record.search_name or record.name or ""
            score = cls._similarity_score(extracted_name, record_name)

            if score >= cls.SIMILARITY_THRESHOLD:
                scored.append(
                    {
                        "record": record,
                        "score": round(score, 4),
                    }
                )

        scored.sort(
            key=lambda item: (
                -item["score"],
                str(item["record"].internal_id),
            )
        )

        return scored[: cls.MAX_SIMILAR_CANDIDATES]

    @classmethod
    def _resolve_ranked_candidate(
        cls,
        *,
        scored,
        extracted_name,
        line_index=None,
        extra=None,
    ):
        base = {
            "matched": False,
            "ambiguous": False,
            "netsuite_id": None,
            "extracted_name": extracted_name,
            "round": 2,
        }

        if line_index is not None:
            base["line_index"] = line_index

        if extra:
            base.update(extra)

        if not scored:
            return base

        best = scored[0]
        record = best["record"]
        best_score = best["score"]

        close_candidates = [
            candidate
            for candidate in scored
            if best_score - candidate["score"] <= cls.AMBIGUITY_SCORE_GAP
        ]

        if len(close_candidates) > 1:
            base.update(
                {
                    "ambiguous": True,
                    "round": 2,
                    "confidence": best_score,
                    "candidates": [
                        {
                            "netsuite_id": str(item["record"].internal_id),
                            "name": item["record"].name,
                            "score": item["score"],
                            **(
                                {
                                    "record_type": item["record"].item_type,
                                }
                                if getattr(item["record"], "item_type", None)
                                else {}
                            ),
                        }
                        for item in close_candidates
                    ],
                }
            )
            return base

        base.update(
            {
                "matched": True,
                "netsuite_id": str(record.internal_id),
                "round": 2,
                "confidence": best_score,
            }
        )

        return base
    
    def validate_document(
        self,
        *,
        document_id,
        connection_id,
        user,
    ):
        """
        Reuse the same Vendor + Item reference validation used by
        the Continue preflight and by Validate Again.
    
        Keep both entry points on one validation implementation so
        their matching behavior cannot drift apart.
        """
        return self.check_references(
            document_id=document_id,
            connection_id=connection_id,
            user=user,
        )

    def check_references(
        self,
        *,
        document_id,
        connection_id,
        user,
    ):
        from ocr.models import OCRDocument, OCRDocumentVersion

        company = getattr(user, "company", None)
        if company is None:
            raise ValueError(
                "Your account is not associated with a company."
            )

        company_lifecycle_service.ensure_operational(company=company)

        if self._is_company_admin(user):
            document = (
                OCRDocument.objects
                .filter(
                    pk=document_id,
                    company_id=user.company_id,
                )
                .first()
            )
        else:
            document = (
                OCRDocument.objects
                .filter(
                    pk=document_id,
                    company_id=user.company_id,
                    user=user,
                )
                .first()
            )

        if document is None:
            raise ValueError(
                "OCR document not found or access is not allowed."
            )

        version = (
            OCRDocumentVersion.objects
            .filter(document=document)
            .order_by("-version_number")
            .first()
        )

        if version is None:
            raise ValueError("No OCR version exists for this document.")

        data = (
            version.reviewed_json
            if isinstance(version.reviewed_json, dict)
            and version.reviewed_json
            else version.normalized_json
        )

        if not isinstance(data, dict):
            raise ValueError("OCR data is not valid JSON.")

        connection = self.repository.get_authorized_for_user(
            user=user,
            connection_id=connection_id,
        )
        if connection is None:
            raise ValueError("No NetSuite connection available.")

        if (
            connection.status != "connected"
            or not connection.is_active
        ):
            raise ValueError(
                "NetSuite connection is not active."
            )

        mappings = list(
            OCRNetSuiteFieldMapping.objects.filter(
                company=company,
                connection=connection,
                record_type="vendorBill",
                mapping_status="MAPPED",
            )
        )

        vendor_mapping = next(
            (
                mapping
                for mapping in mappings
                if str(mapping.target_field_id).lower()
                in {"entity", "vendor"}
                and str(mapping.source_scope).lower()
                in {"header", "body"}
            ),
            None,
        )

        item_mapping = next(
            (
                mapping
                for mapping in mappings
                if str(mapping.target_field_id).lower() == "item"
                and str(mapping.source_scope).lower() == "line"
            ),
            None,
        )

        if vendor_mapping is None:
            raise ValueError(
                "Vendor field mapping is required before NetSuite reference validation."
            )

        # if item_mapping is None:
        #     raise ValueError(
        #         "Item field mapping is required before NetSuite reference validation."
        #     )

        vendor_name = data.get(vendor_mapping.source_field_key)

        if isinstance(vendor_name,str):
            vendor_name = vendor_name.strip()

        if not vendor_name:
            # raise ValueError(
            #     "Vendor value is required before NetSuite reference validation."
            # )
            vendor_name = data.get("vendor_name")

        if isinstance(vendor_name,str):
            vendor_name = vendor_name.strip()

        if not vendor_name:
            raise ValueError(
                f'Vendor value is required. '
                f'Expected value in OCR field "{vendor_mapping.source_field_key}".'
            )

        line_items = data.get("line_items") or []

        if not isinstance(line_items, list):
            line_items = []
        
        vendor_result = self._validate_vendor_live(
            connection=connection,
            vendor_name=vendor_name,
        )
        item_results = []
        errors = []
    
        if not vendor_name or not str(vendor_name).strip():
            errors.append({
                "type": "VENDOR_VALUE_MISSING",
                "message": "No vendor value was found in the saved OCR data.",
                "extracted_name": None,
            })
        elif vendor_result.get("ambiguous"):
            errors.append({
                "type": "VENDOR_AMBIGUOUS",
                "message": "Multiple possible vendors matched. Please confirm the vendor value.",
                "extracted_name": vendor_name,
                "candidates": vendor_result.get("candidates", []),
            })
        elif not vendor_result.get("matched"):
            errors.append({
                "type": "VENDOR_NOT_FOUND",
                "message": "Vendor does not exist in the selected NetSuite account.",
                "extracted_name": vendor_name,
            })
        status = (
            ValidationStatus.VALIDATED
            if not errors
            else ValidationStatus.VALIDATION_FAILED
        )

        validation = OCRValidationResult.objects.create(
            document=document,
            version=version,
            connection=connection,
            status=status,
            vendor_extracted_name=
            # vendor_name or "",
            (
                str(vendor_name).strip()
                if vendor_name is not None else ""
            ),
            vendor_matched=bool(vendor_result.get("matched")),
            vendor_netsuite_id=vendor_result.get("netsuite_id"),
            
            items=item_results,
            errors=errors,
        )

        return {
            "validation_id": str(validation.id),
            "status": status,
            "vendor": vendor_result,
            "items": item_results,
            "errors": errors,
        }
    
    def _validate_vendor_live(
        self,
        *,
        connection,
        vendor_name,
    ):
        if not vendor_name:
            return {
                "matched": False,
                "ambiguous": False,
                "netsuite_id": None,
                "extracted_name": vendor_name,
                "round": 0,
            }

        literal = self._suiteql_literal(vendor_name)

        query = f"""
            SELECT
                id,
                entityid,
                companyname,
                isinactive
            FROM vendor
            WHERE
                LOWER(entityid) = LOWER({literal})
                OR LOWER(companyname) = LOWER({literal})
            ORDER BY id
        """

        response = self._execute_live_suiteql(
            connection=connection,
            query=query,
            limit=20,
        )

        rows = response.get("items", []) if isinstance(response, dict) else []

        active_rows = [
            row
            for row in rows
            if str(row.get("isinactive", "F")).upper() != "T"
        ]

        unique_rows = {
            str(row.get("id")): row
            for row in active_rows
            if row.get("id") is not None
        }

        matches = list(unique_rows.values())

        if len(matches) == 1:
            match = matches[0]

            return {
                "matched": True,
                "ambiguous": False,
                "netsuite_id": str(match["id"]),
                "extracted_name": vendor_name,
                "round": 1,
                "confidence": 1.0,
            }

        if len(matches) > 1:
            return {
                "matched": False,
                "ambiguous": True,
                "netsuite_id": None,
                "extracted_name": vendor_name,
                "round": 1,
                "confidence": 1.0,
                "candidates": [
                    {
                        "netsuite_id": str(row["id"]),
                        "name": (
                            row.get("companyname")
                            or row.get("entityid")
                        ),
                        "score": 1.0,
                    }
                    for row in matches[: self.MAX_SIMILAR_CANDIDATES]
                ],
            }

        return {
            "matched": False,
            "ambiguous": False,
            "netsuite_id": None,
            "extracted_name": vendor_name,
            "round": 1,
            "confidence": 0.0,
        }

    def _validate_items_live(
        self,
        *,
        connection,
        line_items,
        source_field_key,
    ):
        extracted_items = []

        for index, line in enumerate(
            line_items,
            start=1,
        ):
            if not isinstance(line, dict):
                extracted_items.append(
                    {
                        "matched": False,
                        "ambiguous": False,
                        "netsuite_id": None,
                        "extracted_name": None,
                        "line_index": index,
                        "round": 0,
                    }
                )
                continue

            value = line.get(source_field_key)

            extracted_items.append(
                {
                    "line_index": index,
                    "extracted_name": (
                        str(value).strip()
                        if value is not None
                        else None
                    ),
                }
            )

        unique_names = list(
            dict.fromkeys(
                item["extracted_name"]
                for item in extracted_items
                if item.get("extracted_name")
            )
        )

        rows_by_name = {}

        # Keep each SuiteQL request comfortably bounded.
        chunk_size = 25

        for start in range(
            0,
            len(unique_names),
            chunk_size,
        ):
            chunk = unique_names[
                start : start + chunk_size
            ]

            conditions = []

            for name in chunk:
                literal = self._suiteql_literal(name)

                conditions.append(
                    "("
                    f"LOWER(itemid) = LOWER({literal}) "
                    "OR "
                    f"LOWER(displayname) = LOWER({literal})"
                    ")"
                )

            if not conditions:
                continue

            query = f"""
                SELECT
                    id,
                    itemid,
                    displayname,
                    isinactive
                FROM item
                WHERE {" OR ".join(conditions)}
                ORDER BY id
            """

            response = self._execute_live_suiteql(
                connection=connection,
                query=query,
                limit=100,
            )

            rows = (
                response.get("items", [])
                if isinstance(response, dict)
                else []
            )

            for row in rows:
                if str(
                    row.get("isinactive", "F")
                ).upper() == "T":
                    continue

                record_id = row.get("id")

                if record_id is None:
                    continue

                for field_name in (
                    "itemid",
                    "displayname",
                ):
                    field_value = row.get(field_name)

                    if not field_value:
                        continue

                    normalized = self._normalize_match_name(
                        field_value,
                    )

                    rows_by_name.setdefault(
                        normalized,
                        {},
                    )[str(record_id)] = row

        results = []

        for item in extracted_items:
            name = item.get("extracted_name")
            line_index = item["line_index"]

            if not name:
                results.append(
                    {
                        "matched": False,
                        "ambiguous": False,
                        "netsuite_id": None,
                        "extracted_name": name,
                        "line_index": line_index,
                        "round": 0,
                    }
                )
                continue

            candidates = list(
                rows_by_name.get(
                    self._normalize_match_name(name),
                    {},
                ).values()
            )

            if len(candidates) == 1:
                record = candidates[0]

                results.append(
                    {
                        "matched": True,
                        "ambiguous": False,
                        "netsuite_id": str(record["id"]),
                        "extracted_name": name,
                        "line_index": line_index,
                        "record_type": "item",
                        "round": 1,
                        "confidence": 1.0,
                    }
                )

            elif len(candidates) > 1:
                results.append(
                    {
                        "matched": False,
                        "ambiguous": True,
                        "netsuite_id": None,
                        "extracted_name": name,
                        "line_index": line_index,
                        "round": 1,
                        "confidence": 1.0,
                        "candidates": [
                            {
                                "netsuite_id": str(
                                    candidate["id"]
                                ),
                                "name": (
                                    candidate.get("displayname")
                                    or candidate.get("itemid")
                                ),
                                "score": 1.0,
                            }
                            for candidate in candidates[
                                : self.MAX_SIMILAR_CANDIDATES
                            ]
                        ],
                    }
                )

            else:
                results.append(
                    {
                        "matched": False,
                        "ambiguous": False,
                        "netsuite_id": None,
                        "extracted_name": name,
                        "line_index": line_index,
                        "round": 1,
                        "confidence": 0.0,
                    }
                )

        return results

    def _validate_vendor(self, *, connection_id, vendor_name):
        if not vendor_name:
            return {
                "matched": False,
                "ambiguous": False,
                "netsuite_id": None,
                "extracted_name": vendor_name,
                "round": 0,
            }

        normalized = self._normalize_match_name(vendor_name)

        exact_matches = self.repository.find_reference_records(
            connection_id=connection_id,
            record_type=NetSuiteRecordType.VENDOR,
            search_name=normalized,
        )

        if len(exact_matches) == 1:
            match = exact_matches[0]
            return {
                "matched": True,
                "ambiguous": False,
                "netsuite_id": str(match.internal_id),
                "extracted_name": vendor_name,
                "round": 1,
                "confidence": 1.0,
            }

        if len(exact_matches) > 1:
            return {
                "matched": False,
                "ambiguous": True,
                "netsuite_id": None,
                "extracted_name": vendor_name,
                "round": 1,
                "confidence": 1.0,
                "candidates": [
                    {
                        "netsuite_id": str(match.internal_id),
                        "name": match.name,
                        "score": 1.0,
                    }
                    for match in exact_matches[: self.MAX_SIMILAR_CANDIDATES]
                ],
            }

        vendors = NetSuiteReferenceRecord.objects.filter(
            connection_id=connection_id,
            record_type=NetSuiteRecordType.VENDOR,
        ).exclude(is_inactive=True)

        scored = self._rank_similar_records(vendors, vendor_name)

        return self._resolve_ranked_candidate(
            scored=scored,
            extracted_name=vendor_name,
        )

    def _validate_item(self, *, connection_id, description, line_index):
        if not description:
            return {
                "matched": False,
                "ambiguous": False,
                "netsuite_id": None,
                "extracted_name": description,
                "line_index": line_index,
                "round": 0,
            }

        normalized = self._normalize_match_name(description)

        exact_matches = []

        # Round 1 is global across every supported Vendor Bill item subtype.
        # This prevents silently preferring one subtype over another when the
        # same item name is duplicated in NetSuite.
        for item_type in self.ITEM_RECORD_TYPES:
            exact_matches.extend(
                self.repository.find_reference_records(
                    connection_id=connection_id,
                    record_type=item_type,
                    search_name=normalized,
                )
            )

        if len(exact_matches) == 1:
            match = exact_matches[0]
            return {
                "matched": True,
                "ambiguous": False,
                "netsuite_id": str(match.internal_id),
                "extracted_name": description,
                "line_index": line_index,
                "record_type": match.record_type,
                "round": 1,
                "confidence": 1.0,
            }

        if len(exact_matches) > 1:
            return {
                "matched": False,
                "ambiguous": True,
                "netsuite_id": None,
                "extracted_name": description,
                "line_index": line_index,
                "round": 1,
                "confidence": 1.0,
                "candidates": [
                    {
                        "netsuite_id": str(match.internal_id),
                        "name": match.name,
                        "record_type": match.record_type,
                        "score": 1.0,
                    }
                    for match in exact_matches[: self.MAX_SIMILAR_CANDIDATES]
                ],
            }

        items = NetSuiteReferenceRecord.objects.filter(
            connection_id=connection_id,
            record_type__in=self.ITEM_RECORD_TYPES,
        ).exclude(is_inactive=True)

        scored = self._rank_similar_records(items, description)

        result = self._resolve_ranked_candidate(
            scored=scored,
            extracted_name=description,
            line_index=line_index,
        )

        if result.get("matched"):
            result["record_type"] = (
                scored[0]["record"].record_type
                if scored
                else NetSuiteRecordType.INVENTORY_ITEM
            )

        return result

    def _resolve_item_live_for_posting(
        self,
        *,
        connection,
        item_name,
    ):
        """Resolve a Vendor Bill item against the selected NetSuite account.

        NetSuite exposes a consolidated ``Item`` SuiteQL record source.
        Using it avoids probing individual item subtype tables (many of
        which are not queryable in every account) and also prevents the
        same underlying item table from being queried repeatedly.

        Posting requires an exact normalized name/ID match. Fuzzy matching
        is intentionally not used here because this method runs immediately
        before creating a financial transaction.

        Rules:
        - Ignore empty item names.
        - Use NetSuite's consolidated `item` SuiteQL source.
        - Match against itemid/displayname.
        - Ignore inactive items.
        - Normalize both sides in Python for punctuation/spacing differences.
        - Deduplicate by NetSuite internal ID.
        - If multiple exact/normalized matches exist, use first active match.
        - Never place booleans/non-dict values into the match collection.
        """
        raw_item_name = str(item_name or "").strip()
        if not raw_item_name:
            return {
                "matched": False,
                "ambiguous": False,
                "netsuite_id": None,
            }

        normalized_input = self._normalize_match_name(raw_item_name)
        
        # ---------------------------------------------------------
        # Round 1: exact case-insensitive match
        # ---------------------------------------------------------

        if not normalized_input:
            return {
                "matched":False,
                "ambiguous":False,
                "netsuite_id":None,
            }

        query_literal  = self._suiteql_literal(raw_item_name)

        # NetSuite's consolidated Item source covers item records across
        # supported item subtypes. Oracle's SuiteQL examples use `item` as
        # the item record source, so do not derive the SQL table name from
        # REST record-type constants such as `inventoryItem`.
        query  = f"""
            SELECT
                id,
                itemid,
                displayname,
                isinactive
            FROM item
            WHERE
                (
                    LOWER(itemid) = LOWER({query_literal})
                    OR LOWER(displayname) = LOWER({query_literal})
                )
            ORDER BY id
        """

        try:
            response = self._execute_live_suiteql(
                connection=connection,
                query=query,
                limit=50,
            )
        except Exception as exc:
            logger.exception(
                "Live NetSuite consolidated item lookup failed — "
                "connection=%s item=%r",
                connection.id,
                raw_item_name,
            )
            raise NetSuiteRecordFetchException(
                f'Unable to look up NetSuite item "{raw_item_name}" in the selected account.'
            ) from exc

        rows = (
            response.get("items", [])
            if isinstance(response, dict)
            else []
        )

        matches = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            if str(row.get("isinactive", "F")).upper() == "T":
                continue

            record_id = row.get("id")
            if record_id is None:
                continue

            itemid = row.get("itemid")
            displayname = row.get("displayname")

            # Final application-side normalization check.
            itemid_normalized = (
                self._normalize_match_name(itemid)
                if itemid
                else ""
            )

            displayname_normalized = (
                self._normalize_match_name(displayname)
                if displayname
                else ""
            )

            if normalized_input not in (
                itemid_normalized,
                displayname_normalized,
            ):
                continue

            matches.append(
                {
                    "id": str(record_id),
                    "itemid": itemid,
                    "displayname": displayname,
                    "record_type": "item",
                }
            )
        unique_matches = {}

        for match in matches:
            # if not isinstance(match, dict):
            #     continue

            record_id = match.get("id")
            if not record_id:
                continue

            unique_matches.setdefault(
                str(record_id),
                match,
            )

        matches = list(unique_matches.values())

        if not matches:
            logger.info(
                "No active NetSuite item match found — "
                "connection=%s item=%r",
                connection.id,
                raw_item_name,
            )
            return {
                "matched": False,
                "ambiguous": False,
                "netsuite_id": None,
            }

        # Current requirement:
        # first active exact/normalized match wins.
        first_match = matches[0]

        if len(matches) > 1:
            logger.warning(
                "Multiple NetSuite item matches found; using first active "
                "match for posting — item=%r id=%s candidates=%s "
                "connection=%s",
                raw_item_name,
                first_match["id"],
                len(matches),
                connection.id,
            )

        return {
            "matched": True,
            "ambiguous": False,
            "netsuite_id": first_match["id"],
            "record_type": "item",
            "round": 1,
            "confidence": 1.0,
        }

    def resolve_item_for_posting(
        self,
        *,
        connection,
        item_name,
        line_index,
    ):
        result = self._resolve_item_live_for_posting(
            connection=connection,
            item_name=item_name,
        )

        if result.get("ambiguous"):
            raise ValueError(
                f'Line {line_index}: multiple NetSuite items matched '
                f'"{item_name}". Please correct the item.'
            )

        if not result.get("matched"):
            raise ValueError(
                f'Line {line_index}: NetSuite item '
                f'"{item_name}" does not exist in the selected account.'
            )

        item_id = result.get("netsuite_id")

        if not item_id:
            raise ValueError(
                f'Line {line_index}: NetSuite item ID could not be resolved.'
            )

        if result.get("round") != 1:
            raise ValueError(
                f'Line {line_index}: item "{item_name}" was not an exact '
                'NetSuite match. Please correct the item before posting.'
            )

        return result

class NetSuiteCustomFieldService:
    """
    Create and manage NetSuite custom fields for OCR custom fields.

    Enforces duplicate protection and preserves authoritative mapping
    between OCR custom fields and NetSuite script IDs.
    """

    def __init__(self, repository=None):
        self.repository = repository or NetSuiteConnectionRepository()

    def create_custom_field(self, *, company, connection_id, record_type, scope, field_label, datatype, source_field_key, source_field_label):
        connection = self.repository._get_authorized_connection(
            connection_id=connection_id,
            company=company,
            )
        if connection is None:
            raise NetSuiteConnectionNotFoundException("NetSuite connection not found.")

        candidate_id = self._generate_candidate_id(source_field_key, scope)

        existing = NetSuiteCustomField.objects.filter(
            company=company,
            connection=connection,
            record_type=record_type,
            scope=scope,
            source_field_key=source_field_key,
        ).first()

        if existing and existing.netsuite_field_id:
            return existing

        if existing and not existing.netsuite_field_id:
            candidate_id = existing.field_id

        custom_field = NetSuiteCustomField.objects.create(
            company=company,
            connection=connection,
            record_type=record_type,
            scope=scope,
            field_label=field_label,
            field_id=candidate_id,
            datatype=datatype,
            source_field_key=source_field_key,
            source_field_label=source_field_label,
            status='pending',
        )

        try:
            ns_field_id = self._create_in_netsuite(
                connection=connection,
                record_type=record_type,
                scope=scope,
                field_label=field_label,
                field_id=candidate_id,
                datatype=datatype,
            )
            custom_field.netsuite_field_id = str(ns_field_id)
            custom_field.status = 'created'
            custom_field.save(update_fields=['netsuite_field_id', 'status', 'updated_at'])
        except Exception as exc:
            custom_field.status = 'error'
            custom_field.error = str(exc)[:1000]
            custom_field.save(update_fields=['status', 'error', 'updated_at'])
            raise

        return custom_field

    @staticmethod
    def _generate_candidate_id(source_field_key, scope):
        safe = ''.join(
            c if c.isalnum() else '_'
            for c in source_field_key
        ).lower()
        safe = safe.strip('_') or 'custom_field'
        if len(safe) > 25:
            safe = safe[:25]

        prefix = 'custbody' if scope in {'header', 'body'} else 'custcol'
        return f'{prefix}_{safe}'

    def _create_in_netsuite(self, *, connection, record_type, scope, field_label, field_id, datatype):
        """
        Create the custom field in NetSuite via REST API.

        This is a minimal implementation. Production should use the
        NetSuite custom field REST endpoint with proper error handling.
        """
        from netsuite.client import NetSuiteAuthClient
        from tenancy.services import company_lifecycle_service

        company = getattr(connection, 'company', None)
        if company is not None:
            company_lifecycle_service.ensure_operational(company=company)

        client = NetSuiteAuthClient(
            account_id=connection.netsuite_account_id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
        )
        access_token = client.get_valid_access_token()

        ns_datatype = {
            'text': 'text',
            'number': 'integer',
            'date': 'date',
            'boolean': 'checkbox',
            'currency': 'currency',
        }.get(datatype, 'text')

        ns_record_type = record_type
        if record_type == 'vendorBill':
            ns_record_type = 'vendorBill'

        payload = {
            'recordType': ns_record_type,
            'label': field_label,
            'scriptId': field_id,
            'type': ns_datatype,
            'applyTo': scope,
        }

        import requests
        base_url = f"https://{connection.netsuite_account_id}.suitetalk.api.netsuite.com"
        url = f"{base_url}/record/v1/customrecord_customfield"

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code not in (200, 201):
            raise ValueError(
                f"NetSuite custom field creation failed: {response.status_code} {response.text[:500]}"
            )

        result = response.json()
        return result.get('id') or result.get('internalId') or field_id