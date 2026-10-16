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
import uuid
from accounts.models import User
from django.db import transaction
from datetime import timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from netsuite.client import NetSuiteAuthClient
from netsuite.constants import NETSUITE_MAX_TOKEN_ROTATION_HOURS, NetSuiteRecordType
from netsuite.exceptions import (
    NetSuiteStateMismatchException, 
    NetSuiteConnectionNotFoundException, 
    NetSuiteConnectionAlreadyExistsException,
    NetSuiteRecordFetchException,
    NetSuiteTokenExchangeException,
)
from netsuite.models import EmployeeConnection, NetSuiteConnection, NetSuiteCustomField, NetSuiteReferenceRecord, NetSuiteFieldCatalogue
from netsuite.oauth import (
    build_authorization_url,
    netsuite_vendor_bill_url,
    resolve_user_id_from_state,
)
from netsuite.repositories import NetSuiteConnectionRepository
from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from netsuite.token_manager import NetSuiteTokenManager
from netsuite.vendor_bill_baseline import VENDOR_BILL_BASELINE_FIELDS
from tenancy.services import company_lifecycle_service
from ocr.models import OCRValidationResult, ValidationStatus

logger = logging.getLogger(__name__)

# NetSuite metadata/catalogue uses script-style field IDs, while the REST
# Records API expects camelCase JSON properties for these standard fields.
# Keep catalogue IDs unchanged in saved mappings; translate only when
# constructing the outbound REST payload.
NETSUITE_REST_BODY_FIELD_NAMES = {
    "tranid": "tranId",
    "trandate": "tranDate",
    "duedate": "dueDate",
}

def _build_template_netsuite_mappings(
    requested_fields: dict,
    *,
    connection=None,
    record_type: str = "vendorBill",
) -> list[dict]:
    """Build posting/validation mappings exclusively from the selected OCR template.

    ``OCRBatch.requested_fields_json`` is a snapshot of the saved template used
    for this OCR run. The legacy OCRNetSuiteFieldMapping table is deliberately
    not consulted here, so stale/global rows cannot override the selected
    template's source field, NetSuite field ID, scope, or sublist.
    """
    if not isinstance(requested_fields, dict) or not requested_fields:
        raise ValueError(
            "This OCR upload has no saved template configuration. Select a saved "
            "template and upload/process the document again."
        )

    standard_fields = requested_fields.get("standard_fields") or []
    standard_overrides = requested_fields.get("standard_field_overrides") or {}
    custom_fields = requested_fields.get("custom_fields") or []

    if not isinstance(standard_fields, list):
        raise ValueError("The selected template has an invalid standard_fields list.")
    if not isinstance(standard_overrides, dict):
        raise ValueError("The selected template has invalid standard field mappings.")
    if not isinstance(custom_fields, list):
        raise ValueError("The selected template has an invalid custom_fields list.")

    # NetSuiteFieldCatalogue stores live target-field metadata (datatype,
    # required flag, and sublist identity). It is reference metadata only;
    # source-to-target mapping always comes from this saved template.
    catalogue_fields: list[dict] = []
    if connection is not None:
        catalogue = (
            NetSuiteFieldCatalogue.objects
            .filter(connection=connection, record_type=record_type)
            .first()
        )
        if catalogue is not None:
            for fallback_scope, fields in (
                ("body", catalogue.body_fields or []),
                ("column", catalogue.line_fields or []),
            ):
                for field in fields:
                    if not isinstance(field, dict):
                        continue
                    field_id = str(field.get("field_id") or field.get("id") or "").strip()
                    if not field_id:
                        continue
                    raw_scope = str(field.get("scope") or fallback_scope).strip().lower()
                    normalized_scope = (
                        "column"
                        if raw_scope in {"line", "column", "sublist"}
                        else "body"
                    )
                    sublist_id = str(
                        field.get("sublist_id")
                        or field.get("sublist")
                        or field.get("sublistId")
                        or ""
                    ).strip().lower() if normalized_scope == "column" else ""
                    catalogue_fields.append({
                        **field,
                        "field_id": field_id,
                        "_normalized_scope": normalized_scope,
                        "_normalized_sublist_id": sublist_id,
                    })

    mappings: list[dict] = []
    seen_targets: set[tuple[str, str, str]] = set()

    def add_mapping(source_key, config, *, is_custom):
        source_key = str(source_key or "").strip()
        if not source_key:
            return
        if not isinstance(config, dict):
            raise ValueError(
                f'Template mapping for "{source_key}" must be an object.'
            )

        target_field_id = str(config.get("netsuite_field_id") or "").strip()
        if not target_field_id:
            raise ValueError(
                f'Template field "{config.get("label") or source_key}" has no '
                "NetSuite Field ID. Edit and save the template before posting."
            )

        source_scope = (
            "line"
            if str(config.get("scope") or "header").strip().lower() == "line"
            else "header"
        )
        raw_target_scope = str(config.get("netsuite_field_scope") or "").strip().lower()
        if not raw_target_scope:
            target_scope = "column" if source_scope == "line" else "body"
        elif raw_target_scope in {"line", "column", "sublist"}:
            target_scope = "column"
        elif raw_target_scope in {"body", "header"}:
            target_scope = "body"
        else:
            raise ValueError(
                f'Template field "{config.get("label") or source_key}" has an '
                f'unsupported NetSuite field scope "{raw_target_scope}".'
            )

        if source_scope == "header" and target_scope != "body":
            raise ValueError(
                f'Template field "{config.get("label") or source_key}" is a '
                "header field but targets a NetSuite line/sublist field."
            )
        if source_scope == "line" and target_scope != "column":
            raise ValueError(
                f'Template field "{config.get("label") or source_key}" is a '
                "line field but targets a NetSuite body field."
            )

        target_sublist_id = str(
            config.get("netsuite_field_sublist_id") or ""
        ).strip().lower()
        target_identity = (
            target_field_id.casefold(),
            target_scope,
            target_sublist_id,
        )
        if target_identity in seen_targets:
            raise ValueError(
                f'NetSuite field "{target_field_id}" is mapped more than once '
                "in the selected template for the same scope/sublist. Use a "
                "distinct target field for each source field."
            )
        seen_targets.add(target_identity)

        target_metadata_candidates = [
            field for field in catalogue_fields
            if str(field.get("field_id") or "").strip().casefold()
            == target_field_id.casefold()
            and field.get("_normalized_scope") == target_scope
            and (
                target_scope == "body"
                or not target_sublist_id
                or field.get("_normalized_sublist_id") == target_sublist_id
            )
        ]
        if target_scope == "column" and not target_sublist_id:
            candidate_sublists = {
                field.get("_normalized_sublist_id")
                for field in target_metadata_candidates
            }
            if len(candidate_sublists) > 1:
                raise ValueError(
                    f'NetSuite field "{target_field_id}" exists on multiple '
                    "sublists. Reopen the template and select the correct field "
                    "context (Item or Expense)."
                )
        target_metadata = (
            target_metadata_candidates[0]
            if target_metadata_candidates else {}
        )
        if target_metadata and target_scope == "column":
            metadata_sublist = target_metadata.get("_normalized_sublist_id") or ""
            if target_sublist_id and metadata_sublist and metadata_sublist != target_sublist_id:
                raise ValueError(
                    f'NetSuite field "{target_field_id}" no longer matches the '
                    "sublist saved in the selected template. Edit and save the template again."
                )
            target_sublist_id = target_sublist_id or metadata_sublist

        label = str(config.get("label") or source_key).strip()
        mappings.append(
            {
                "source_field_key": source_key,
                "source_field_label": label,
                "source_scope": source_scope,
                "source_datatype": str(config.get("data_type") or "text").strip().lower(),
                "target_field_id": target_field_id,
                "target_field_label": str(
                    target_metadata.get("label")
                    or config.get("target_field_label")
                    or target_field_id
                ).strip(),
                "target_scope": target_scope,
                "target_sublist_id": target_sublist_id,
                "target_datatype": str(
                    target_metadata.get("datatype")
                    or config.get("target_datatype")
                    or config.get("netsuite_field_datatype")
                    or ""
                ).strip().lower(),
                "is_required": bool(
                    target_metadata.get("is_required", config.get("is_required", False))
                ),
                "target_is_custom": bool(target_metadata.get("is_custom", False)),
                "reference_type": target_metadata.get("reference_type"),
                # This flag describes whether the OCR source key is a custom
                # template field, not whether the NetSuite target is custom.
                "is_custom": is_custom,
            }
        )

    for raw_key in standard_fields:
        source_key = str(raw_key or "").strip()
        if not source_key or source_key == "line_items":
            continue
        add_mapping(
            source_key,
            standard_overrides.get(source_key),
            is_custom=False,
        )

    from ocr.notebook_extraction_service import _slugify_field_key

    for custom in custom_fields:
        if not isinstance(custom, dict):
            raise ValueError("A custom field in the selected template is invalid.")
        if custom.get("enabled") is False:
            continue
        raw_source_key = str(custom.get("key") or custom.get("label") or "").strip()
        source_key = _slugify_field_key(raw_source_key) if raw_source_key else ""
        if not source_key:
            raise ValueError("Every custom template field must have a key or label.")
        add_mapping(source_key, custom, is_custom=True)

    if not mappings:
        raise ValueError(
            "No NetSuite field mappings are configured in the selected OCR template."
        )
    return mappings

def raise_if_reauth_required(connection) -> None:
    """
    A connection whose tokens were cleared after ``invalid_grant`` can never
    refresh silently. Report that as a token error (-> 401
    NETSUITE_REAUTH_REQUIRED) instead of a generic "not active" message.
    """
    if connection.status == "error" and not connection.refresh_token:
        raise NetSuiteTokenExchangeException(
            "NETSUITE_INVALID_GRANT: NetSuite authorization is no longer "
            "valid. Re-authorization is required."
        )


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
        # client: NetSuiteAuthClient | None = None,
        token_manager: NetSuiteTokenManager | None = None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()
        self.token_manager = token_manager or NetSuiteTokenManager(repository=self.repository)

    def _ensure_user_company_operational(self, *, user: User) -> None:
        company = getattr(user, 'company', None)

        if company is not None:
            company_lifecycle_service.ensure_operational(
                company=company
            )
    
    def get_authorization_url(self, *, user: User, connection,post_connect_redirect_url: str | None = None) -> str:
        """Step 1: build the URL the frontend should redirect the browser to."""
        self._ensure_user_company_operational(user=user)
        return build_authorization_url(user_id=str(user.id),connection_id=str(connection.id),account_id=connection.netsuite_account_id,
        client_id=connection.client_id,post_connect_redirect_url=post_connect_redirect_url,)

    def get_reconnect_url(self, *, user: User, connection_id) -> str:
        """
        Build a fresh authorize URL for an EXISTING connection so its
        stored client credentials are reused and only the OAuth grant is
        renewed. The callback (complete_OAuth) restores status/is_active.
        """
        connection = self.repository.get_for_company(
            connection_id=connection_id,
            company=user.company,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection not found or not accessible."
            )
        return self.get_authorization_url(user=user, connection=connection)

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
                # NetSuite forces re-authorization this long after consent,
                # however often the refresh token is rotated.
                refresh_token_expires_at=(
                    timezone.now()
                    + timedelta(hours=NETSUITE_MAX_TOKEN_ROTATION_HOURS)
                ),
            )
            if user.current_netsuite_connection_id is None:
                user.current_netsuite_connection = connection
                user.save(
                    update_fields=[
                        "current_netsuite_connection",
                        "updated_at",
                    ]
                )
            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.CONNECT,
                entity="NetSuiteConnection",
                entity_id=str(connection.id),
                company=connection.company,
                user=user,
                new_value={
                    "event": "oauth_completed",
                    "account_name": connection.netsuite_account_id,
                    "client_name": connection.client_name,
                },
            )

            # Reference/master-data synchronization is intentionally not triggered
            # from the OAuth callback. Connecting a NetSuite account must not depend
            # on Celery or Redis availability.
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

            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.CONNECT,
                entity="NetSuiteConnection",
                entity_id=str(connection.id),
                company=connection.company,
                user=user,
                new_value={
                    "event": "oauth_failed",
                    "account_name": connection.netsuite_account_id,
                    "client_name": connection.client_name,
                    "detail": str(exc)[:1000],
                },
            )
            raise


    # def list_connections(self,*,user:User):
    #     self._ensure_user_company_operational(user=user)
    #     return self.repository.list_by_user(user)
    
    def create_connection(
            self,*,
            user:User,
            client_name:str,
            environment:str,
            client_id:str,
            client_secret:str,
            netsuite_account_id:str,
            callback_uri: str | None = None,
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
            )

            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.CONNECT,
                entity="NetSuiteConnection",
                entity_id=str(connection.id),
                company=connection.company,
                user=user,
                new_value={
                    "event": "oauth_retry_started",
                    "account_name": connection.netsuite_account_id,
                    "client_name": connection.client_name,
                },
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

            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.CREATE,
                entity="NetSuiteConnection",
                entity_id=str(connection.id),
                company=connection.company,
                user=user,
                new_value={
                    "event": "created",
                    "account_name": connection.netsuite_account_id,
                    "client_name": connection.client_name,
                },
            )

        authorization_url = self.get_authorization_url(user=user,connection=connection,post_connect_redirect_url=callback_uri)

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
        audit_service.log(
            module=AuditModule.NETSUITE,
            action=AuditAction.UPDATE,
            entity="NetSuiteConnection",
            entity_id=str(renamed.id),
            company=renamed.company,
            user=user,
            old_value={
                "client_name": old_name,
            },
            new_value={
                "event": "renamed",
                "client_name": client_name,
                "detail": f'"{old_name}" -> "{client_name}"',
                "account_name": renamed.netsuite_account_id,
            },
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

        audit_service.log(
            module=AuditModule.NETSUITE,
            action=AuditAction.DELETE,
            entity="NetSuiteConnection",
            entity_id=str(connection.id),
            company=connection.company,
            user=user,
            old_value={
                "event": "deleted",
                "account_name": connection.netsuite_account_id,
                "client_name": connection.client_name,
                "environment": connection.environment,
            },
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
            
        user.current_netsuite_connection = connection
        user.save(
            update_fields=[
                "current_netsuite_connection",
                "updated_at",
            ]
        )
        audit_service.log(
            module=AuditModule.NETSUITE,
            action=AuditAction.UPDATE,
            entity="NetSuiteConnection",
            entity_id=str(connection.id),
            company=connection.company,
            user=user,
            new_value={
                "event": "switched_active",
                "account_name": connection.netsuite_account_id,
                "client_name": connection.client_name,
            },
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

        role = getattr(user, "role", None)

        return role is not None and role.name.lower() == "company admin"

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
        

    # def get_employee_connection(self, *, employee_id):

    #     user = User.objects.select_related("company").get(pk=employee_id)

    #     return self.repository.get_for_user(user)

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

            audit_service.log(
                module=AuditModule.NETSUITE,
                action=AuditAction.CONNECT,
                entity="NetSuiteConnection",
                entity_id=str(connection.id),
                company=connection.company,
                user=connection.user,
                new_value={
                    "event": "oauth_failed",
                    "account_name": connection.netsuite_account_id,
                    "client_name": connection.client_name,
                    "detail": error_message[:1000],
                },
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

    def execute_suiteql(self, *, query: str, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        """
        Run a SuiteQL query for `user`'s connected NetSuite account.

        # Reuses _get_authenticated_client() — the same connection lookup
        # and token-refresh path get_records()/get_record() already use —
        # so authentication logic isn't duplicated for SuiteQL. The Client
        Reuses _get_authenticated_client() so connection lookup and token
        refresh logic stay centralized. The Client
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

    # def get_customers(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
    #     return self.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=user, limit=limit, offset=offset)

    # def get_employees(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
    #     return self.get_records(record_type=NetSuiteRecordType.EMPLOYEE, user=user, limit=limit, offset=offset)

    # def get_vendors(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
    #     return self.get_records(record_type=NetSuiteRecordType.VENDOR, user=user, limit=limit, offset=offset)

    # def get_sales_orders(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
    #     return self.get_records(record_type=NetSuiteRecordType.SALES_ORDER, user=user, limit=limit, offset=offset)
    
    # def get_purchase_orders(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
    #     return self.get_records(record_type=NetSuiteRecordType.PURCHASE_ORDER, user=user, limit=limit, offset=offset)
    
    # def get_invoices(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
    #     return self.get_records(record_type=NetSuiteRecordType.INVOICE, user=user, limit=limit, offset=offset)

    # def get_items(self, *, user: User, item_type: str = NetSuiteRecordType.INVENTORY_ITEM, limit: int | None = None, offset: int | None = None) -> dict:
    #     if not NetSuiteRecordType.is_valid(item_type):
    #         raise ValueError(f"Invalid NetSuite item type: {item_type}")
    #     return self.get_records(record_type=item_type, user=user, limit=limit, offset=offset)--------
    # SuiteQL-based list methods
    #
    # The plain REST record collection endpoint, accessed via
    # get_records(), returns only {id, links} per item —
    # no business fields at all. This is documented NetSuite behavior,
    # not a bug in this client: see "Listing All Record Instances" in
    # Oracle's NetSuite REST API docs, which shows exactly this shape.
    # Getting field data out of the plain collection endpoint requires
    # fetching every record individually (N+1 — slow, and not what we
    # want), so list pages use SuiteQL instead: one call, exact fields,
    # no extra round trips.
    #
    # Field verification status:
    #''' - customer/vendor id/entityid/companyname/email fields: already
    #   verified against a live NetSuite sandbox (see analytics/services.py).
    # - transaction id/tranid/entity/foreigntotal/trandate/type fields:
    #   same — already verified in analytics/services.py.
    # - employee, inventoryitem fields and BUILTIN.DF() usage below:
    #   NOT yet verified against this project's NetSuite sandbox —
    #   sourced from Oracle's official SuiteQL documentation and
    #   confirmed community examples, but should be tested against a
    #   real account and adjusted if any field name doesn't match.'''
    #  Vendor id/entityid/companyname/email fields: verified against a
    #   live NetSuite sandbox in analytics/services.py.
    # - Inventory item fields and BUILTIN.DF() usage below: not yet
    #   verified against this project's NetSuite sandbox; test against a
    #   real account if a field name fails for that account--------

    def _list_via_suiteql(self, *, user: User, query: str, limit: int, offset: int) -> dict:
        response = self.execute_suiteql(query=query, user=user, limit=limit, offset=offset)
        return {
            'items': response.get('items', []),
            'totalResults': response.get('totalResults', 0),
        }

    # def list_customers(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     raw = self._list_via_suiteql(
    #         user=user, limit=limit, offset=offset,
    #         query="""
    #             SELECT id, entityid, companyname, email, phone, isinactive
    #             FROM customer
    #             ORDER BY id
    #         """,
    #     )
    #     raw['items'] = [
    #         {
    #             'id': row.get('id'),
    #             'entityId': row.get('entityid'),
    #             'companyName': row.get('companyname'),
    #             'email': row.get('email'),
    #             'phone': row.get('phone'),
    #             'status': 'Inactive' if row.get('isinactive') == 'T' else 'Active',
    #         }
    #         for row in raw['items']
    #     ]
    #     return raw

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

    # def list_employees(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     raw = self._list_via_suiteql(
    #         user=user, limit=limit, offset=offset,
    #         query="""
    #             SELECT id, entityid, firstname, lastname, email, title,
    #                    BUILTIN.DF(department) AS department
    #             FROM employee
    #             ORDER BY id
    #         """,
    #     )
    #     raw['items'] = [
    #         {
    #             'id': row.get('id'),
    #             'entityId': row.get('entityid'),
    #             'firstName': row.get('firstname'),
    #             'lastName': row.get('lastname'),
    #             'email': row.get('email'),
    #             'title': row.get('title'),
    #             'department': row.get('department'),
    #         }
    #         for row in raw['items']
    #     ]
    #     return raw

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

    # def _list_transactions_via_suiteql(self, *, user: User, transaction_type: str, limit: int, offset: int) -> dict:
    #     """Shared by sales orders/purchase orders/invoices — all live in NetSuite's single `transaction` table, discriminated by `type`."""
    #     raw = self._list_via_suiteql(
    #         user=user, limit=limit, offset=offset,
    #         query=f"""
    #             SELECT id, tranid, entity, BUILTIN.DF(entity) AS entityname,
    #                    BUILTIN.DF(status) AS status, foreigntotal, trandate
    #             FROM transaction
    #             WHERE type = '{transaction_type}'
    #             ORDER BY id
    #         """,
    #     )
    #     raw['items'] = [
    #         {
    #             'id': row.get('id'),
    #             'tranId': row.get('tranid'),
    #             'entity': {'id': row.get('entity'), 'name': row.get('entityname')},
    #             'status': row.get('status'),
    #             'total': row.get('foreigntotal'),
    #             'createdDate': row.get('trandate'),
    #         }
    #         for row in raw['items']
    #     ]
    #     return raw

    # def list_sales_orders(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     return self._list_transactions_via_suiteql(user=user, transaction_type='SalesOrd', limit=limit, offset=offset)

    # def list_purchase_orders(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     return self._list_transactions_via_suiteql(user=user, transaction_type='PurchOrd', limit=limit, offset=offset)

    # def list_invoices(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     return self._list_transactions_via_suiteql(user=user, transaction_type='CustInvc', limit=limit, offset=offset)

    # def list_cash_sales(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     return self._list_transactions_via_suiteql(
    #         user=user,
    #         transaction_type='CashSale',
    #         limit=limit,
    #         offset=offset,
    #     )
    
    # def list_vendor_bills(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     return self._list_transactions_via_suiteql(
    #         user=user,
    #         transaction_type='VendBill',
    #         limit=limit,
    #         offset=offset,
    #     )
    
    # def list_vendor_payments(self, *, user: User, limit: int = 20, offset: int = 0) -> dict:
    #     return self._list_transactions_via_suiteql(
    #         user=user,
    #         transaction_type='VendPymt',
    #         limit=limit,
    #         offset=offset,
    #     )
        

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
            role = getattr(user, "role", None)

            return role is not None and role.name.lower() == "company admin"
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
    def _normalise_mapped_value(value, mapping, *, line_number=None):
        """Return a JSON-safe value using the target field's saved metadata.

        The template snapshot determines both the source key and the NetSuite
        target key.  This helper only normalises values (for example OCR's
        numeric strings); it never substitutes another source field.
        """
        field_label = (
            mapping.get("target_field_label")
            or mapping.get("target_field_id")
            or "field"
        )
        prefix = f"Line {line_number}: " if line_number is not None else ""

        if isinstance(value, str):
            value = value.strip()

        if value in (None, ""):
            return None

        datatype = str(
            mapping.get("target_datatype")
            or mapping.get("source_datatype")
            or ""
        ).strip().lower()

        if isinstance(value, (list, tuple, set)):
            raise ValueError(
                f"{prefix}NetSuite {field_label} must have one value."
            )

        if isinstance(value, dict):
            record_id = value.get("id")
            if record_id not in (None, ""):
                return {"id": str(record_id).strip()}
            raise ValueError(
                f"{prefix}NetSuite {field_label} needs an internal ID."
            )

        if datatype in {
            "integer", "number", "currency", "decimal", "float",
            "percent", "percentage",
        }:
            if isinstance(value, bool):
                raise ValueError(f"{prefix}NetSuite {field_label} must be numeric.")
            try:
                numeric_value = float(str(value).replace(",", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{prefix}NetSuite {field_label} value {value!r} is not numeric."
                ) from exc
            return int(numeric_value) if numeric_value.is_integer() else numeric_value

        if datatype in {"checkbox", "boolean", "bool"}:
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"true", "t", "yes", "y", "1"}:
                return True
            if normalized in {"false", "f", "no", "n", "0"}:
                return False
            raise ValueError(f"{prefix}NetSuite {field_label} must be true or false.")

        return value

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
                "netsuite_record_url": netsuite_vendor_bill_url(
                    account_id=existing.connection.netsuite_account_id,
                    record_id=existing.netsuite_record_id,
                ),
                "already_posted": True,
            }

        # Reuse the exact vendor/item IDs selected by the successful
        # validation result. Posting never performs a second fuzzy/ambiguous
        # item lookup.
        validated_vendor_id = validation.vendor_netsuite_id
        if not validated_vendor_id:
            raise ValueError(
                "Validated result does not contain a NetSuite vendor ID."
            )

        item_validation_results = validation.items or []

        # Validation is authoritative for the exact NetSuite item selected by
        # the user. Do not perform a second live name search during posting:
        # a name can match multiple NetSuite item records and the posting
        # step must never silently choose a different record than validation.
        validated_items_by_line = {}
        for validated_item in item_validation_results:
            if not isinstance(validated_item, dict):
                continue
            line_index = validated_item.get("line_index")
            if line_index is None:
                continue
            validated_items_by_line[str(line_index)] = validated_item

        # Build mappings from the exact template snapshot used for this OCR upload.
        # Do not read a legacy mapping table here: separate rows may contain stale
        # mappings from the separate Field Mapping screen and must not override
        # the user's selected template.
        upload = getattr(document, "upload", None)
        batch = getattr(upload, "batch", None) if upload else None

        requested_fields = (
            getattr(batch, "requested_fields_json", None)
            if batch else None
        )
        template_mappings = _build_template_netsuite_mappings(
            requested_fields,
            connection=connection,
            record_type="vendorBill"
        )

        item_line_mappings = [
            mapping for mapping in template_mappings
            if mapping.get("source_scope") == "line"
            and mapping.get("target_scope") == "column"
            and mapping.get("target_sublist_id") in {"", "item", "items"}
        ]
        item_mapping = next(
            (
                mapping for mapping in item_line_mappings
                if str(mapping.get("target_field_id") or "").strip().lower()
                in {"item", "items"}
            ),
            None,
        )
        if item_mapping is None:
            raise ValueError(
                "The selected template must map one line field to NetSuite Item."
            )

        unsupported_line_mappings = [
            mapping for mapping in template_mappings
            if mapping.get("source_scope") == "line"
            and mapping.get("target_scope") == "column"
            and mapping.get("target_sublist_id") not in {"", "item", "items"}
        ]
        if unsupported_line_mappings:
            labels = ", ".join(
                str(mapping.get("target_field_label") or mapping.get("target_field_id"))
                for mapping in unsupported_line_mappings
            )
            raise ValueError(
                "The selected template contains line mappings outside the Vendor "
                f"Bill Item sublist: {labels}."
            )

        payload_items = []
        item_source_key = item_mapping["source_field_key"]
        for index, line in enumerate(line_items, start=1):
            if not isinstance(line, dict):
                raise ValueError(f"Line {index}: OCR line item is invalid.")

            item_name = line.get(item_source_key)
            if isinstance(item_name, str):
                item_name = item_name.strip()
            if item_name in (None, ""):
                continue

            validated_item = validated_items_by_line.get(str(index))
            if not isinstance(validated_item, dict):
                raise ValueError(
                    f"Line {index}: no persisted NetSuite item validation exists "
                    "for this OCR line. Validate the document again before posting."
                )
            if validated_item.get("ambiguous"):
                raise ValueError(
                    f'Line {index}: multiple NetSuite items were matched for '
                    f'"{item_name}" during validation. Please correct the item '
                    "mapping and validate again."
                )
            if not validated_item.get("matched"):
                raise ValueError(
                    f'Line {index}: NetSuite item "{item_name}" was not '
                    "successfully validated. Validate the document again before posting."
                )

            item_id = validated_item.get("netsuite_id")
            if not item_id:
                raise ValueError(f"Line {index}: validated NetSuite item ID is missing.")

            item_payload = {}
            for mapping in item_line_mappings:
                target_field_id = str(mapping.get("target_field_id") or "").strip()
                target_key = target_field_id.lower()
                if target_key in {"item", "items"}:
                    # ``item`` is the Vendor Bill REST column name. The source
                    # field remains fully template-driven; the value is the ID
                    # selected during validation, never a second text lookup.
                    item_payload["item"] = {"id": str(item_id)}
                    continue

                mapped_value = self._normalise_mapped_value(
                    line.get(mapping["source_field_key"]),
                    mapping,
                    line_number=index,
                )
                if mapped_value is not None:
                    item_payload[target_field_id] = mapped_value

            payload_items.append(item_payload)

        payload = {}

        # Every Vendor Bill body field comes from the saved OCR-template
        # snapshot. This includes custom ``custbody_*`` fields; a separate
        # database mapping must never add, replace, or redirect a value.
        body_field_mappings = [
            mapping for mapping in template_mappings
            if mapping.get("source_scope") == "header"
            and mapping.get("target_scope") == "body"
        ]

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
        NETSUITE_VENDOR_BILL_UNSUPPORTED_FIELDS = {
            "entityid",
        }

        for mapping in body_field_mappings:
            target_field_id = str(
                mapping.get("target_field_id") or ""
            ).strip()
            if not target_field_id:
                continue

            target_field_key = target_field_id.strip().lower()
            if target_field_key in {"entity", "vendor"}:
                # The template must explicitly map its vendor source field to
                # Entity/Vendor.  The validated internal ID, rather than OCR
                # text, is the only value safe to send for that reference.
                payload["entity"] = {"id": str(validated_vendor_id)}
                continue

            api_field_name = NETSUITE_REST_BODY_FIELD_NAMES.get(
                target_field_key,target_field_id
            )
            if api_field_name.casefold() in {
                str(key).casefold() for key in payload
            }:
                # Already set explicitly above (entity/item), or a
                # duplicate mapping row — first mapping wins.
                continue

            if target_field_id.strip().lower() in NETSUITE_VENDOR_BILL_UNSUPPORTED_FIELDS:
                logger.warning(
                    "Skipping unsupported Vendor Bill body field mapping "
                    "— field=%s connection=%s",
                    target_field_id,
                    connection.id,
                )
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

            raw_value = self._normalise_mapped_value(
                data.get(mapping["source_field_key"]),
                mapping,
            )
            if raw_value is None:
                continue

            table_config = validation_service.SELECT_FIELD_SUITEQL_TABLES.get(
                target_field_id.strip().lower()
            )

            if table_config is not None:
                if isinstance(raw_value, dict) and raw_value.get("id"):
                    payload[api_field_name] = raw_value
                    continue
                resolved_id = validation_service._resolve_select_field_live(
                    connection=connection,
                    target_field_id=target_field_id,
                    value=raw_value,
                    require_unique=(
                        target_field_id.strip().lower() == "location"
                    ),
                )
                if resolved_id:
                    payload[api_field_name] = {"id": resolved_id}
                    continue

                if mapping.get("is_required", False):
                    raise ValueError(
                        f'"{raw_value}" could not be matched to an active '
                        f'NetSuite {mapping.get("target_field_label") or target_field_id} '
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

            if (mapping.get("target_datatype") or "").strip().lower() == "select":
                if isinstance(raw_value, dict) and raw_value.get("id"):
                    payload[api_field_name] = raw_value
                    continue
                # NetSuite does not accept a display name for arbitrary custom
                # select fields. Failing here is safer than silently omitting a
                # mapped value or writing it to a different field.
                raise ValueError(
                    f'NetSuite {mapping.get("target_field_label") or target_field_id} '
                    "requires an internal ID in the reviewed OCR data."
                )

            if api_field_name == "tranId":
                # Vendor Bill Reference No. supports up to 45 characters.
                raw_value = str(raw_value).strip()[:45]
            payload[api_field_name] = raw_value

        if "entity" not in payload:
            raise ValueError(
                "The selected template must map a header field to NetSuite Entity."
            )
        # NetSuite UI may default the header Location onto item rows, but the
        # REST API can require it explicitly for inventory items.
        header_location = payload.get("location")
        if (
            payload_items
            and isinstance(header_location,dict)
            and header_location.get("id") not in (None,"")
        ):
            for item_payload in payload_items:
                # A separately mapped line Location, if present, must remain unchanged
                if not item_payload.get("location"):
                    item_payload["location"] = {
                        "id":str(header_location["id"]),
                    }
        if payload_items:
            payload["item"] = {"items":payload_items}

        # Stable reconciliation identity across versions and interrupted attempts.
        payload['externalId'] = f'agsuite-vb-{company.pk}-{document.pk}'


        logger.warning(
            "Vendor Bill payload summary before NetSuite POST — "
            "vendor_id=%s location_id=%s subsidiary=%s currency=%s "
            "item_count=%s item_lines=%s body_keys=%s custom_fields=%s "
            "connection=%s",
            str(validated_vendor_id),
            (payload.get("location") or {}).get("id"),
            payload.get("subsidiary"),
            payload.get("currency"),
            len(payload_items),
            [
                {
                    "item_id": line.get("item", {}).get("id"),
                    "quantity": line.get("quantity"),
                    "rate": line.get("rate"),
                    "location_id": line.get("location", {}).get("id"),
                }
                for line in payload_items
            ],
            sorted(payload.keys()),
            len(
                (payload.get("customFieldList") or {}).get(
                    "customField",
                    [],
                )
            )
            if isinstance(payload.get("customFieldList"), dict)
            else 0,
            connection.id,
        )

        # Final fail-closed item/subsidiary verification.
        # Validation may have happened earlier and the reviewed/mapped payload
        # is authoritative only after all final body mappings and line merges
        # are complete. Verify the exact item IDs that are about to be posted.
        if payload_items:
            payload_subsidiary = payload.get("subsidiary")
            payload_subsidiary_id = (
                payload_subsidiary.get("id")
                if isinstance(payload_subsidiary, dict)
                else None
            )

            # Subsidiary is account-specific. When the selected template maps
            # it, it is resolved above and checked against the items. Accounts
            # that do not use OneWorld subsidiaries are allowed to post without
            # inventing a subsidiary value.
            if payload_subsidiary_id in (None, ""):
                payload_subsidiary_id = None

            final_item_ids = []
            for line_number, item_payload in enumerate(
                payload_items,
                start=1,
            ):
                item_reference = (
                    item_payload.get("item")
                    if isinstance(item_payload, dict)
                    else None
                )
                item_id = (
                    item_reference.get("id")
                    if isinstance(item_reference, dict)
                    else None
                )

                if item_id in (None, ""):
                    raise ValueError(
                        f"Final Vendor Bill item line {line_number} "
                        "does not contain a NetSuite item ID."
                    )

                final_item_ids.append(str(item_id).strip())

            invalid_items = []
            if payload_subsidiary_id is not None:
                invalid_items = validation_service._validate_item_ids_for_subsidiary_live(
                    connection=connection,
                    item_ids=final_item_ids,
                    subsidiary_id=payload_subsidiary_id,
                )

            if invalid_items:
                invalid = invalid_items[0]
                reason = invalid.get("reason")
                item_name = invalid.get("name") or invalid.get("netsuite_id")
                item_id = invalid.get("netsuite_id")

                if reason == "SUBSIDIARY_MISMATCH":
                    raise ValueError(
                        f'NetSuite item "{item_name}" (internal ID {item_id}) '
                        f'is not associated with Vendor Bill subsidiary ID '
                        f'{payload_subsidiary_id}. '
                        "Associate the item with the transaction subsidiary "
                        "or choose a compatible item, then validate again."
                    )

                if reason == "INACTIVE":
                    raise ValueError(
                        f'NetSuite item "{item_name}" (internal ID {item_id}) '
                        "is inactive. Activate it or choose another item, "
                        "then validate again."
                    )

                raise ValueError(
                    f"NetSuite item internal ID {item_id} could not be "
                    "verified immediately before posting. Validate the "
                    "document again and retry."
                )

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
                "netsuite_record_url": netsuite_vendor_bill_url(
                    account_id=connection.netsuite_account_id,
                    record_id=str(record_id),
                ),
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

    # MAX_AI_MAPPING_ATTEMPTS = 2
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
        if connection.is_active:
            raise_if_reauth_required(connection)
        if connection.status != "connected" or not connection.is_active:
            raise NetSuiteConnectionNotFoundException(
                "NetSuite connection is not active."
            )
        return connection

    @staticmethod
    def _merge_baseline_fields(normalized):
        """
        Merge the static AGSuite Vendor Bill baseline with live NetSuite
        metadata while preserving the actual NetSuite sublist context.

        A field ID can legitimately exist in multiple sublists, for example:

            taxrate1 -> item
            taxrate1 -> expense

        Therefore field identity is:

        field_id + scope + sublist_id
        """
        live_body = list(normalized.get("body_fields") or [])
        live_column = list(normalized.get("line_fields") or [])

        live_fields = {}
        live_by_base = {}

        for field in [*live_body, *live_column]:
            field_id = str(field.get("field_id") or "").strip()
            if not field_id:
                continue

            scope = (
                "column"
                if str(field.get("scope") or "").lower() in {"line", "column", "sublist"}
                else "body"
            )
            sublist_id = (
                str(
                field.get("sublist_id") 
                or field.get("sublist") 
                or field.get("sublistId") 
                or "" 
                ).strip().lower() if scope == "column" else ""
            )

            normalized_field = {
                **field,
                "field_id": field_id,
                "scope": scope,
            }

            if sublist_id:
                normalized_field["sublist_id"] = sublist_id
            else:
                normalized_field.pop("sublist_id", None)
            
            key = (field_id, scope, sublist_id)
            live_fields[key] = normalized_field
            live_by_base.setdefault(
                (field_id, scope),
                [],
            ).append(key)

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
            exact_key = (field_id, scope, "")
            contextual_keys = live_by_base.get(
                (field_id, scope),
                [],
            )

            if exact_key in live_fields:
                live_field = live_fields.pop(exact_key)
                merged[exact_key] = {
                    **baseline_field,
                    **live_field,
                    "baseline": True,
                }
                continue

            # If NetSuite exposes contextual variants such as
            # item / expense, don't create an ambiguous generic
            # baseline entry.

            if contextual_keys:
                for key in contextual_keys:
                    live_field = live_fields.pop(key)

                    merged[key] = {
                        **baseline_field,
                        **live_field,
                        "baseline": True,
                    }

                continue
            merged[exact_key] = baseline_field

        # Preserve every account-specific/live field that was not in baseline.
        for key, field in live_fields.items():
            merged[key] = field

        body_fields = [
            field
            for (field_id, scope, sublist_id), field in merged.items()
            if scope == "body"
        ]

        column_fields = [
            field
            for (field_id, scope, sublist_id), field in merged.items()
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
        print(response)

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
        # with open("data.txt", "a", encoding="utf-8") as file:
        #     file.write(json.dumps(payload, indent=4) + "\n")
                # print("payload: ",payload)
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
        # for schemas in schema:
        #     print("schema: ", schema)
        value = str(
            schema.get("type")
            or schema.get("datatype")
            or schema.get("dataType")
            or "text"
        ).lower()
        # for values in value:
        #     print("value: ",value)
        
        fmt = str(schema.get("format") or "").lower()
        # for fmts in fmt:
        #     print("fmt: ",fmt)
        
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
    def _is_reference_value_schema(schema):
        """Return whether an object schema represents one selectable field.

        NetSuite represents select/reference fields as objects containing their
        identifier and display-name properties.  Those objects are leaves in a
        transaction sublist, not nested sublists to walk.
        """
        if not isinstance(schema, dict):
            return False

        properties = schema.get("properties")
        if str(schema.get("type") or "").lower() != "object" or not isinstance(properties, dict):
            return False

        return bool(properties) and set(properties).issubset(
            {"id", "refName", "externalId", "links"}
        )

    @staticmethod
    def _is_sublist_schema(schema):
        """Return whether a root metadata property is a transaction sublist.

        NetSuite represents transaction sublists as an object whose ``items``
        property is an array of line objects.  Vendor Bills commonly expose
        ``item`` and ``expense``, but account features and customisations add
        others (for example, landed costs and accounting-book details).
        """
        if not isinstance(schema, dict):
            return False

        properties = schema.get("properties")
        items = (
            properties.get("items")
            if isinstance(properties, dict)
            else schema
        )
        if not isinstance(items, dict):
            return False

        line_schema = items.get("items")
        return (
            str(items.get("type") or "").lower() == "array"
            and isinstance(line_schema, dict)
            and isinstance(line_schema.get("properties"), dict)
            and bool(line_schema.get("properties"))
        )

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
        properties = (
            schema.get("properties")
            if isinstance(schema, dict)
            else None
        )

        if not isinstance(properties, dict):
            return {
                "body_fields": [],
                "line_fields": [],
                "custom_fields": [],
                "raw_metadata": raw,
            }

        required = (
            set(schema.get("required", []))
            if isinstance(schema.get("required"), list)
            else set()
        )

        body_fields = []
        line_fields = []
        custom_fields = []

        def add_field(
            field_id,
            field_schema,
            scope,
            required_set,
            sublist_id=None,
        ):
            if not isinstance(field_schema, dict):
                field_schema = {}

            item = {
                "field_id": str(field_id),
                "label": cls._title_for(
                    str(field_id),
                    field_schema,
                ),
                "datatype": cls._normalise_datatype(
                    field_schema
                ),
                "scope": scope,
                "is_required": str(field_id) in required_set,
                "is_custom": cls._is_custom_field(
                    str(field_id),
                    field_schema,
                ),
                "reference_type": cls._reference_type(
                    field_schema
                ),
            }

            if scope == "column" and sublist_id:
                item["sublist_id"] = str(
                    sublist_id
                ).lower()

            target = (
                line_fields
                if scope == "column"
                else body_fields
            )

            target.append(item)

            if item["is_custom"]:
                custom_fields.append(item)

        def walk_sublist_schema(
            node,
            sublist_id,
            required_set=None,
        ):
            """
            Walk a NetSuite sublist schema while preserving
            the originating sublist context.

            Handles structures such as:

                item
                  -> properties
                    -> items
                      -> items
                        -> properties
                          -> taxRate1

            and the equivalent expense structure.
            """
            if not isinstance(node, dict):
                return

            current_required = (
                set(node.get("required", []) or [])
                if isinstance(node.get("required"), list)
                else set(required_set or [])
            )

            properties_node = node.get("properties")

            if isinstance(properties_node, dict):
                for nested_id, nested_schema in properties_node.items():
                    if not isinstance(nested_schema, dict):
                        nested_schema = {}

                    lower_nested_id = str(
                        nested_id
                    ).lower()

                    if lower_nested_id == "items":
                        walk_sublist_schema(
                            nested_schema,
                            sublist_id,
                            current_required,
                        )
                        continue

                    nested_properties = nested_schema.get(
                        "properties"
                    )
                    nested_items = nested_schema.get(
                        "items"
                    )

                    if (
                        (
                            isinstance(nested_properties, dict)
                            and not cls._is_reference_value_schema(nested_schema)
                        )
                        or isinstance(nested_items, dict)
                    ):
                        walk_sublist_schema(
                            nested_schema,
                            sublist_id,
                            set(
                                nested_schema.get(
                                    "required",
                                    []
                                )
                                or []
                            ),
                        )
                        continue

                    # Actual line-level field.
                    add_field(
                        nested_id,
                        nested_schema,
                        "column",
                        current_required,
                        sublist_id=sublist_id,
                    )

            # Also support schemas where the array is represented
            # directly through the JSON Schema "items" keyword.
            items_node = node.get("items")

            if isinstance(items_node, dict):
                walk_sublist_schema(
                    items_node,
                    sublist_id,
                    current_required,
                )

        # Root Vendor Bill fields
        for field_id, field_schema in properties.items():
            lower_id = str(field_id).lower()

            # Every metadata-defined Vendor Bill sublist.  ``item`` and
            # ``expense`` are the common cases, but this intentionally keeps
            # feature-specific and customisation-specific sublists available
            # in the field-mapping catalogue too.
            if cls._is_sublist_schema(field_schema):
                sublist_id = (
                    "item"
                    if lower_id == "items"
                    else lower_id
                )

                walk_sublist_schema(
                    field_schema,
                    sublist_id,
                    required,
                )

                continue

            # Normal body/header field.
            add_field(
                field_id,
                field_schema,
                "body",
                required,
            )

        def dedupe(fields):
            seen = set()
            output = []

            for field in fields:
                key = (
                    field.get("scope"),
                    field.get("sublist_id") or "",
                    field.get("field_id"),
                )

                if key in seen:
                    continue

                seen.add(key)
                output.append(field)

            return output

        body_fields = dedupe(body_fields)
        line_fields = dedupe(line_fields)

        custom_fields = [
            field
            for field in dedupe(
                body_fields + line_fields
            )
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

    @staticmethod
    def _catalogue_field_key(field, fallback_scope=None):
        if not isinstance(field, dict):
            return None

        field_id = str(
            field.get('field_id') or field.get('id') or ''
        ).strip()

        if not field_id:
            return None

        raw_scope = str(
            field.get('scope') or fallback_scope or 'body'
        ).strip().lower()

        scope = (
            'column'
            if raw_scope in {'line', 'column', 'sublist'}
            else 'body'
        )

        sublist_id = ''

        if scope == 'column':
            sublist_id = str(
                field.get('sublist_id')
                or field.get('sublist')
                or field.get('sublistId')
                or ''
            ).strip().lower()

        return field_id.casefold(), scope, sublist_id


    @classmethod
    def _merge_catalogue_field_lists(
        cls,
        existing_fields,
        incoming_fields,
        fallback_scope=None,
    ):
        merged = []
        seen = set()

        for field in [
            *(existing_fields or []),
            *(incoming_fields or []),
        ]:
            if not isinstance(field, dict):
                merged.append(field)
                continue

            key = cls._catalogue_field_key(
                field,
                fallback_scope=fallback_scope,
            )

            if key is None:
                merged.append(dict(field))
                continue

            if key in seen:
                continue

            seen.add(key)
            merged.append(dict(field))

        return merged


    def _append_local_custom_fields(
        self,
        normalized,
        *,
        connection,
        record_type,
    ):
        local_custom = list(
            NetSuiteCustomField.objects.filter(
                company=connection.company,
                connection=connection,
                record_type=record_type,
                status__in=['created', 'pending'],
            ).values(
                'field_id',
                'field_label',
                'datatype',
                'scope',
            )
        )

        for field in local_custom:
            scope = (
                'column'
                if str(field.get('scope') or '').strip().lower()
                in {'column', 'line', 'sublist'}
                else 'body'
            )

            mapped = {
                'field_id': str(field.get('field_id') or '').strip(),
                'label': field.get('field_label') or field.get('field_id') or '',
                'datatype': field.get('datatype') or 'text',
                'scope': scope,
                'is_required': False,
                'is_custom': True,
                'reference_type': None,
            }

            if not mapped['field_id']:
                continue

            current = (
                normalized.setdefault('line_fields', [])
                if scope == 'column'
                else normalized.setdefault('body_fields', [])
            )

            key = self._catalogue_field_key(
                mapped,
                fallback_scope=scope,
            )

            existing_keys = {
                self._catalogue_field_key(item, fallback_scope=scope)
                for item in current
            }

            if key not in existing_keys:
                current.append(mapped)

        normalized['custom_fields'] = self._merge_catalogue_field_lists(
            normalized.get('custom_fields', []),
            [
                field
                for field in (
                    normalized.get('body_fields', [])
                    + normalized.get('line_fields', [])
                )
                if isinstance(field, dict) and field.get('is_custom')
            ],
        )

        return normalized


    def _catalogue_cache_miss_payload(
        self,
        *,
        connection,
        record_type,
        error=None,
    ):
        normalized = self._merge_baseline_fields({
            'body_fields': [],
            'line_fields': [],
            'custom_fields': [],
        })

        normalized = self._append_local_custom_fields(
            normalized,
            connection=connection,
            record_type=record_type,
        )

        return {
            'record_type': record_type,
            'fields': {
                'body': normalized.get('body_fields', []),
                'column': normalized.get('line_fields', []),
            },
            'custom_fields': normalized.get('custom_fields', []),
            'source': 'fallback',
            'stale': False,
            'available': False,
            'error': (
                error
                or 'No saved catalogue exists. A Company Admin can refresh it.'
            ),
            'fetched_at': None,
            'added_fields_count': 0,
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

        # Normal reads never call NetSuite.
        if not force_refresh:
            if existing:
                return self._catalogue_payload(
                    existing,source='database',
                )
            return self._catalogue_cache_miss_payload(
                connection=connection,
                record_type=record_type,
            )
        lock_key = f"netsuite:field-catalogue-refresh:{connection.pk}:{record_type}"
        lock_token = uuid.uuid4().hex
        cache_lock_owned = False
        try:
            lock_acquired = cache.add(  
                lock_key,
                lock_token,
                timeout=self.METADATA_TIMEOUT_SECONDS + 30,
            )
            cache_lock_owned = lock_acquired
        except Exception:
            # A cache outage should not make an explicitly requested refresh
            # impossible; the database row lock below still protects writes.
            logger.exception("Unable to acquire NetSuite catalogue refresh cache lock")
            lock_acquired = True
            cache_lock_owned = False

        if not lock_acquired:
            current = NetSuiteFieldCatalogue.objects.filter(
                connection=connection,
                record_type=record_type,
            ).first()
            if current:
                payload = self._catalogue_payload(
                    current,
                    source="database",
                    stale=True,
                    available=True,
                    error="A NetSuite field refresh is already in progress.",
                )
                payload.update({"added_fields_count": 0, "refresh_failed": True})
                return payload
            return self._catalogue_cache_miss_payload(
                connection=connection,
                record_type=record_type,
                error="A NetSuite field refresh is already in progress.",
            )

        try:
            raw = self._fetch_live_metadata(
                connection=connection,
                record_type=record_type,
            )
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

            with transaction.atomic():
                NetSuiteConnection.objects.select_for_update().get(
                    pk=connection.pk
                )
                current = (
                    NetSuiteFieldCatalogue.objects.select_for_update()
                    .filter(
                        connection=connection,
                        record_type=record_type,
                    ).first()
                )

                old_body = list(current.body_fields or []) if current else []
                old_line = list(current.line_fields or []) if current else []
                old_custom = list(current.custom_fields or []) if current else []

                merged_body = self._merge_catalogue_field_lists(
                    old_body,
                    normalized["body_fields"],
                    fallback_scope="body",
                )

                merged_line = self._merge_catalogue_field_lists(
                    old_line,
                    normalized["line_fields"],
                    fallback_scope="column",
                )

                def get_field_keys(body_fields, line_fields):
                    keys = set()

                    for field in body_fields:
                        key = self._catalogue_field_key(field,fallback_scope="body")
                        if key:
                            keys.add(key)

                    for field in line_fields:
                        key = self._catalogue_field_key(
                            field,
                            fallback_scope="column",
                        )
                        if key:
                            keys.add(key)
                    return keys

                old_keys = get_field_keys(old_body,old_line)

                incoming_keys = get_field_keys(
                    normalized["body_fields"],
                    normalized["line_fields"],
                )

                added_fields_count = len(incoming_keys - old_keys)

                merged_custom = self._merge_catalogue_field_lists(
                    old_custom,
                    normalized["custom_fields"],
                )

                catalogue, _ = NetSuiteFieldCatalogue.objects.update_or_create(
                    connection=connection,
                    record_type=record_type,
                    defaults={
                        "body_fields": merged_body,
                        "line_fields": merged_line,
                        "custom_fields": merged_custom,
                        "raw_metadata": raw,
                        "metadata_hash": metadata_hash,
                    },
                )
            payload = self._catalogue_payload(catalogue, source="netsuite", stale=False)
            payload["added_fields_count"] = added_fields_count
            return payload

        except NetSuiteTokenExchangeException:
            raise

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

            normalized_fallback = self._merge_baseline_fields(
                {
                    "body_fields": [],
                    "line_fields": [],
                    "custom_fields": [],
                }
            )
            fields = {
                "body": normalized_fallback["body_fields"],
                "column": normalized_fallback["line_fields"],
            }
            
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
                "added_fields_count":0,
            }
        finally:
            if cache_lock_owned:
                try:
                    if cache.get(lock_key) == lock_token:
                        cache.delete(lock_key)
                except Exception:
                    logger.exception(
                        "Unable to release NetSuite catalogue refresh cache lock"
                    )

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
        # Subsidiary ancestry is immutable for the duration of one service
        # instance. Cache it so validation does not re-query the same chain
        # for every item candidate. Keys are (connection_id, subsidiary_id).
        self._subsidiary_ancestor_cache = {}
    
    @staticmethod
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
        
        except NetSuiteTokenExchangeException:
            raise

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
        require_unique=False,
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

        except NetSuiteTokenExchangeException:
            raise

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
            if require_unique:
                raise ValueError(
                    f'Multiple active NetSuite {table} records match "{raw_value}". '
                    "Resolve duplicate names in NetSuite before posting."
                )
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
            include_error=True,
        )
        if connection is None:
            raise ValueError("No NetSuite connection available.")

        raise_if_reauth_required(connection)

        if (
            connection.status != "connected"
            or not connection.is_active
        ):
            raise ValueError(
                "NetSuite connection is not active."
            )
        
        # Template-based NetSuite mapping
        upload = getattr(document, "upload", None)
        batch = getattr(upload, "batch", None) if upload else None

        requested_fields = (
            getattr(batch, "requested_fields_json", None)
            if batch
            else None
        )
        template_mappings = _build_template_netsuite_mappings(
            requested_fields,
            connection=connection,
            record_type="vendorBill",
        )

        # The shared builder is the single source of truth for validation and posting.
        # It already validates the template JSON and returns enriched mapping dictionaries.

        vendor_mapping = next(
            (
                mapping
                for mapping in template_mappings
                if str(mapping.get("target_field_id") or "").strip().lower()
                in {"entity", "vendor"}
                and str(mapping.get("source_scope") or "").strip().lower()
                in {"header", "body"}
            ),
            None,
        )

        ITEM_MAPPING_FIELD_IDS = {"item", "items"}
        item_mapping = next(
            (
                mapping
                for mapping in template_mappings
                if str(mapping.get("target_field_id") or "").strip().lower()
                in ITEM_MAPPING_FIELD_IDS
                and str(mapping.get("source_scope") or "").strip().lower()
                == "line"
            ),
            None,
        )

        if vendor_mapping is None:
            raise ValueError(
                "Vendor field mapping is required before NetSuite reference validation."
            )

        # Resolve the Vendor Bill transaction subsidiary using the same
        # mapping and live select-field resolver used during posting.
        # Missing mapping/value is intentionally a skipped subsidiary check;
        # an explicitly supplied but unresolvable value is a validation error.
        subsidiary_mapping = next(
            (
                mapping
                for mapping in template_mappings
                if str(mapping.get("target_field_id") or "").strip().lower()
                == "subsidiary"
                and str(mapping.get("source_scope") or "").strip().lower()
                in {"header", "body"}
            ),
            None,
        )

        transaction_subsidiary_id = None
        transaction_subsidiary_name = None
        subsidiary_check = "skipped"
        subsidiary_validation_error = None

        if subsidiary_mapping is not None:
            raw_subsidiary_value = data.get(
                subsidiary_mapping["source_field_key"]
            )

            if isinstance(raw_subsidiary_value, str):
                raw_subsidiary_value = raw_subsidiary_value.strip()

            if raw_subsidiary_value not in (None, ""):
                if isinstance(raw_subsidiary_value, dict):
                    transaction_subsidiary_name = (
                        raw_subsidiary_value.get("name")
                        or raw_subsidiary_value.get("label")
                        or raw_subsidiary_value.get("text")
                    )
                    if transaction_subsidiary_name is not None:
                        transaction_subsidiary_name = str(
                            transaction_subsidiary_name
                        ).strip()

                    direct_id = raw_subsidiary_value.get("id")
                    if direct_id not in (None, ""):
                        transaction_subsidiary_id = str(direct_id).strip()
                    elif transaction_subsidiary_name:
                        transaction_subsidiary_id = (
                            self._resolve_select_field_live(
                                connection=connection,
                                target_field_id="subsidiary",
                                value=transaction_subsidiary_name,
                            )
                        )
                else:
                    transaction_subsidiary_name = str(
                        raw_subsidiary_value
                    ).strip()
                    if transaction_subsidiary_name:
                        transaction_subsidiary_id = (
                            self._resolve_select_field_live(
                                connection=connection,
                                target_field_id="subsidiary",
                                value=transaction_subsidiary_name,
                            )
                        )

                if transaction_subsidiary_id:
                    subsidiary_check = "passed"
                else:
                    subsidiary_validation_error = {
                        "type": "SUBSIDIARY_NOT_FOUND",
                        "message": (
                            f'NetSuite subsidiary "{transaction_subsidiary_name}" '
                            "could not be resolved in the selected account."
                        ),
                        "extracted_name": transaction_subsidiary_name,
                    }

        # A Vendor Bill must have one explicit active Location.
        location_mapping = next(
            (
                mapping
                for mapping in template_mappings
                if str(mapping.get("target_field_id") or "").strip().lower()
                == "location"
                and str(mapping.get("source_scope") or "").strip().lower()
                in {"header", "body"}
                and str(mapping.get("target_scope") or "").strip().lower()
                == "body"
            ),
            None,
        )

        location_name = None
        location_netsuite_id = None
        location_check = "failed"
        location_error = None

        if location_mapping is None:
            location_error = {
                "type": "LOCATION_MAPPING_REQUIRED",
                "message": (
                    "Add the Location standard field to the template and map it "
                    "to the NetSuite Location field."
                ),
                "extracted_name": None,
            }
        else:
            raw_location_value = data.get(
                location_mapping["source_field_key"]
            )

            if isinstance(raw_location_value, dict):
                location_name = (
                    raw_location_value.get("name")
                    or raw_location_value.get("label")
                    or raw_location_value.get("text")
                )
            else:
                location_name = raw_location_value

            if location_name is not None:
                location_name = str(location_name).strip()

            if not location_name:
                location_error = {
                    "type": "LOCATION_VALUE_MISSING",
                    "message": (
                        "Enter the exact NetSuite Location name in OCR review, "
                        "save the result, and validate again."
                    ),
                    "extracted_name": None,
                }
            else:
                try:
                    location_netsuite_id = self._resolve_select_field_live(
                        connection=connection,
                        target_field_id="location",
                        value=location_name,
                        require_unique=True,
                    )
                except ValueError as exc:
                    location_error = {
                        "type": "LOCATION_AMBIGUOUS",
                        "message": str(exc),
                        "extracted_name": location_name,
                    }

                if location_netsuite_id:
                    location_check = "passed"
                elif location_error is None:
                    location_error = {
                        "type": "LOCATION_NOT_FOUND",
                        "message": (
                            f'NetSuite Location "{location_name}" could not be '
                            "matched to one active Location in the selected account."
                        ),
                        "extracted_name": location_name,
                    }

        vendor_name = data.get(vendor_mapping["source_field_key"])

        if isinstance(vendor_name,str):
            vendor_name = vendor_name.strip()

        if not vendor_name:
            vendor_name = data.get("vendor_name")

        if isinstance(vendor_name,str):
            vendor_name = vendor_name.strip()

        if not vendor_name:
            raise ValueError(
                f'Vendor value is required. '
                f'Expected value in OCR field "{vendor_mapping["source_field_key"]}".'
            )

        line_items = data.get("line_items") or []

        if not isinstance(line_items, list):
            line_items = []
        
        vendor_result = self._validate_vendor_live(
            connection=connection,
            vendor_name=vendor_name,
        )

        # Validate only real Vendor Bill item rows. OCR can also return
        # account/tax/TDS/GST rows inside line_items; those rows do not have
        # quantity or unit price and must not become NetSuite item lines.
        if item_mapping is None:
            raise ValueError(
                "Item field mapping is required before NetSuite reference validation."
            )
        item_source_key = item_mapping["source_field_key"]
        real_item_lines = []
        real_item_line_indexes = []
        for line_index, line in enumerate(line_items, start=1):
            if not isinstance(line, dict):
                continue
            item_name = line.get(item_source_key)

            if item_name is None or not str(item_name).strip():
                continue

            real_item_lines.append(line)
            real_item_line_indexes.append(line_index)

        if item_mapping is None and real_item_lines:
            raise ValueError(
                "Item field mapping is required before NetSuite reference validation."
            )

        item_results = []
        if real_item_lines:
            raw_item_results = self._validate_items_live(
                connection=connection,
                line_items=real_item_lines,
                source_field_key=item_mapping["source_field_key"],
                subsidiary_id=transaction_subsidiary_id,
                subsidiary_name=transaction_subsidiary_name,
            )
            for result, original_line_index in zip(
                raw_item_results,
                real_item_line_indexes,
            ):
                result["line_index"] = original_line_index
                item_results.append(result)

        errors = []

        if subsidiary_validation_error:
            errors.append(subsidiary_validation_error)

        if location_error:
            errors.append(location_error)

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

        # Emit one subsidiary mismatch error per unique NetSuite item, while
        # retaining every affected OCR line number for traceability.
        mismatch_errors_by_key = {}

        for item in item_results:
            if item.get("item_subsidiary_mismatch"):
                item_id = item.get("netsuite_id")
                candidate_details = item.get("candidates") or []
                if item_id:
                    key = str(item_id)
                elif candidate_details:
                    key = str(
                        candidate_details[0].get("netsuite_id")
                    )
                else:
                    key = self._normalize_match_name(
                        item.get("extracted_name")
                    )

                existing_error = mismatch_errors_by_key.get(key)
                if existing_error is not None:
                    line_index = item.get("line_index")
                    if (
                        line_index is not None
                        and line_index not in existing_error["affected_lines"]
                    ):
                        existing_error["affected_lines"].append(line_index)
                    continue

                primary_candidate = (
                    candidate_details[0]
                    if candidate_details
                    else {}
                )
                primary_name = (
                    primary_candidate.get("name")
                    or item.get("extracted_name")
                    or "Unknown item"
                )
                primary_id = primary_candidate.get("netsuite_id") or item_id
                affected_lines = [
                    item.get("line_index")
                ] if item.get("line_index") is not None else []

                error = {
                    "type": "ITEM_SUBSIDIARY_MISMATCH",
                    "message": (
                        f'NetSuite item "{primary_name}" (internal ID '
                        f"{primary_id}) is not associated with Vendor Bill "
                        f'subsidiary "{item.get("transaction_subsidiary") or transaction_subsidiary_name or transaction_subsidiary_id}".'
                    ),
                    "extracted_name": item.get("extracted_name"),
                    "netsuite_id": primary_id,
                    "item_name": primary_name,
                    "item_subsidiary": primary_candidate.get(
                        "item_subsidiary"
                    ),
                    "transaction_subsidiary": (
                        item.get("transaction_subsidiary")
                        or transaction_subsidiary_name
                    ),
                    "transaction_subsidiary_id": str(
                        item.get("transaction_subsidiary_id")
                        or transaction_subsidiary_id
                        or ""
                    ),
                    "affected_lines": affected_lines,
                    "candidates": candidate_details,
                }
                mismatch_errors_by_key[key] = error
                errors.append(error)

            elif item.get("ambiguous"):
                errors.append({
                    "type": "ITEM_AMBIGUOUS",
                    "message": "Multiple possible items matched. Please confirm the item mapping.",
                    "extracted_name": item.get("extracted_name"),
                    "line_index": item.get("line_index"),
                    "candidates": item.get("candidates", []),
                })
            elif not item.get("matched"):
                errors.append({
                    "type": "ITEM_NOT_FOUND",
                    "message": "Item does not exist in the selected NetSuite account.",
                    "extracted_name": item.get("extracted_name"),
                    "line_index": item.get("line_index"),
                })

        matched_items = [
            item
            for item in item_results
            if item.get("matched")
        ]
        unique_netsuite_items = {
            str(item.get("netsuite_id"))
            for item in matched_items
            if item.get("netsuite_id") not in (None, "")
        }

        summary = {
            "source_rows": len(real_item_lines),
            "matched_rows": len(matched_items),
            "unique_netsuite_items": len(unique_netsuite_items),
            "unmatched_rows": max(
                0,
                len(real_item_lines) - len(matched_items),
            ),
        }

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
            "summary": summary,
            "subsidiary": {
                "check": subsidiary_check,
                "name": transaction_subsidiary_name,
                "netsuite_id": (
                    str(transaction_subsidiary_id)
                    if transaction_subsidiary_id
                    else None
                ),
            },
            "location": {
                "check": location_check,
                "name": location_name,
                "netsuite_id": (
                    str(location_netsuite_id)
                    if location_netsuite_id
                    else None
                ),
            },
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

    @staticmethod
    def _suiteql_id_literal(value):
        """Return a safe SuiteQL literal for an internal record ID."""
        raw = str(value or "").strip()
        if not raw:
            return None

        # NetSuite internal IDs are normally numeric. Keep numeric IDs
        # unquoted; fall back to the existing SQL-escaped literal helper for
        # defensive handling of unexpected non-numeric identifiers.
        if re.fullmatch(r"\d+", raw):
            return raw

        return NetSuiteValidationService._suiteql_literal(raw)

    def _get_subsidiary_ancestors_live(
        self,
        *,
        connection,
        subsidiary_id,
    ):
        """Return parent subsidiary IDs from nearest parent to root.

        NetSuite subsidiaries form a hierarchy. We resolve the parent chain
        live instead of hard-coding account-specific IDs. A cycle guard keeps
        malformed master data from causing an infinite loop.
        """
        raw_id = str(subsidiary_id or "").strip()
        if not raw_id:
            return []

        cache_key = (str(connection.id), raw_id)
        cached = self._subsidiary_ancestor_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        ancestors = []
        seen = {raw_id}
        current_id = raw_id
        max_depth = 100

        for _ in range(max_depth):
            literal = self._suiteql_id_literal(current_id)
            if literal is None:
                break

            query = f"""
                SELECT
                    id,
                    parent
                FROM subsidiary
                WHERE id = {literal}
                ORDER BY id
            """

            response = self._execute_live_suiteql(
                connection=connection,
                query=query,
                limit=5,
            )

            rows = (
                response.get("items", [])
                if isinstance(response, dict)
                else []
            )

            row = next(
                (item for item in rows if isinstance(item, dict)),
                None,
            )

            if row is None:
                # The subsidiary ID was resolved from NetSuite just before
                # this lookup. If its hierarchy record cannot be read now,
                # ancestry-based compatibility cannot be established safely.
                # Fail closed instead of reporting a misleading mismatch.
                raise NetSuiteRecordFetchException(
                    f"Unable to resolve the parent hierarchy for NetSuite "
                    f"subsidiary {current_id}."
                )

            raw_parent = row.get("parent")
            if isinstance(raw_parent, dict):
                raw_parent = (
                    raw_parent.get("id")
                    or raw_parent.get("value")
                    or raw_parent.get("internal_id")
                )

            parent_id = str(raw_parent or "").strip()
            if not parent_id:
                break

            if parent_id in seen:
                logger.error(
                    "Cycle detected in NetSuite subsidiary hierarchy "
                    "— subsidiary=%s parent=%s connection=%s",
                    current_id,
                    parent_id,
                    connection.id,
                )
                raise NetSuiteRecordFetchException(
                    "NetSuite subsidiary hierarchy contains a cycle; "
                    "item/subsidiary compatibility cannot be validated safely."
                )

            ancestors.append(parent_id)
            seen.add(parent_id)
            current_id = parent_id

        else:
            logger.error(
                "NetSuite subsidiary hierarchy exceeded maximum depth "
                "while resolving ancestors — subsidiary=%s connection=%s",
                raw_id,
                connection.id,
            )
            raise NetSuiteRecordFetchException(
                "NetSuite subsidiary hierarchy exceeded the safe maximum "
                "depth; item/subsidiary compatibility cannot be validated safely."
            )

        self._subsidiary_ancestor_cache[cache_key] = tuple(ancestors)
        return list(ancestors)

    def _get_item_subsidiary_status_live(
        self,
        *,
        connection,
        item_ids,
        subsidiary_id,
    ):
        """Return live compatibility status for exact NetSuite item IDs.

        The result is keyed by item ID and contains one of:
        - compatible=True
        - reason=SUBSIDIARY_MISMATCH
        - reason=INACTIVE
        - reason=NOT_FOUND

        SuiteQL/network failures raise NetSuiteRecordFetchException so callers
        can fail closed instead of treating an unknown check as a match.
        """
        normalized_ids = []
        seen_ids = set()

        for item_id in item_ids or []:
            raw_id = str(item_id or "").strip()
            if not raw_id or raw_id in seen_ids:
                continue
            seen_ids.add(raw_id)
            normalized_ids.append(raw_id)

        if not normalized_ids:
            return {}

        normalized_subsidiary_id = str(subsidiary_id or "").strip()
        if not normalized_subsidiary_id:
            raise ValueError(
                "A NetSuite transaction subsidiary is required for "
                "item compatibility validation."
            )

        ancestors = self._get_subsidiary_ancestors_live(
            connection=connection,
            subsidiary_id=normalized_subsidiary_id,
        )

        subsidiary_clauses = [
            (
                "BUILTIN.MNFILTER(subsidiary, "
                "'MN_INCLUDE', '', 'TRUE', "
                f"{self._suiteql_id_literal(normalized_subsidiary_id)}) = 'T'"
            )
        ]

        for ancestor_id in ancestors:
            ancestor_literal = self._suiteql_id_literal(ancestor_id)
            if ancestor_literal is None:
                continue
            subsidiary_clauses.append(
                "(includechildren = 'T' AND "
                "BUILTIN.MNFILTER(subsidiary, "
                "'MN_INCLUDE', '', 'TRUE', "
                f"{ancestor_literal}) = 'T')"
            )

        compatibility_clause = " OR ".join(subsidiary_clauses)

        compatible_ids = set()

        # Keep IN clauses bounded; candidate matching already fetches at most
        # 100 item rows per name chunk. The helper is also reused by final
        # posting checks, so keep it safe for future larger batches.
        chunk_size = 100

        for start in range(0, len(normalized_ids), chunk_size):
            chunk = normalized_ids[start : start + chunk_size]
            id_literals = [
                self._suiteql_id_literal(item_id)
                for item_id in chunk
            ]
            id_literals = [literal for literal in id_literals if literal]
            if not id_literals:
                continue

            query = f"""
                SELECT
                    id
                FROM item
                WHERE
                    id IN ({", ".join(id_literals)})
                    AND isinactive = 'F'
                    AND (
                        {compatibility_clause}
                    )
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
                if not isinstance(row, dict):
                    continue
                item_id = row.get("id")
                if item_id is not None:
                    compatible_ids.add(str(item_id).strip())

        unresolved_ids = [
            item_id
            for item_id in normalized_ids
            if item_id not in compatible_ids
        ]

        details_by_id = {}

        for start in range(0, len(unresolved_ids), chunk_size):
            chunk = unresolved_ids[start : start + chunk_size]
            id_literals = [
                self._suiteql_id_literal(item_id)
                for item_id in chunk
            ]
            id_literals = [literal for literal in id_literals if literal]
            if not id_literals:
                continue

            query = f"""
                SELECT
                    id,
                    itemid,
                    displayname,
                    isinactive,
                    includechildren,
                    BUILTIN.DF(subsidiary) AS subsidiary_name
                FROM item
                WHERE id IN ({", ".join(id_literals)})
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
                if not isinstance(row, dict):
                    continue
                item_id = row.get("id")
                if item_id is not None:
                    details_by_id[str(item_id).strip()] = row

        statuses = {}

        for item_id in normalized_ids:
            if item_id in compatible_ids:
                statuses[item_id] = {
                    "compatible": True,
                    "subsidiary_check": "passed",
                    "netsuite_id": item_id,
                }
                continue

            row = details_by_id.get(item_id)
            if row is None:
                statuses[item_id] = {
                    "compatible": False,
                    "subsidiary_check": "failed",
                    "reason": "NOT_FOUND",
                    "netsuite_id": item_id,
                }
                continue

            is_inactive = str(
                row.get("isinactive", "F")
            ).upper() == "T"

            if is_inactive:
                reason = "INACTIVE"
            else:
                reason = "SUBSIDIARY_MISMATCH"

            item_name = (
                row.get("displayname")
                or row.get("itemid")
                or item_id
            )

            statuses[item_id] = {
                "compatible": False,
                "subsidiary_check": "failed",
                "reason": reason,
                "netsuite_id": item_id,
                "name": str(item_name),
                "item_subsidiary": row.get("subsidiary_name"),
                "includechildren": str(
                    row.get("includechildren", "F")
                ).upper() == "T",
            }

        return statuses

    def _validate_item_ids_for_subsidiary_live(
        self,
        *,
        connection,
        item_ids,
        subsidiary_id,
    ):
        """Return exact item IDs that cannot be posted for a subsidiary.

        This is the fail-closed wrapper used immediately before Vendor Bill
        posting. It shares the same live compatibility implementation used by
        pre-post validation, so validation and posting cannot drift apart.
        """
        statuses = self._get_item_subsidiary_status_live(
            connection=connection,
            item_ids=item_ids,
            subsidiary_id=subsidiary_id,
        )

        invalid_items = []
        for item_id, status in statuses.items():
            if status.get("compatible"):
                continue
            invalid_items.append(dict(status))

        return invalid_items

    def _validate_items_live(
        self,
        *,
        connection,
        line_items,
        source_field_key,
        subsidiary_id=None,
        subsidiary_name=None,
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
        chunk_size = 200

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
                limit=1000,
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

        # Apply the subsidiary filter once across the full candidate set.
        # This preserves the existing name-matching query while ensuring an
        # incompatible candidate can never win simply because it appears first.
        candidate_ids = []
        if subsidiary_id not in (None, ""):
            candidate_ids = [
                str(row.get("id")).strip()
                for name_rows in rows_by_name.values()
                for row in name_rows.values()
                if isinstance(row, dict) and row.get("id") is not None
            ]

            candidate_ids = list(dict.fromkeys(candidate_ids))
            subsidiary_statuses = self._get_item_subsidiary_status_live(
                connection=connection,
                item_ids=candidate_ids,
                subsidiary_id=subsidiary_id,
            )
        else:
            subsidiary_statuses = {}

        results = []

        for item in extracted_items:
            name = item.get("extracted_name")
            line_index = item["line_index"]

            base = {
                "extracted_name": name,
                "line_index": line_index,
                "round": 1,
                "subsidiary_check": (
                    "passed"
                    if subsidiary_id not in (None, "")
                    else "skipped"
                ),
            }

            if not name:
                results.append(
                    {
                        **base,
                        "matched": False,
                        "ambiguous": False,
                        "netsuite_id": None,
                        "round": 0,
                    }
                )
                continue

            all_candidates = list(
                rows_by_name.get(
                    self._normalize_match_name(name),
                    {},
                ).values()
            )

            if subsidiary_id not in (None, ""):
                candidates = [
                    candidate
                    for candidate in all_candidates
                    if subsidiary_statuses.get(
                        str(candidate.get("id")).strip(),
                        {},
                    ).get("compatible")
                ]

                if all_candidates and not candidates:
                    candidate_details = []
                    for candidate in all_candidates:
                        candidate_id = str(candidate.get("id")).strip()
                        status = subsidiary_statuses.get(candidate_id, {})
                        candidate_details.append(
                            {
                                "netsuite_id": candidate_id,
                                "name": (
                                    candidate.get("displayname")
                                    or candidate.get("itemid")
                                    or name
                                ),
                                "item_subsidiary": status.get(
                                    "item_subsidiary"
                                ),
                                "includechildren": bool(
                                    status.get("includechildren")
                                ),
                                "reason": status.get("reason")
                                or "SUBSIDIARY_MISMATCH",
                            }
                        )

                    results.append(
                        {
                            **base,
                            "matched": False,
                            "ambiguous": False,
                            "netsuite_id": None,
                            "item_subsidiary_mismatch": True,
                            "transaction_subsidiary": subsidiary_name,
                            "transaction_subsidiary_id": str(
                                subsidiary_id
                            ),
                            "candidates": candidate_details[
                                : self.MAX_SIMILAR_CANDIDATES
                            ],
                            "round": 1,
                            "confidence": 0.0,
                        }
                    )
                    continue

                # Only the compatible candidates participate in the existing
                # first-match selection logic. If exactly one remains, the
                # subsidiary filter is the reason the ambiguity disappeared.
                if len(candidates) == 1 and len(all_candidates) > 1:
                    base["resolved_by"] = "subsidiary"
            else:
                candidates = all_candidates

            if len(candidates) == 1:
                record = candidates[0]

                results.append(
                    {
                        **base,
                        "matched": True,
                        "ambiguous": False,
                        "netsuite_id": str(record["id"]),
                        "record_type": "item",
                        "confidence": 1.0,
                    }
                )

            elif len(candidates) > 1:
                # Preserve the existing behavior among the remaining
                # subsidiary-compatible candidates: first active match wins.
                first_candidate = candidates[0]
                logger.warning(
                    "Multiple NetSuite item matches found during validation; "
                    "using first active compatible match — item=%r id=%s "
                    "candidates=%s subsidiary=%s connection=%s",
                    name,
                    first_candidate["id"],
                    len(candidates),
                    subsidiary_id,
                    connection.id,
                )
                results.append(
                    {
                        **base,
                        "matched": True,
                        "ambiguous": False,
                        "netsuite_id": str(first_candidate["id"]),
                        "record_type": "item",
                        "confidence": 1.0,
                        "candidates": [
                            {
                                "netsuite_id": str(candidate["id"]),
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
                        **base,
                        "matched": False,
                        "ambiguous": False,
                        "netsuite_id": None,
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
        
        # Round 1: exact case-insensitive match

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
