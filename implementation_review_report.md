# Implementation Review Report

## 1. Files Created

### backend/superadmin/apps.py
- Purpose: Registers the superadmin Django app.
- Number of lines: 7
- Classes created: SuperadminConfig
- Functions created: None

### backend/superadmin/models.py
- Purpose: Defines super-admin subscription and support models.
- Number of lines: 95
- Classes created:
  - PlanStatus
  - Plan
  - CompanyPlanStatus
  - CompanyPlan
  - SupportSessionStatus
  - SupportSession
- Functions created:
  - Plan.__str__
  - CompanyPlan.__str__
  - SupportSession.__str__

### backend/superadmin/permissions.py
- Purpose: Enforces super-admin access using the custom RBAC model instead of Django groups.
- Number of lines: 24
- Classes created: IsSuperAdmin
- Functions created: None

### backend/superadmin/serializers.py
- Purpose: Serializes super-admin company, plan, module, and user payloads.
- Number of lines: 75
- Classes created:
  - PlanSerializer
  - CompanyPlanSerializer
  - SupportSessionSerializer
  - CompanySerializer
  - ModuleSerializer
  - CompanyModuleSerializer
  - UserSerializer
- Functions created: None

### backend/superadmin/views.py
- Purpose: Provides the super-admin viewset layer and audit hooks.
- Number of lines: 164
- Classes created:
  - CompanyViewSet
  - PlanViewSet
  - CompanyPlanViewSet
  - SupportSessionViewSet
  - ModuleViewSet
  - CompanyModuleViewSet
  - EmployeeViewSet
  - DashboardViewSet
  - NotificationViewSet
- Functions created: None
- Note: The class-level actions such as suspend, activate, soft_delete, restore, and stats are methods on the viewset, not module-level functions.

### backend/superadmin/migrations/0001_initial.py
- Purpose: Creates the initial superadmin database schema.
- Number of lines: 90
- Classes created: Migration
- Functions created: None

---

## 2. Files Modified

### backend/config/settings/apps.py
- Exactly what changed:
  - Added the local app entry "superadmin" to LOCAL_APPS.
- Why it changed:
  - The superadmin app had to be installed so its models, permissions, and viewsets could be loaded by Django.

### backend/superadmin/apps.py
- Exactly what changed:
  - Created the app config class.
- Why it changed:
  - Required to register the app under the name "superadmin".

### backend/superadmin/models.py
- Exactly what changed:
  - Added Plan, CompanyPlan, and SupportSession.
  - Added enumerations PlanStatus, CompanyPlanStatus, and SupportSessionStatus.
- Why it changed:
  - Super-admin functionality needed subscription-plan and support-session records.

### backend/superadmin/permissions.py
- Exactly what changed:
  - Added custom IsSuperAdmin permission logic tied to the project’s RBAC model.
- Why it changed:
  - This project does not use Django Groups, so super-admin authorization had to be based on UserRole → Role.

### backend/superadmin/views.py
- Exactly what changed:
  - Imported the custom IsSuperAdmin implementation.
  - Added CompanyViewSet with suspend, activate, soft_delete, restore, and stats actions.
  - Added audit_service.log calls for company lifecycle actions.
  - Kept the remaining superadmin viewsets as placeholders.
- Why it changed:
  - To enforce the existing RBAC policy and to add actual super-admin company operations.

### backend/superadmin/serializers.py
- Exactly what changed:
  - Added serializers for Plan, CompanyPlan, SupportSession, Company, Module, CompanyModule, and User.
- Why it changed:
  - To expose a consistent data contract for super-admin API layers.

### backend/superadmin/migrations/0001_initial.py
- Exactly what changed:
  - Created DB tables sa_plan, sa_company_plan, and sa_support_session.
- Why it changed:
  - Required to persist super-admin subscription and support-session data.

### backend/dashboard/services.py
- Exactly what changed:
  - Kept dashboard logic in a single service.
  - Reused NetSuite list methods for summary counts.
  - Removed placeholder-style business logic from this module and kept it to record counts and recent items.
- Why it changed:
  - To ensure dashboard metrics are derived from actual NetSuite record totals instead of fake values.

### backend/dashboard/views.py
- Exactly what changed:
  - Added summary and recent-record API views.
  - Used standard success_response and paginated_response wrappers.
  - Kept the view layer thin and service-backed.
- Why it changed:
  - To expose only real dashboard metrics backed by existing data sources.

### backend/dashboard/urls.py
- Exactly what changed:
  - Added routes for:
    - summary
    - recent-sales-orders
    - recent-invoices
    - recent-customers
- Why it changed:
  - To route the dashboard API endpoints.

---

## 3. Models

### User
- File: backend/accounts/models.py
- Fields:
  - id
  - email
  - first_name
  - last_name
  - mobile_number
  - profile_pic
  - company
  - employee_id
  - designation
  - department
  - last_activity
  - is_active
  - is_staff
  - is_email_verified
  - last_login_at
  - created_at
  - updated_at
- Relationships:
  - Many-to-one with Company
  - One-to-many with OTP, LoginActivity, notifications, audit_logs, invoice_batches, reviewed_invoices, etc.
- Constraints:
  - email unique
  - mobile_number unique, nullable
- Indexes:
  - Default Django index on email, plus custom login_activity indexes in LoginActivity
- Meta options:
  - db_table = user

### OTP
- File: backend/accounts/models.py
- Fields:
  - id
  - user
  - otp_hash
  - purpose
  - expires_at
  - is_used
  - attempt_count
  - created_at
  - updated_at
- Relationships:
  - Many-to-one with User
- Constraints:
  - None beyond FK
- Indexes:
  - otp_user_purpose_used_idx on user, purpose, is_used
- Meta options:
  - db_table = otp

### LoginActivity
- File: backend/accounts/models.py
- Fields:
  - id
  - user
  - ip_address
  - user_agent
  - created_at
- Relationships:
  - Many-to-one with User
- Constraints:
  - None
- Indexes:
  - login_activity_user_recent_idx on user, created_at desc
- Meta options:
  - db_table = login_activity
  - ordering = [-created_at]

### Company
- File: backend/tenancy/models.py
- Fields:
  - id
  - name
  - code
  - status
  - contact_email
  - contact_phone
  - country
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - One-to-one with CompanySettings
  - One-to-many with users, company_modules, support_sessions, company_plans, notification records, audit logs, invoice batches
- Constraints:
  - code unique
- Indexes:
  - db_index on status
- Meta options:
  - db_table = company
  - ordering = ["name"]

### Module
- File: backend/tenancy/models.py
- Fields:
  - id
  - name
  - code
  - display_name
  - icon
  - description
  - sort_order
  - is_active
  - is_system
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-many via CompanyModule and Plan.enabled_models
- Constraints:
  - name unique
  - code unique
- Indexes:
  - ordering by sort_order, name
- Meta options:
  - db_table = module

### CompanyModule
- File: backend/tenancy/models.py
- Fields:
  - id
  - company
  - module
  - enabled
  - usage_limit
  - activated_at
  - activated_by
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-one with Company
  - Many-to-one with Module
- Constraints:
  - unique_company_module on company + module
- Indexes:
  - None beyond FK indexes
- Meta options:
  - db_table = company_module

### CompanySettings
- File: backend/tenancy/models.py
- Fields:
  - id
  - company
  - timezone
  - currency
  - language
  - date_format
  - number_format
- Relationships:
  - One-to-one with Company
- Constraints:
  - None
- Indexes:
  - None
- Meta options:
  - db_table = company_settings

### Role
- File: backend/rbac/models.py
- Fields:
  - id
  - name
  - description
  - is_system
  - company
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-one with Company
  - One-to-many with UserRole and RolePermission
- Constraints:
  - unique_role_name_company on name + company
  - unique_role_name_global on name where company is null
- Indexes:
  - ordering by name
- Meta options:
  - db_table = role

### Permission
- File: backend/rbac/models.py
- Fields:
  - id
  - code
  - name
  - module
  - description
  - is_system
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - One-to-many with RolePermission
- Constraints:
  - code unique
- Indexes:
  - permission_module_idx on module
  - permission_code_idx on code
- Meta options:
  - db_table = permission
  - ordering = ["module", "name"]

### RolePermission
- File: backend/rbac/models.py
- Fields:
  - id
  - role
  - permission
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-one with Role
  - Many-to-one with Permission
- Constraints:
  - unique_role_permission on role + permission
- Indexes:
  - None beyond FK indexes
- Meta options:
  - db_table = role_permission

### UserRole
- File: backend/rbac/models.py
- Fields:
  - id
  - user
  - role
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-one with User
  - Many-to-one with Role
- Constraints:
  - unique_user_role on user + role
- Indexes:
  - None beyond FK indexes
- Meta options:
  - db_table = user_role

### Notification
- File: backend/notifications/models.py
- Fields:
  - id
  - company
  - user
  - title
  - message
  - type
  - is_read
  - read_at
  - created_at
- Relationships:
  - Many-to-one with Company, User
- Constraints:
  - None
- Indexes:
  - notif_user_recent_idx on user, created_at desc
  - notif_user_unread_idx on user, is_read
- Meta options:
  - db_table = notification
  - ordering = ["-created_at"]

### NotificationPreference
- File: backend/notifications/models.py
- Fields:
  - id
  - user
  - category
  - email_enabled
  - in_app_enabled
  - push_enabled
- Relationships:
  - Many-to-one with User
- Constraints:
  - unique_user_category on user + category
- Indexes:
  - None
- Meta options:
  - db_table = notification_preference

### AuditLog
- File: backend/audit/models.py
- Fields:
  - id
  - company
  - user
  - module
  - action
  - entity
  - entity_id
  - old_value
  - new_value
  - ip_address
  - created_at
- Relationships:
  - Many-to-one with Company
  - Many-to-one with User
- Constraints:
  - None
- Indexes:
  - audit_company_recent_idx on company, created_at desc
  - audit_user_recent_idx on user, created_at desc
  - audit_module_entity_idx on module, entity
- Meta options:
  - db_table = audit_log
  - ordering = ["-created_at"]

### Plan
- File: backend/superadmin/models.py
- Fields:
  - id
  - name
  - description
  - monthly_price
  - yearly_price
  - max_employees
  - max_ocr_documents
  - max_storage_gb
  - status
  - enabled_models
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-many with Module via enabled_models
  - One-to-many with CompanyPlan
- Constraints:
  - unique on name
- Indexes:
  - ordering by name
- Meta options:
  - db_table = sa_plan

### CompanyPlan
- File: backend/superadmin/models.py
- Fields:
  - id
  - company
  - plan
  - start_date
  - end_date
  - status
  - is_auto_renew
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-one with Company
  - Many-to-one with Plan
- Constraints:
  - unique_active_company_plan on company when status in ACTIVE and TRIAL
- Indexes:
  - ordering by start_date desc
- Meta options:
  - db_table = sa_company_plan

### SupportSession
- File: backend/superadmin/models.py
- Fields:
  - id
  - company
  - support_user
  - reason
  - started_at
  - ended_at
  - status
  - ip_address
  - created_at
  - updated_at
  - is_deleted
  - deleted_at
  - created_by
  - updated_by
- Relationships:
  - Many-to-one with Company
  - Many-to-one with User
- Constraints:
  - None
- Indexes:
  - ordering by started_at desc
- Meta options:
  - db_table = sa_support_session

---

## 4. APIs

### Dashboard API

#### 1) GET /api/v1/dashboard/summary/
- File: backend/dashboard/views.py
- Permission: IsAuthenticated
- Request Body: None
- Response:
  - success_response with message and data dictionary of summary keys
  - Example shape: total_customers, total_employees, total_vendors, total_inventory_items, total_sales_orders, total_purchase_orders, total_invoices
- Business logic:
  - Calls DashboardService.get_summary(user=request.user)
  - Returns actual NetSuite totalResults values from list methods

#### 2) GET /api/v1/dashboard/recent-sales-orders/
- File: backend/dashboard/views.py
- Permission: IsAuthenticated
- Request Body: None
- Response:
  - paginated_response with results list, count, next, previous
- Business logic:
  - Parses offset and limit
  - Calls DashboardService.get_recent_sales_orders(user=request.user)
  - Uses NetSuiteDataService.get_records(record_type=SALES_ORDER, limit=limit)

#### 3) GET /api/v1/dashboard/recent-invoices/
- File: backend/dashboard/views.py
- Permission: IsAuthenticated
- Request Body: None
- Response:
  - paginated_response with results list, count, next, previous
- Business logic:
  - Calls DashboardService.get_recent_invoices(user=request.user)

#### 4) GET /api/v1/dashboard/recent-customers/
- File: backend/dashboard/views.py
- Permission: IsAuthenticated
- Request Body: None
- Response:
  - paginated_response with results list, count, next, previous
- Business logic:
  - Calls DashboardService.get_recent_customers(user=request.user)

### Superadmin API surface
- File: backend/superadmin/views.py
- Current status:
  - CompanyViewSet is implemented.
  - PlanViewSet, CompanyPlanViewSet, SupportSessionViewSet, ModuleViewSet, CompanyModuleViewSet, EmployeeViewSet, DashboardViewSet, and NotificationViewSet remain pass or empty stubs.
  - No router or urls.py registration is present in the project for these viewsets, so no public URL is currently exposed for them.
- Permission:
  - CompanyViewSet.permission_classes = [IsSuperAdmin]
  - IsSuperAdmin logic is in backend/superadmin/permissions.py
- Request Body:
  - Not publicly exposed due to missing route registration
- Response:
  - None at runtime because no public endpoint is mounted
- Business logic:
  - CompanyViewSet has suspend, activate, soft_delete, restore, and stats actions
  - Audit entries are written using audit_service.log

### Notifications API
- File: backend/notifications/models.py
- Current status:
  - Foundation-only model layer exists.
  - No API or service endpoint is implemented.
- Method: None
- URL: None
- Permission: None
- Request Body: None
- Response: None
- Business logic: None

---

## 5. Services

### DashboardService
- File: backend/dashboard/services.py
- Responsibilities:
  - Build dashboard summary counts from NetSuite list endpoints.
  - Fetch recent sales orders, invoices, customers, and employees.
  - Use a fallback path if SuiteQL list methods fail.
- Methods:
  - get_summary
  - get_recent_sales_orders
  - get_recent_invoices
  - get_recent_customers
  - get_recent_employees
  - _get_total
  - _get_items
- Existing services reused:
  - NetSuiteDataService from backend/netsuite/services.py
  - NetSuiteRecordType from backend/netsuite/constants.py
  - User model from backend/accounts/models.py

### AuditService
- File: backend/audit/services.py
- Responsibilities:
  - Writes audit log entries when a caller needs explicit audit tracking.
- Methods:
  - log
- Existing services reused:
  - AuditLog model from backend/audit/models.py
  - Company and User references from related models

### REST response helpers
- Files:
  - backend/common/utils/response.py
  - backend/common/utils/pagination.py
- Responsibilities:
  - Build standard envelope responses and paginated responses
- Methods:
  - success_response
  - paginated_response
- Existing services reused:
  - DRF Response and Request objects only

### RBAC permission classes
- File: backend/rbac/permissions.py
- Responsibilities:
  - Evaluate role membership, permission membership, and module access
- Methods:
  - HasRole.has_permission
  - HasPermission.has_permission
  - HasModuleAccess.has_permission
- Existing services reused:
  - RolePermission model
  - UserRole model
  - CompanyModule model

---

## 6. RBAC

The actual hierarchy is:

User
↓
UserRole
↓
Role
↓
Permission

### Actual implementation
- User is the custom auth model in backend/accounts/models.py
- UserRole is defined in backend/rbac/models.py
- Role is defined in backend/rbac/models.py
- Permission is defined in backend/rbac/models.py
- RolePermission links Role to Permission in backend/rbac/models.py

### Permission flow
- UserRole records which roles belong to a user.
- RolePermission records which permissions belong to a role.
- HasRole checks the user’s role names from UserRole.role__name.
- HasPermission checks permission codes from RolePermission.permission__code through the user’s roles.
- HasModuleAccess checks whether the user’s Company has the requested module enabled.

### Super-admin check
- In backend/superadmin/permissions.py, IsSuperAdmin evaluates:
  - request.user.is_superuser
  - OR request.user.user_roles.filter(role__company__isnull=True, role__name='super_admin').exists()

### Django auth.Group usage
- Confirmed: Django auth.Group is not used anywhere in the active backend Python code.
- No import of django.contrib.auth.models.Group is present.
- No auth.group model usage is present in the active project files.

---

## 7. Database

### New tables
- sa_plan
  - Created in backend/superadmin/migrations/0001_initial.py
- sa_company_plan
  - Created in backend/superadmin/migrations/0001_initial.py
- sa_support_session
  - Created in backend/superadmin/migrations/0001_initial.py

### Existing RBAC tables used by this implementation
- role
- permission
- role_permission
- user_role

### New indexes
- unique_active_company_plan on CompanyPlan.company when status in ACTIVE or TRIAL
- permission_module_idx on Permission.module
- permission_code_idx on Permission.code
- audit_company_recent_idx on AuditLog.company and created_at
- audit_user_recent_idx on AuditLog.user and created_at
- audit_module_entity_idx on AuditLog.module and entity
- notif_user_recent_idx on Notification.user and created_at
- notif_user_unread_idx on Notification.user and is_read

### New constraints
- Plan.name unique
- CompanyPlan unique_active_company_plan
- Role unique_role_name_company
- Role unique_role_name_global
- RolePermission unique_role_permission
- UserRole unique_user_role
- NotificationPreference unique_user_category

### New migrations
- backend/superadmin/migrations/0001_initial.py

---

## 8. Performance

### select_related()
- Used in backend/superadmin/views.py:
  - Company.objects.all().select_related('settings')
- Purpose:
  - Reduces query count for the Company.settings relationship when listing companies

### prefetch_related()
- Used in backend/superadmin/views.py:
  - prefetch_related('company_modules__module')
- Purpose:
  - Loads nested company-module and module rows efficiently without N+1 queries

### Pagination
- Used in backend/dashboard/views.py
- Implementation:
  - _parse_pagination_params
  - paginated_response from backend/common/utils/pagination.py
- Purpose:
  - Limits result size and provides next/previous metadata

### Filtering
- Used in backend/superadmin/views.py
- Implementation:
  - filterset_fields = ['status', 'country']
  - search_fields = ['name', 'code', 'contact_email']
- Purpose:
  - Supports list filtering and search for superadmin company queries

### Ordering
- Used in:
  - backend/superadmin/views.py
  - backend/superadmin/models.py
  - backend/tenancy/models.py
- Examples:
  - ordering = ['name']
  - ordering = ['-start_date']
  - ordering = ['-created_at']
- Purpose:
  - Keeps stable deterministic ordering for admin listings and timestamps

---

## 9. Audit

The actual audit log calls in the implemented code are:

### backend/superadmin/views.py
1. suspend
   - Calls audit_service.log with:
     - module = AuditModule.TENANCY
     - action = AuditAction.UPDATE
     - entity = "Company"
     - old_value = {"status": company.status}
     - new_value = {"status": company.status}

2. activate
   - Calls audit_service.log with:
     - module = AuditModule.TENANCY
     - action = AuditAction.UPDATE
     - entity = "Company"
     - old_value = {"status": company.status}
     - new_value = {"status": company.status}

3. soft_delete
   - Calls audit_service.log with:
     - module = AuditModule.TENANCY
     - action = AuditAction.DELETE
     - entity = "Company"

4. restore
   - Calls audit_service.log with:
     - module = AuditModule.TENANCY
     - action = AuditAction.UPDATE
     - entity = "Company"

### backend/invoice/views.py
5. invoice extraction review action
   - Calls audit_service.log with:
     - module = AuditModule.INVOICE
     - action = AuditAction.UPDATE for edit, AuditAction.APPROVE for approve, or AuditAction.REJECT for reject
     - entity = "ExtractedInvoice"
     - entity_id = str(extraction.id)
     - company = invoice_file.batch.company
     - old_value = {"status": extraction.extraction_status}
     - new_value = {"status": extraction.extraction_status, "action": action_type}

---

## 10. Reused Components

These are the actual reused modules and imports in the implementation:

- backend/superadmin/views.py
  - from .models import Plan, CompanyPlan, SupportSession
  - from .serializers import PlanSerializer, CompanyPlanSerializer, SupportSessionSerializer, CompanySerializer, ModuleSerializer, CompanyModuleSerializer, UserSerializer
  - from .permissions import IsSuperAdmin
  - from tenancy.models import Company, Module
  - from django.contrib.auth import get_user_model
  - from audit.services import audit_service
  - from audit.models import AuditAction, AuditModule

- backend/dashboard/views.py
  - from common.utils.pagination import paginated_response
  - from common.utils.response import success_response
  - from common.throttles import DashboardThrottle
  - from dashboard.services import DashboardService

- backend/dashboard/services.py
  - from accounts.models import User
  - from netsuite.constants import NetSuiteRecordType
  - from netsuite.services import NetSuiteDataService

- backend/rbac/permissions.py
  - from rbac.models import RolePermission, UserRole
  - from tenancy.models import CompanyModule

- backend/audit/services.py
  - from audit.models import AuditAction, AuditLog, AuditModule

- backend/notifications/models.py
  - from django.conf import settings
  - from django.db import models
  - from tenancy.models import Company

- backend/superadmin/models.py
  - from django.db import models
  - from django.conf import settings
  - from tenancy.models import Company, Module
  - from core.models import BaseModel

---

## 11. Technical Debt

- The superadmin API surface is incomplete:
  - backend/superadmin/views.py contains several class stubs with pass.
  - PlanViewSet, CompanyPlanViewSet, SupportSessionViewSet, ModuleViewSet, CompanyModuleViewSet, EmployeeViewSet, DashboardViewSet, and NotificationViewSet are not implemented.
- No public URL configuration exists for the superadmin endpoints.
  - There is no matching urls.py or router registration for these viewsets in the active project.
- Notification API is not implemented.
  - backend/notifications/models.py is foundation-only.
  - No NotificationViewSet or notification endpoint exists.
- The dashboard uses NetSuite totals as the data source, which is valid for the current codebase, but it is still dependent on external third-party data availability.
- Super-admin role matching relies on a hardcoded role name: "super_admin".
  - This works only if that seed exists exactly as created by the RBAC seeding command.

---

## 12. Self Review

### Things implemented well
- The RBAC fix follows the project’s required structure: User → UserRole → Role → Permission.
- The custom super-admin permission does not use Django auth.Group.
- Dashboard metrics are driven by existing NetSuite list endpoints and totalResults rather than fabricated numbers.
- The view layer is kept thin and delegates business logic to DashboardService.
- AuditService is used for company lifecycle actions and invoice review actions.

### Weak areas
- Superadmin endpoints are not fully implemented beyond the company operations.
- There is no public routing for the superadmin API.
- Notifications do not have a live service or API.
- The project still contains stubbed superadmin viewsets, which leaves the feature incomplete.

### Possible improvements
- Implement the remaining superadmin viewsets and register routes.
- Add tests specifically for IsSuperAdmin permission behavior.
- Implement a real notification API only when the backing notification module is actually ready.
- Add explicit route-level permission checks to any future superadmin endpoints.

---

## 13. Verification

- No placeholder code: True for the implemented dashboard and RBAC work.
  - The dashboard summary is fed from NetSuite counts, not static constants.
  - There is no placeholder notification endpoint in the active code.
- No fake dashboard values: True.
  - backend/dashboard/services.py reads actual totalResults from NetSuite list methods.
- No Django Groups: True.
  - No django.contrib.auth.models.Group or auth.group references are present in the active backend Python code.
- No duplicated models: True for the implemented RBAC and superadmin work.
  - The project uses the existing custom RBAC model and the superadmin app owns its own app-level subscription/support models without duplicating the core Company model.
- No duplicated services: True.
  - The dashboard logic is centralized in backend/dashboard/services.py, and it reuses backend/netsuite/services.py rather than duplicating data-source logic.
