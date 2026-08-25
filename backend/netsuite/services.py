"""
Business logic for connecting an AGSuite ERP user's NetSuite account.

Orchestrates oauth.py (URL/state), NetSuiteAuthClient (token exchange),
and NetSuiteConnectionRepository (persistence) — the view layer never
touches any of those directly, mirroring how AuthenticationService
orchestrates UserRepository/OTPService for the accounts app.
"""

import logging
from difflib import SequenceMatcher
import re
from accounts.models import User
from django.conf import settings
from netsuite.client import NetSuiteAuthClient
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import NetSuiteStateMismatchException, NetSuiteConnectionNotFoundException, NetSuiteConnectionAlreadyExistsException
from netsuite.models import EmployeeConnection, NetSuiteConnection, NetSuiteCustomField, NetSuiteOCRPosting, NetSuiteReferenceRecord
from netsuite.oauth import build_authorization_url, resolve_user_id_from_state
from netsuite.repositories import NetSuiteConnectionAuditLogRepository, NetSuiteConnectionRepository
from netsuite.token_manager import NetSuiteTokenManager
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
    ):
        self.repository = repository or NetSuiteConnectionRepository()
        self.audit_log_repository = audit_log_repository or NetSuiteConnectionAuditLogRepository()

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
            user=user,
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
        connection = self.repository.get_by_id(user,connection_id)

        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")

        self.audit_log_repository.log(action='deleted', connection=connection)
        self.repository.delete(connection)
        # return "connection removed succefully."
    
    def switch_connection(
            self,*,
            user:User,
            connection_id,
    ):
        self._ensure_user_company_operational(user=user)
        connection = self.repository.get_by_id(user,connection_id)

        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")

        switched = self.repository.switch_active_connection(user,connection,)
        self.audit_log_repository.log(action='switched_active', connection=switched)
        return switched

    def get_company_connections(self, *, company_id):
        return (
            NetSuiteConnection.objects
            .filter(
                company_id=company_id,
                status="connected",
                is_active=True,
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

    def assign_employee(self, *, connection_id, employee_id):
        connection = NetSuiteConnection.objects.select_related(
                'company'
            ).get(pk=connection_id)

        if connection.company is not None:
            company_lifecycle_service.ensure_operational(
                company=connection.company
            )

        employee = User.objects.get(pk=employee_id)

        if connection.company and employee.company_id != connection.company_id:
            raise ValueError('Employee does not belong to the same company as this connection.')

        if self._is_company_admin(employee):
            raise ValueError(
                'Company Admin already has NetSuite access and does not need assignment.'
            )


        assignment, _ = EmployeeConnection.objects.get_or_create(
            employee=employee,
            connection=connection,
        )
        return assignment

    def remove_employee(self, *, connection_id, employee_id):
        connection = NetSuiteConnection.objects.select_related(
            'company'
        ).filter(pk=connection_id).first()

        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "connection not found."
            )

        if connection.company is not None:
            company_lifecycle_service.ensure_operational(
                company=connection.company
            )

        deleted, _ = EmployeeConnection.objects.filter(
            connection_id=connection_id,
            employee_id=employee_id,
        ).delete()
        if deleted == 0:
            raise ValueError('Employee is not assigned to this connection.')

    def get_employee_connection(self, *, employee_id):
        user = User.objects.select_related("company").get(pk=employee_id)
        if self._is_company_admin(user):
            return (
            NetSuiteConnection.objects
            .filter(
                company=user.company,
                status="connected",
                is_active=True,
            )
            .order_by("-connected_at")
            .first()
        )
        assignment = EmployeeConnection.objects.select_related('connection').filter(employee_id=employee_id).first()

        if not assignment:
            return None

        return assignment.connection

    def test_connection(self, *, connection_id):
        connection = NetSuiteConnection.objects.select_related('company').get(pk=connection_id)
        if connection.company is not None:
            company_lifecycle_service.ensure_operational(
                company=connection.company
            )
        client = NetSuiteAuthClient(
            account_id=connection.netsuite_account_id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
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
        if connection is None or not connection.is_active:
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

        # If the caller supplied a connection, it must be company-authorized
        # and must exactly match the connection used for validation.
        if connection_id:
            connection = self.repository._get_authorized_connection(
                connection_id=connection_id,
                company=company,
            )
            if connection is None:
                raise ValueError(
                    "NetSuite connection not found or not accessible."
                )
        else:
            connection = validation.connection

        if connection is None:
            raise ValueError(
                "The validated NetSuite connection is no longer available."
            )

        if validation.connection_id != connection.id:
            raise ValueError(
                "The selected NetSuite connection does not match the "
                "connection used for validation."
            )

        data = self._reviewed_data(version)
        line_items = data.get("line_items") or []

        if not data.get("vendor_name"):
            raise ValueError(
                "Vendor Name is required before posting."
            )

        if not line_items:
            raise ValueError(
                "At least one OCR item line is required before posting."
            )

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

        if len(item_validation_results) != len(line_items):
            raise ValueError(
                "Validation result does not match the current OCR line items. "
                "Please validate the document again."
            )

        vendor = {
            "internal_id": str(validated_vendor_id),
        }

        payload_items = []

        for index, line in enumerate(line_items, start=1):
            if not isinstance(line, dict):
                raise ValueError(
                    f"Line {index}: OCR line item is invalid."
                )

            description = line.get("description")
            quantity = line.get("quantity")
            rate = line.get("unit_price")

            if not description:
                raise ValueError(
                    f"Line {index}: item description is required."
                )

            if quantity in (None, ""):
                raise ValueError(
                    f"Line {index}: quantity is required."
                )

            if rate in (None, ""):
                raise ValueError(
                    f"Line {index}: unit price is required."
                )

            validated_item = item_validation_results[index - 1]

            if not validated_item.get("matched"):
                raise ValueError(
                    f"Line {index}: item is no longer validated."
                )

            item_id = validated_item.get("netsuite_id")
            if not item_id:
                raise ValueError(
                    f"Line {index}: validation did not return a NetSuite item ID."
                )

            payload_items.append(
                {
                    "item": {"id": str(item_id)},
                    "quantity": quantity,
                    "rate": rate,
                }
            )

        payload = {
            "entity": {"id": vendor["internal_id"]},
            "item": {"items": payload_items},
        }

        if data.get("invoice_number"):
            payload["tranid"] = data["invoice_number"]
        if data.get("invoice_date"):
            payload["trandate"] = data["invoice_date"]
        if data.get("due_date"):
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
    """
    Manage OCR → NetSuite field mappings and AI-assisted suggestions.
    """

    def __init__(self, repository=None):
        self.repository = repository or NetSuiteConnectionRepository()

    def get_field_catalogue(self, *,company ,connection_id, record_type='vendorBill'):
        """
        Return available NetSuite fields for a record type from synced
        reference data and known metadata.
        """
        connection = self.repository.get_for_company(
            connection_id=connection_id,
            company=company,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection not found or not accessible."
            )

        fields = self._build_standard_catalogue(record_type)
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
            'record_type': record_type,
            'fields': fields,
            'custom_fields': custom_fields,
        }

    def _build_standard_catalogue(self, record_type):
        """
        Hardcoded baseline catalogue of standard NetSuite Vendor Bill
        fields. In production this would be enriched from live NetSuite
        metadata; the baseline ensures the UI always has candidates.
        """
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

        return {
            'body': body_fields,
            'column': item_fields,
        }

    def suggest_mappings(self, *,company, connection_id, record_type, source_fields):
        """
        Return AI-assisted mapping suggestions for source fields.

        Uses rule-based semantic matching with datatype/scope compatibility
        checks. Falls back to UNRESOLVED when no safe candidate exists.
        """
        catalogue = self.get_field_catalogue(
            company=company,
            connection_id=connection_id,
            record_type=record_type,
        )
        all_targets = (
            catalogue.get('fields', {}).get('body', [])
            + catalogue.get('fields', {}).get('column', [])
            + catalogue.get('custom_fields', [])
        )

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
            elif len(candidates) == 1:
                status = 'MAPPED'
                best = candidates[0]
            elif candidates[0].get('score', 0) >= 0.8:
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
            'number': {'decimal', 'integer', 'currency'},
            'date': {'date'},
            'boolean': {'checkbox'},
            'currency': {'currency', 'decimal'},
        }
        allowed = compatible.get(source_dtype.lower(), set())
        return target_dtype.lower() in allowed or target_dtype.lower() == 'text'

    def save_mappings(self, *, company, connection_id, record_type, mappings):
        """
        Persist confirmed field mappings. Replaces existing mappings for
        the same company/connection/record_type/source_field_key.
        """
        connection = self.repository.get_for_company(
            connection_id=connection_id,
            company=company,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection not found or not accessible."
            )

        saved = []
        for mapping in mappings:
            source_key = mapping.get('source_field_key')
            if not source_key:
                continue

            obj, _ = OCRNetSuiteFieldMapping.objects.update_or_create(
                company=company,
                connection=connection,
                record_type=record_type,
                source_field_key=source_key,
                defaults={
                    'source_field_label': mapping.get('source_field_label', source_key),
                    'source_scope': mapping.get('source_scope', 'header'),
                    'source_datatype': mapping.get('source_datatype', 'text'),
                    'target_field_id': mapping.get('target_field_id', ''),
                    'target_field_label': mapping.get('target_field_label', ''),
                    'target_scope': mapping.get('target_scope', 'body'),
                    'target_datatype': mapping.get('target_datatype', 'text'),
                    'is_required': mapping.get('is_required', False),
                    'is_custom': mapping.get('is_custom', False),
                    'reference_type': mapping.get('reference_type'),
                    # 'mapping_status': mapping.get('status', 'MAPPED'),
                    'mapping_status': mapping.get(
                        'mapping_status',
                        'MAPPED' if mapping.get('target_field_id') else 'UNRESOLVED',
                    ),
                    'confidence': mapping.get('confidence'),
                    'metadata': mapping.get('metadata', {}),
                },
            )
            saved.append(obj)
        return saved

    def get_mappings(self, *, company, connection_id, record_type):
        connection = self.repository.get_by_id_any(connection_id)
        if connection is None:
            return []
        return list(
            OCRNetSuiteFieldMapping.objects.filter(
                company=company,
                connection=connection,
                record_type=record_type,
            ).values()
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
        NetSuiteRecordType.NON_INVENTORY_PURCHASE_ITEM,
        NetSuiteRecordType.SERVICE_SALE_ITEM,
        NetSuiteRecordType.SERVICE_PURCHASE_ITEM,
        NetSuiteRecordType.DESCRIPTION_ITEM,
    )

    def __init__(self, repository=None):
        self.repository = repository or NetSuiteConnectionRepository()

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

    def validate_document(self, *, document_id, user):
        from ocr.models import OCRDocument, OCRDocumentVersion, OCRLineItem

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

        connection = self.repository.get_for_user(user)
        if connection is None:
            raise ValueError("No NetSuite connection available.")

        vendor_name = data.get("vendor_name")
        line_items = data.get("line_items") or []

        if not isinstance(line_items, list):
            raise ValueError("OCR line_items must be a list.")

        vendor_result = self._validate_vendor(
            connection_id=connection.id,
            vendor_name=vendor_name,
        )

        item_results = []

        for index, line in enumerate(line_items, start=1):
            if not isinstance(line, dict):
                item_results.append(
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

            description = (
                line.get("description")
                or line.get("item_name")
            )

            item_results.append(
                self._validate_item(
                    connection_id=connection.id,
                    description=description,
                    line_index=index,
                )
            )

        errors = []
        status = ValidationStatus.VALIDATED

        if vendor_result.get("ambiguous"):
            status = ValidationStatus.VALIDATION_FAILED
            errors.append(
                {
                    "type": "VENDOR_AMBIGUOUS",
                    "message": (
                        "Multiple possible vendors matched. "
                        "Please confirm the vendor mapping."
                    ),
                    "extracted_name": vendor_name,
                    "candidates": vendor_result.get("candidates", []),
                }
            )
        elif not vendor_result.get("matched"):
            status = ValidationStatus.VALIDATION_FAILED
            errors.append(
                {
                    "type": "VENDOR_NOT_FOUND",
                    "message": "This vendor is not existed",
                    "extracted_name": vendor_name,
                }
            )

        for item in item_results:
            if item.get("ambiguous"):
                status = ValidationStatus.VALIDATION_FAILED
                errors.append(
                    {
                        "type": "ITEM_AMBIGUOUS",
                        "message": (
                            "Multiple possible items matched. "
                            "Please confirm the item mapping."
                        ),
                        "extracted_name": item.get("extracted_name"),
                        "line_index": item.get("line_index"),
                        "candidates": item.get("candidates", []),
                    }
                )
            elif not item.get("matched"):
                status = ValidationStatus.VALIDATION_FAILED
                errors.append(
                    {
                        "type": "ITEM_NOT_FOUND",
                        "message": "Item not existed",
                        "extracted_name": item.get("extracted_name"),
                        "line_index": item.get("line_index"),
                    }
                )

        result = OCRValidationResult.objects.create(
            document=document,
            version=version,
            connection=connection,
            status=status,
            vendor_extracted_name=vendor_name or "",
            vendor_matched=bool(vendor_result.get("matched")),
            vendor_netsuite_id=vendor_result.get("netsuite_id"),
            items=item_results,
            errors=errors,
        )

        return {
            "validation_id": str(result.id),
            "status": status,
            "vendor": vendor_result,
            "items": item_results,
            "errors": errors,
        }

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