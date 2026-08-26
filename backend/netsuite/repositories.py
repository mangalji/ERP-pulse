from accounts.models import User
from netsuite.models import NetSuiteConnection, NetSuiteConnectionAuditLog
from django.db import transaction
from netsuite.models import EmployeeConnection, NetSuiteConnection, NetSuiteConnectionAuditLog, NetSuiteReferenceRecord, NetSuiteOCRPosting, NetSuiteUserConnectionPreference
import logging
from netsuite.exceptions import NetSuiteConnectionNotFoundException

logger = logging.getLogger(__name__)


class NetSuiteConnectionRepository:
    """
    Persistence-only operations for NetSuiteConnection.

    Contains no OAuth/HTTP logic — token exchange happens in
    NetSuiteAuthClient (client.py), orchestration in
    NetSuiteConnectionService (services.py). This class only reads from
    and writes to the database.
    """
    def _get_authorized_connection(self, *, connection_id, company):
        # connection = self.repository.get_for_company(
        #     connection_id=connection_id,
        #     company=company,
        # )
        connection = (
            NetSuiteConnection.objects
            .filter(
                id=connection_id,
                company=company,
                status="connected",
                is_active=True,
            )
            .first()
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection not found or not accessible."
            )

        return connection

    def get_by_user(self, user: User) -> NetSuiteConnection | None:
        # return NetSuiteConnection.objects.filter(user=user,is_active=True).first()
        # return self.get_for_user(user)
        return (
            NetSuiteConnection.objects.filter(
                user=user,
                is_active=True,
            ).first()
        )

    # def get_for_user(self, user: User) -> NetSuiteConnection | None:
    #     """
    #     Resolve the NetSuite connection available to this user.

    #     Company Admin:
    #         Uses the active connection they own.

    #     Employee:
    #         Uses the active connection assigned through EmployeeConnection.
    #     """
        
    #     from netsuite.models import NetSuiteUserConnectionPreference
    #     is_company_admin = (
    #         getattr(user, "is_superuser", False) 
    #         or user.user_roles.filter(
    #             role__name__iexact="Company Admin",
    #         ).exists()
    #     )
    #     # Build the user's actually authorized connections first.
    #     if is_company_admin:
    #         available = NetSuiteConnection.objects.filter(
    #                 company_id=user.company_id,
    #                 status="connected",
    #                 is_active=True,
    #             ).order_by("-connected_at")
    #     else:
    #         available = (
    #             NetSuiteConnection.objects.filter(
    #                 employee_assignments__employee=user,
    #                 company_id=user.company_id,
    #                 status="connected",
    #                 is_active=True,
    #             )
    #             .distinct()
    #             .order_by("-connected_at")
    #         )
    #     # No usable connection at all.
    #     if not available.exists():
    #         return None
    #     # Use explicit user preference when it is still valid.
    #     preference = (
    #     NetSuiteUserConnectionPreference.objects
    #     .select_related('connection')
    #     .filter(user=user)
    #     .first()
    #     )
    #     if preference and preference.connection:
    #         preferred = available.filter(id=preference.connection_id).first()
    #         if preferred:
    #             return preferred
    #         # Preference points to a connection the user can no longer use.
    #         # Clear stale preference and fall back safely.
    #         preference.connection = None
    #         preference.save(
    #             update_fields=["connections","updated_at"]
    #         )
    #         # Existing user / first-time user fallback.
    #         current = available.first()
    #         # Persist the fallback so subsequent requests use an explicit
    #         # current connection.
    #         NetSuiteUserConnectionPreference.objects.update_or_create(
    #             user=user,
    #             defaults={"connection": current},
    #         )
    #         return current

    # def get_for_user(self, user: User) -> NetSuiteConnection | None:
    #     """
    #     Return the user's current NetSuite connection.

    #     Company Admin:
    #         - Can use any connected active connection in their company.

    #     Employee:
    #         - Can use only connected active connections assigned to them.

    #     Preference:
    #         - If a valid preference exists, use it.
    #         - If no preference exists, automatically select the first
    #           available connection and persist it.
    #         - If the saved preference becomes invalid, automatically
    #           fall back to the first available connection.
    #     """

    #     from netsuite.models import NetSuiteUserConnectionPreference

    #     is_company_admin = (
    #         getattr(user, "is_superuser", False)
    #         or user.user_roles.filter(
    #             role__name__iexact="Company Admin",
    #         ).exists()
    #     )

    #     # ---------------------------------------------------------
    #     # 1. Build connections this user is actually allowed to use
    #     # ---------------------------------------------------------
    #     if is_company_admin:
    #         available = (
    #             NetSuiteConnection.objects
    #             .filter(
    #                 company_id=user.company_id,
    #                 status="connected",
    #                 is_active=True,
    #             )
    #             .order_by("-connected_at")
    #         )
    #     else:
    #         available = (
    #             NetSuiteConnection.objects
    #             .filter(
    #                 company_id=user.company_id,
    #                 employee_assignments__employee=user,
    #                 status="connected",
    #                 is_active=True,
    #             )
    #             .distinct()
    #             .order_by("-connected_at")
    #         )

    #     # ---------------------------------------------------------
    #     # 2. No available connection
    #     # ---------------------------------------------------------
    #     if not available.exists():
    #         return None

    #     # ---------------------------------------------------------
    #     # 3. Try the user's saved preference
    #     # ---------------------------------------------------------
    #     preference = (
    #         NetSuiteUserConnectionPreference.objects
    #         .select_related("connection")
    #         .filter(user=user)
    #         .first()
    #     )

    #     if preference and preference.connection_id:
    #         selected = available.filter(
    #             id=preference.connection_id
    #         ).first()

    #         if selected:
    #             return selected

    #         # Saved preference is stale/invalid.
    #         preference.connection = None
    #         preference.save(
    #             update_fields=[
    #                 "connection",
    #                 "updated_at",
    #             ]
    #         )

    #     # ---------------------------------------------------------
    #     # 4. Existing user with no preference:
    #     #    automatically select first available connection
    #     # ---------------------------------------------------------
    #     selected = available.first()

    #     NetSuiteUserConnectionPreference.objects.update_or_create(
    #         user=user,
    #         defaults={
    #             "connection": selected,
    #         },
    #     )

    #     return selected

    def get_for_user(self, user:User) -> NetSuiteConnection | None:
        available = self.list_available_for_user(user)

        if not available.exists():
            return None

        preference = (
            NetSuiteUserConnectionPreference.objects
            .select_related("connection")
            .filter(user=user)
            .first()
        )

        if preference and preference.connection_id:
            selected = available.filter(
                id=preference.connection_id
            ).first()

            if selected:
                return selected

        selected = available.filter(status="connected").first()

        if selected is None:
            return None

        NetSuiteUserConnectionPreference.objects.update_or_create(
            user=user,
            defaults={"connection": selected},
        )

        return selected

    def get_authorized_for_user(
        self,
        *,
        user: User,
        connection_id,
    ) -> NetSuiteConnection | None:

        """
        Return a connection only when the current user is authorized
        to use it.

        Company Admin:
            Any active connection belonging to their company.

        Employee:
            Only an active connection assigned through EmployeeConnection.
        """

        connection = (
            NetSuiteConnection.objects
            .filter(
                id=connection_id,
                company_id=user.company_id,
                status="connected",
                is_active=True,
            )
            .first()
        )

        if connection is None:
            return None

        is_company_admin = (
            getattr(user, "is_superuser", False)
            or user.user_roles.filter(
                role__name__iexact="Company Admin",
            ).exists()
        )

        if is_company_admin:
            return connection

        if EmployeeConnection.objects.filter(
            employee=user,
            connection=connection,
        ).exists():
            return connection

        return None

    def list_available_for_user(
        self,
        user: User,
    ):
        is_company_admin = (
            getattr(user, "is_superuser", False)
            or user.user_roles.filter(
                role__name__iexact="Company Admin",
            ).exists()
        )
        connections = NetSuiteConnection.objects.filter(
            company_id = user.company_id,
            # status="connected",
            is_active=True,
        ).order_by("-connected_at")
    
        if is_company_admin:
            return connections
            # return NetSuiteConnection.objects.filter(
            #     company_id=user.company_id,
            #     status='connected',
            #     is_active=True,
            # ).order_by('-connected_at')
    
        # return (
        #     NetSuiteConnection.objects
        #     .filter(
        #         employee_assignments__employee=user,
        #         company_id=user.company_id,
        #         status='connected',
        #         is_active=True,
        #     )
        #     .distinct()
        #     .order_by('-connected_at')
        # )
        return connections.filter(
            employee_assignments__employee=user
        ).distinct()

    def update_tokens(
        self,
        connection: NetSuiteConnection,
        *,
        access_token: str,
        refresh_token: str,
        access_token_expires_at,
        refresh_token_expires_at=None,
    ) -> NetSuiteConnection:
        """Persist a refreshed access/refresh token pair after a token-refresh call."""
        connection.access_token = access_token
        connection.refresh_token = refresh_token
        connection.access_token_expires_at = access_token_expires_at
        if refresh_token_expires_at is not None:
            connection.refresh_token_expires_at=refresh_token_expires_at
        connection.status = "connected"
        connection.consecutive_failures = 0
        connection.last_error = None
        connection.save(
            update_fields=[
                'access_token', 'refresh_token', 'access_token_expires_at','refresh_token_expires_at','status', "consecutive_failures", "last_error", 'updated_at',
            ]
        )
        return connection

    def deactivate(self, connection: NetSuiteConnection) -> NetSuiteConnection:
        """Mark a connection inactive (e.g. on disconnect) without deleting history."""
        connection.is_active = False
        connection.save(update_fields=['is_active', 'updated_at'])
        return connection

    def list_by_user(self,user:User):
        # return NetSuiteConnection.objects.filter(user=user).order_by("-is_active","-connected_at")
        return self.list_available_for_user(user)
    
    def get_by_id(self,user:User,connection_id)-> NetSuiteConnection | None:
        return NetSuiteConnection.objects.filter(
            id=connection_id,
            company_id=user.company_id,
        ).first()

    def get_by_id_any(self, connection_id) -> NetSuiteConnection | None:
        return NetSuiteConnection.objects.filter(
            id=connection_id,
        ).first()

    def get_for_company( self, *, connection_id, company) -> NetSuiteConnection | None:
        return (NetSuiteConnection.objects.select_related("company").filter(
            id=connection_id,
            company=company,
            ).first()
        )


    def exists_for_account(self, company_id, netsuite_account_id: str) -> bool:
        """
        Used by NetSuiteConnectionService.create_connection() to give a
        clean validation error instead of letting the (user,
        netsuite_account_id) unique constraint raise an IntegrityError
        that the generic exception handler can't map to anything but a
        500.
        """
        return NetSuiteConnection.objects.filter(
            company_id=company_id,
            netsuite_account_id=netsuite_account_id,
        ).exists()
    
    def get_locked(self, connection_id) -> NetSuiteConnection:
        """
        Re-fetch a connection with a Postgres row-level lock (SELECT ...
        FOR UPDATE). Must be called inside `transaction.atomic()`.

        Used by NetSuiteTokenManager to serialize concurrent token
        refreshes for the same connection — without this, two requests
        arriving while the token is expired could both call NetSuite's
        refresh endpoint at once, and since NetSuite rotates refresh
        tokens on use, the second call can fail or the two DB writes can
        race. The lock makes the second caller wait for the first to
        finish and commit before it re-checks expiry.
        """
        return NetSuiteConnection.objects.select_for_update().get(id=connection_id)

    # def switch_active_connection(self, user: User, connection: NetSuiteConnection):
    #     with transaction.atomic():
    #         NetSuiteConnection.objects.filter(
    #             user=user,
    #             is_active=True,
    #         ).update(is_active=False)

    #         connection.is_active = True
    #         connection.save(update_fields=["is_active", "updated_at"])

    #         return connection
    
    def create(
    self,
    *,
    user:User,
    client_name: str,
    environment: str,
    client_id: str,
    client_secret: str,
    netsuite_account_id: str,
    company_id=None,
    ):
        return NetSuiteConnection.objects.create(
        user=user,
        company_id=company_id,
        client_name=client_name,
        environment=environment,
        client_id=client_id,
        client_secret=client_secret,
        netsuite_account_id=netsuite_account_id,
        status="pending",
        is_active=False,
    )

    def get_existing_for_account( self, *, company_id, netsuite_account_id: str) -> NetSuiteConnection | None:
        return (
            NetSuiteConnection.objects
            .filter(
                company_id=company_id,
                netsuite_account_id=netsuite_account_id,
            )
            .first()
        )

    def prepare_for_oauth_retry(
        self,
        connection: NetSuiteConnection,
        *,
        user: User,
        company_id,
        client_name: str,
        environment: str,
        client_id: str,
        client_secret: str,
    ) -> NetSuiteConnection:
        connection.user = user
        connection.company_id = company_id
        connection.client_name = client_name
        connection.environment = environment
        connection.client_id = client_id
        connection.client_secret = client_secret
    
        connection.access_token = None
        connection.refresh_token = None
        connection.access_token_expires_at = None
        connection.refresh_token_expires_at = None
    
        connection.status = "pending"
        connection.is_active = False
        connection.last_error = None
        connection.consecutive_failures = 0
    
        connection.save()
    
        return connection

    def rename(
    self,
    connection: NetSuiteConnection,
    client_name: str,) -> NetSuiteConnection:
        connection.client_name = client_name
        connection.save(update_fields=["client_name", "updated_at"])
        return connection

    def delete(self, connection: NetSuiteConnection):
        with transaction.atomic():
            connection.delete()

            # user = connection.user
            # was_active = connection.is_active

            # connection.delete()

            # if was_active:
            #     next_connection = (
            #         NetSuiteConnection.objects.filter(
            #             user=user,
            #             status="connected",
            #         )
            #         .order_by("-connected_at")
            #         .first()
            #     )

            #     if next_connection:
            #         next_connection.is_active = True
            #         next_connection.save(update_fields=["is_active", "updated_at"])

    def record_sync_success(self, connection: NetSuiteConnection) -> NetSuiteConnection:
        """Called after a successful NetSuite data fetch or token refresh."""
        from django.utils import timezone

        connection.last_synced_at = timezone.now()
        connection.last_error = None
        connection.consecutive_failures = 0
        
        update_fields=['last_synced_at', 'last_error', 'consecutive_failures', 'updated_at']
        
        if connection.status == 'error':
            connection.status = 'connected'
            update_fields.append('status')
        connection.save(update_fields=update_fields)
        return connection

    def record_sync_failure(self, connection: NetSuiteConnection, *, error_message: str) -> NetSuiteConnection:
        """Called when a NetSuite data fetch or token refresh fails."""
        connection.last_error = error_message[:2000]
        connection.consecutive_failures += 1
        update_fields = ['last_error', 'consecutive_failures', 'updated_at']
        # Three or more failures in a row means this connection needs
        # attention — surface it in the connection list rather than
        # continuing to show a stale "connected" status.
        if connection.consecutive_failures >= NetSuiteConnection.UNHEALTHY_FAILURE_THRESHOLD and connection.status == 'connected':
            connection.status = 'error'
            update_fields.append('status')
        connection.save(update_fields=update_fields)
        return connection

    def record_connection_success(self,connection: NetSuiteConnection) -> NetSuiteConnection:
        """
        Mark a connection healthy after a successful live NetSuite operation.
        """
        connection.status = "connected"
        connection.consecutive_failures = 0
        connection.last_error = None

        connection.save(
            update_fields=[
                "status",
                "consecutive_failures",
                "last_error",
                "updated_at",
            ]
        )

        return connection

    def touch_last_used(self, connection: NetSuiteConnection) -> NetSuiteConnection:
        """
        Called after any successful live NetSuite API call through this
        connection (record fetch, SuiteQL, token refresh) — broader than
        record_sync_success, which is reserved for actual sync-job runs.
        """
        from django.utils import timezone

        connection.last_used_at = timezone.now()
        connection.save(update_fields=['last_used_at', 'updated_at'])
        return connection

    def complete_OAuth(self,
                       connection:NetSuiteConnection,
                       *,
                       access_token: str,
                       refresh_token: str,
                       access_token_expires_at,
                       refresh_token_expires_at=None):
        with transaction.atomic():
            # NetSuiteConnection.objects.filter(
            #     user=connection.user,
            #     is_active=True,
            # ).exclude(id=connection.id).update(is_active=False)
            connection.access_token=access_token
            connection.refresh_token=refresh_token
            connection.access_token_expires_at = access_token_expires_at
            connection.refresh_token_expires_at = refresh_token_expires_at
            connection.status = "connected"
            connection.is_active = True

            connection.save(
                update_fields=[
                "access_token",
                "refresh_token",
                "access_token_expires_at",
                "refresh_token_expires_at",
                "status",
                "is_active",
                "updated_at",
                ]
            )

            return connection

    def upsert_reference_records(self, records: list[dict]) -> int:
        """Bulk upsert cached NetSuite reference records."""
        if not records:
            return 0

        objects = [
            NetSuiteReferenceRecord(
                connection_id=item["connection_id"],
                record_type=item["record_type"],
                internal_id=str(item["internal_id"]),
                external_id=item.get("external_id"),
                name=item.get("name") or "",
                search_name=item.get("search_name") or "",
                item_type=item.get("item_type"),
                is_inactive=bool(item.get("is_inactive", False)),
                data=item.get("data") or {},
            )
            for item in records
            if item.get("internal_id") is not None
        ]

        if not objects:
            return 0

        NetSuiteReferenceRecord.objects.bulk_create(
            objects,
            update_conflicts=True,
            update_fields=[
                "external_id",
                "name",
                "search_name",
                "item_type",
                "is_inactive",
                "data",
                "synced_at",
            ],
            unique_fields=[
                "connection",
                "record_type",
                "internal_id",
            ],
            batch_size=500,
        )
        return len(objects)

    def find_reference_records(
        self,
        *,
        connection_id,
        record_type: str,
        search_name: str,
    ) -> list[NetSuiteReferenceRecord]:
        value = (search_name or "").strip()
        if not value:
            return []

        queryset = NetSuiteReferenceRecord.objects.filter(
            connection_id=connection_id,
            record_type=record_type,
            is_inactive=False,
        )

        # Exact match is intentional: financial posting must never guess.
        return list(
            queryset.filter(search_name__iexact=value)
            .order_by("internal_id")
        )

    def get_ocr_posting(self, *, document_id, version_id):
        return (
            NetSuiteOCRPosting.objects
            .filter(document_id=document_id, version_id=version_id)
            .first()
        )

    def save_ocr_posting(
        self,
        *,
        document,
        version,
        connection,
        user,
        status: str,
        request_payload: dict | None = None,
        response_payload: dict | None = None,
        netsuite_record_id: str | None = None,
        error_message: str | None = None,
    ):
        posting, _ = NetSuiteOCRPosting.objects.get_or_create(
            document=document,
            version=version,
            defaults={
                "connection": connection,
                "created_by": user,
            },
        )

        posting.connection = connection
        posting.created_by = user
        posting.status = status
        posting.request_payload = request_payload or {}
        posting.response_payload = response_payload or {}
        posting.netsuite_record_id = netsuite_record_id
        posting.error_message = error_message
        posting.save()
        return posting

class NetSuiteConnectionAuditLogRepository:
    """
    Persistence-only operations for NetSuiteConnectionAuditLog.

    Deliberately minimal — a single log() method, since every write is
    the same shape (action + who + which connection + optional detail).
    No update/delete methods: audit rows are append-only by design.
    """

    def log(
        self,
        *,
        action: str,
        connection: NetSuiteConnection | None = None,
        user: User | None = None,
        netsuite_account_id: str | None = None,
        client_name: str | None = None,
        detail: str | None = None,
    ) -> NetSuiteConnectionAuditLog:
        return NetSuiteConnectionAuditLog.objects.create(
            action=action,
            connection=connection,
            user=user or (connection.user if connection else None),
            netsuite_account_id=netsuite_account_id or (connection.netsuite_account_id if connection else None),
            client_name=client_name if client_name is not None else (connection.client_name if connection else None),
            detail=detail,
        )

    def list_by_user(self, user: User, *, limit: int = 100):
        return NetSuiteConnectionAuditLog.objects.filter(user=user)[:limit]

    def list_by_company(self, company_id):
        return NetSuiteConnection.objects.filter(company_id=company_id).order_by('-is_active', '-connected_at')

    def get_employee_connection(self, employee_id):
        return EmployeeConnection.objects.select_related('connection').filter(employee_id=employee_id).first()

    def assign_employee(self, connection_id, employee_id):
        return EmployeeConnection.objects.get_or_create(
            connection_id=connection_id,
            employee_id=employee_id,
        )

    def remove_employee(self, connection_id, employee_id):
        return EmployeeConnection.objects.filter(
            connection_id=connection_id,
            employee_id=employee_id,
        ).delete()

    def list_connection_employees(self, connection_id):
        return EmployeeConnection.objects.filter(connection_id=connection_id).select_related('employee')
