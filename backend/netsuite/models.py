import uuid

from django.conf import settings
from django.db import models
from common.utils.crypto import EncryptedTextField


class NetSuiteConnection(models.Model):

    ENVIRONMENT_CHOICES = [
        ("sandbox", "Sandbox"),
        ("production", "Production"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("connected", "Connected"),
        ("disconnected", "Disconnected"),
        ("error", "Error"),
    ]


    """
    One row per AGSuite ERP user's connected NetSuite account.

    Stores only the OAuth token set for that connection — no NetSuite
    business data (Customers/Items/Sales Orders live in their own models
    in a later task, per NETSUITE_CONTEXT.md). Populated by
    NetSuiteConnectionService after the OAuth callback succeeds
    (see services.py) and refreshed by NetSuiteAuthClient when the
    access token expires.

    SECURITY NOTE: client_secret/access_token/refresh_token are encrypted
    at rest via EncryptedTextField (Fernet). FIELD_ENCRYPTION_KEY must be
    set in the environment before any connection is created — see
    common/utils/crypto.py.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="netsuite_connections")
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='netsuite_connections',
    )
    client_name = models.CharField(max_length=255,null=True,blank=True)
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        null=True,
        blank=True,
    )
    client_id = models.CharField(max_length=255,null=True,blank=True)
    client_secret = EncryptedTextField(null=True,blank=True)
    netsuite_account_id = models.CharField(max_length=50)
    access_token = EncryptedTextField(null=True,blank=True)
    refresh_token = EncryptedTextField(null=True,blank=True)
    access_token_expires_at = models.DateTimeField(null=True,blank=True)
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    is_active = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Last time any live NetSuite API call succeeded through this '
                   'connection — broader than last_synced_at, which is scoped to '
                   'sync jobs specifically.',
    )
    last_error = models.TextField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Failure streak beyond which a "connected" connection is reported as
    # unhealthy rather than healthy — chosen to tolerate a couple of
    # transient blips without flapping the status, while still surfacing
    # a connection that's genuinely stuck failing.
    UNHEALTHY_FAILURE_THRESHOLD = 3

    class Meta:
        db_table = 'netsuite_connection'

        constraints = [
            models.UniqueConstraint(
                fields=["company", "netsuite_account_id"],
                name="unique_company_netsuite_account",
            )
        ]

        indexes = [
            # Covers NetSuiteConnectionRepository.get_by_user()'s exact
            # filter shape — the unique constraint above indexes
            # (user, netsuite_account_id), a different column pair that
            # doesn't help this query.
            models.Index(fields=["user", "is_active"], name="netsuite_conn_user_active_idx"),
            models.Index(fields=["company", "is_active"], name="ns_conn_co_active_idx"),
        ]

    @property
    def health(self) -> str:
        """
        Computed, not stored — derived from status + consecutive_failures
        so there's one source of truth instead of two fields that could
        drift out of sync with each other.

        One of: 'healthy', 'degraded', 'unhealthy', 'disconnected'.
        """
        if self.status in ('disconnected', 'pending'):
            return 'disconnected'
        if self.status == 'error' or self.consecutive_failures >= self.UNHEALTHY_FAILURE_THRESHOLD:
            return 'unhealthy'
        if self.consecutive_failures > 0:
            return 'degraded'
        return 'healthy'


    def __str__(self):
        return f"{self.client_name} ({self.user.email})"


class NetSuiteConnectionAuditLog(models.Model):
    """
    One row per lifecycle event on a NetSuiteConnection — created,
    renamed, deleted, switched active, OAuth completed, or a sync
    failure recorded against it.

    `connection` is nullable and SET_NULL on delete (not CASCADE) so a
    deleted connection's audit history survives the deletion itself —
    otherwise "this connection was deleted" would delete its own audit
    trail as a side effect, which defeats the point of an audit log.
    `netsuite_account_id`/`client_name` are duplicated onto the log row
    (not just looked up via the FK) for the same reason: they need to
    stay readable after the connection is gone.
    """

    ACTION_CHOICES = [
        ('created', 'Created'),
        ('oauth_completed', 'OAuth Completed'),
        ('renamed', 'Renamed'),
        ('switched_active', 'Switched Active'),
        ('deleted', 'Deleted'),
        ('sync_failed', 'Sync Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='netsuite_connection_audit_logs',
    )

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    netsuite_account_id = models.CharField(max_length=50, null=True, blank=True)
    client_name = models.CharField(max_length=255, null=True, blank=True)
    detail = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'netsuite_connection_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='ns_audit_user_recent_idx'),
        ]

    def __str__(self):
        return f'{self.get_action_display()} — {self.client_name or self.netsuite_account_id}'


class EmployeeConnection(models.Model):
    """
    Assigns a company employee to a specific NetSuite connection.

    Employees do not manage credentials directly. They use whatever
    connection the Company Admin assigns to them.
    """

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_netsuite_connections',
    )
    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.CASCADE,
        related_name='employee_assignments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'employee_netsuite_connection'
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'connection'],
                name='unique_employee_connection',
            )
        ]
        indexes = [
            models.Index(fields=['employee'], name='emp_conn_emp_idx'),
            models.Index(fields=['connection'], name='emp_conn_conn_idx'),
        ]

    def __str__(self):
        return f'{self.employee.email} → {self.connection.client_name or self.connection.netsuite_account_id}'


class NetSuiteUserConnectionPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='netsuite_connection_preference',
    )

    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_for_users',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'netsuite_user_connection_preference'

    def __str__(self):
        account = (
            self.connection.client_name
            if self.connection
            else 'No connection'
        )
        return f'{self.user.email} → {account}'


class NetSuiteReferenceRecord(models.Model):
    """Cached NetSuite master/reference record for one connected account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.CASCADE,
        related_name="reference_records",
    )
    record_type = models.CharField(max_length=80)
    internal_id = models.CharField(max_length=64)
    external_id = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=500, blank=True, default="")
    search_name = models.CharField(max_length=500, blank=True, default="")
    item_type = models.CharField(max_length=80, null=True, blank=True)
    is_inactive = models.BooleanField(default=False)
    data = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "netsuite_reference_record"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "record_type", "internal_id"],
                name="unique_ns_reference_record",
            ),
        ]
        indexes = [
            models.Index(
                fields=["connection", "record_type", "search_name"],
                name="ns_ref_conn_type_name_idx",
            ),
            models.Index(
                fields=["connection", "record_type", "external_id"],
                name="ns_ref_conn_type_ext_idx",
            ),
        ]

    def __str__(self):
        return f"{self.record_type}:{self.internal_id} — {self.name or self.external_id or ''}"


class NetSuiteFieldCatalogue(models.Model):
    """
    Cached Vendor Bill field metadata for one connected NetSuite account.

    Metadata is connection-scoped because different NetSuite accounts can have
    different customizations, enabled features and custom fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.CASCADE,
        related_name="field_catalogues",
    )
    record_type = models.CharField(max_length=80, default="vendorBill")
    body_fields = models.JSONField(default=list, blank=True)
    line_fields = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=list, blank=True)
    raw_metadata = models.JSONField(default=dict, blank=True)
    metadata_hash = models.CharField(max_length=64, blank=True, default="")
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "netsuite_field_catalogue"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "record_type"],
                name="unique_ns_field_catalogue_connection_record",
            ),
        ]
        indexes = [
            models.Index(
                fields=["connection", "record_type"],
                name="ns_field_cat_conn_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.connection_id}:{self.record_type}"



class NetSuiteOCRPosting(models.Model):
    """Audit/idempotency record for an OCR document posted to NetSuite."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("posted", "Posted"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        "ocr.OCRDocument",
        on_delete=models.CASCADE,
        related_name="netsuite_postings",
    )
    version = models.ForeignKey(
        "ocr.OCRDocumentVersion",
        on_delete=models.CASCADE,
        related_name="netsuite_postings",
    )
    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.CASCADE,
        related_name="ocr_postings",
    )
    record_type = models.CharField(max_length=80, default="vendorBill")
    netsuite_record_id = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="netsuite_ocr_postings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "netsuite_ocr_posting"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version"],
                name="unique_ocr_netsuite_posting",
            ),
        ]
        indexes = [
            models.Index(
                fields=["connection", "status"],
                name="ns_post_conn_status_idx",
            ),
            models.Index(
                fields=["netsuite_record_id"],
                name="ns_post_record_id_idx",
            ),
        ]

    def __str__(self):
        return f"{self.document_id} v{self.version_id} → {self.netsuite_record_id or self.status}"


class NetSuiteCustomField(models.Model):
    """
    Tracks NetSuite custom fields created on behalf of AGSuite OCR
    custom fields.

    Prevents duplicate creation and preserves the authoritative mapping
    between an OCR custom field and the resulting NetSuite script ID.
    """

    SCOPE_CHOICES = [
        ('body', 'Body'),
        ('column', 'Column / Item Sublist'),
    ]

    DATATYPE_CHOICES = [
        ('text', 'Text'),
        ('integer', 'Integer'),
        ('decimal', 'Decimal'),
        ('date', 'Date'),
        ('checkbox', 'Checkbox'),
        ('currency', 'Currency'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='netsuite_custom_fields',
    )
    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.CASCADE,
        related_name='ocr_custom_fields',
    )
    record_type = models.CharField(max_length=80)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    field_label = models.CharField(max_length=255)
    field_id = models.CharField(max_length=100)
    datatype = models.CharField(max_length=20, choices=DATATYPE_CHOICES)

    source_field_key = models.CharField(max_length=100)
    source_field_label = models.CharField(max_length=255)

    netsuite_field_id = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    error = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'netsuite_custom_field'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'connection', 'record_type', 'scope', 'source_field_key'],
                name='unique_ns_custom_field_per_context',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'connection', 'record_type'], name='ns_cf_conn_idx'),
            models.Index(fields=['source_field_key'], name='ns_cf_src_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.field_id} ({self.record_type}:{self.scope})'