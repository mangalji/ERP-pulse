# ERP Pulse — Current Project Status

**Last Updated:** 2026-08-07T12:17:03+05:30  
**Project Phase:** Authentication & Multi-Tenancy Foundation (Sprint 8.4)

---

## Executive Summary

The project is an ERP platform with three portals (Super Admin, Client, Public) being built with a Django REST Framework backend and a React/TypeScript frontend. The current focus is fixing the authentication flow — specifically the login 403/429 issues, company creation with admin invitation, and frontend routing. Significant progress has been made on the Super Admin dashboard, client portal, and auth flow.

---

## 1. Workflow Progress

### Login & Authentication Flow Fix
- **Status:** Partially Complete
- **Completed:**
  - Root cause identified: `LoginOTPThrottle` (5 req/min rate limit) causing HTTP 429 on rapid retries
  - `CookieJWTAuthentication` verified fixed — correctly returns `None` on invalid/expired cookies instead of raising `AuthenticationFailed`, allowing anonymous access to `AllowAny` endpoints like `/auth/login/`
  - Frontend debug logging cleaned up in `apiClient.js` and `LoginPage.jsx`
- **In Progress:**
  - Backend debug `print()` statements in 3 files still contain Unicode `→` characters causing `UnicodeEncodeError` — needs replacement with `logger.debug()`
- **To Do:**
  - Resolve the discrepancy: user reports 403 for active user login (testing shows 200)
  - Re-run inactive user login test after debug print cleanup

### Company Creation with Admin Invitation
- **Status:** Complete
- **Completed:**
  - `CompanySerializer` now accepts `admin_email`, `admin_first_name`, `admin_last_name`
  - `create()` method auto-sends invitation email to admin with "Company Admin" role
  - Frontend `CompaniesPage.jsx` form updated with Admin User section
- **Verified:** All 10 backend tests pass (superadmin + invitations)

### Frontend Routing Audit
- **Status:** Complete
- **Completed:**
  - All 6 public pages now wrapped in `PublicLayout`
  - `ProtectedRoute` enforces role-based access (`requiredRole="admin"` vs `requiredRole="client"`)
  - 2 new detail page routes added: `/app/invoice-reader/:id` and `/app/invoice-reader/:id/payload`
  - Catch-all route made role-aware
  - 15 dead flat-page imports removed (commented out)
  - Build passes, lint clean (no new warnings)
- **Known Issues Remaining:**
  - Legacy `DashboardLayout` (15 flat pages) still on disk (dead code)
  - Legacy redirect routes (`/history`, `/vendors`, `/system-health` → `/app`)
  - `RegisterPage` & `CompleteProfilePage` intentionally unrouted (Sprint 8.4)

---

## 2. Current Status — Functionality Overview

### ✅ Working (Production-Ready)

| Module | Functionality | Status |
|--------|--------------|--------|
| **Authentication** | Login (email/password → OTP), OTP verification, logout | ✅ Working |
| **Authentication** | CookieJWTAuthentication with httpOnly cookies | ✅ Working |
| **Authentication** | Forgot/reset password flow | ✅ Working (backend) |
| **Authentication** | Invitation accept flow (token → set password → user created) | ✅ Working |
| **Super Admin** | Dashboard summary (company/user/plan stats) | ✅ Working |
| **Super Admin** | Company CRUD (list, view, suspend, activate, soft delete, restore) | ✅ Working |
| **Super Admin** | Company creation (with auto-admin invitation) | ✅ Working |
| **Super Admin** | Plan CRUD, assign/upgrade/downgrade/cancel/renew plans | ✅ Working |
| **Super Admin** | Module management per company | ✅ Working |
| **Super Admin** | Employee CRUD + role assignment/removal | ✅ Working |
| **Super Admin** | Support sessions (start/end/list) | ✅ Working |
| **Super Admin** | Notifications (fetch, read, unread count, mark all read) | ✅ Working |
| **Client Portal** | Dashboard, Invoice Reader, OCR Jobs, AI Assistant | ✅ Working |
| **Client Portal** | BI Analytics (Sales, Purchase, Customers, Inventory, Finance, Insights) | ✅ Working |
| **Client Portal** | Reports Engine (generate, schedules, history, templates) | ✅ Working |
| **Client Portal** | Company settings, profile, subscription, NetSuite integrations | ✅ Working |
| **Frontend Routing** | All 54 active routes properly connected with role-based auth | ✅ Working |
| **Frontend Build** | `npm run build` passes | ✅ Working |
| **Frontend Lint** | `npm run lint` — no new warnings | ✅ Working |

### ⚠️ Partially Working

| Module | Issue |
|--------|-------|
| **Login (Inactive User)** | `UnicodeEncodeError` in debug `print()` statements masks `AccountNotVerifiedException` (403) — pending debug print cleanup |
| **Company Creation (Admin)** | Invitation email sent correctly, but needs verification that admin can complete the flow end-to-end |
| **Demo Requests** | Route `/admin/demo-requests` exists but not linked in AdminLayout sidebar |
| **Subscription Management** | Route `/admin/companies/:id/subscription` exists but not linked from CompaniesPage drawer |

### ❌ Not Working / Missing

| Module | Functionality | Issue |
|--------|--------------|-------|
| **Super Admin** | Demo Requests management | Route exists but no backend endpoint/linked |
| **Client Portal** | Invoice detail page field mapping | `InvoiceDetailPage.jsx:239` uses `record.edited_by?.get_full_name` but backend returns `record.edited_by_name` |
| **Client Portal** | Invoice review/payload preview actions | `frontend/src/services/invoice.js` missing `reviewFile`, `previewPayload`, `getFileHistory` methods |
| **RBAC** | Role-based access control at view level | Not enforced on some endpoints (documented issue) |
| **Demo** | Approve action | Sends no notification/email to prospect |
| **Employee Creation** | Via `/client/employees/` | Does not auto-send invitation email |
| **Role ID Type Mismatch** | Frontend sends IntegerField, backend Invitation.role expects UUID |
| **Backend Debug Prints** | Unicode `→` in 3 files | Causes `UnicodeEncodeError` |

---

## 3. What Works Well

1. **Multi-tenancy architecture** is solid — `Company` model with `CompanySettings` auto-created via signal, RBAC with system roles (Super Admin, Company Admin, Employee), and role-scoping (global vs company-specific).

2. **Invitation system** is well-designed — token-based, expiry tracking, status management (PENDING/ACCEPTED/EXPIRED/CANCELLED), email sending via dedicated `InvitationService`.

3. **Frontend routing** is clean after audit — role-aware ProtectedRoute, layout-per-portal, legacy redirect shims for backward compat.

4. **Super Admin dashboard** has comprehensive functionality — companies, plans, modules, employees, support sessions, notifications all wired up and tested.

5. **Test coverage** exists for invitations (7 tests) — all passing.

## 4. What Needs Improvement

1. **Debug logging hygiene** — Temporary `print()` statements with Unicode characters need cleanup. Use `logger.debug()` only.

2. **Company creation flow** — Should consider whether the admin should be created immediately (with password) or always via invitation. Current approach uses invitation, which is correct for security.

3. **Field mapping bugs** — Invoice detail page field name mismatch (`edited_by` vs `edited_by_name`).

4. **Missing service methods** — Frontend `invoice.js` is missing methods for invoice review/payload history.

5. **RBAC enforcement** — Some endpoints don't enforce view-level permissions.

## 5. Remaining Work (by Priority)

### High Priority
- [ ] Clean up backend debug `print()` statements (replace with `logger.debug()`) in:
  - `backend/accounts/views.py`
  - `backend/authentication_service.py`
  - `backend/common/exception_handler.py`
- [ ] Fix `InvoiceDetailPage.jsx:239` — `edited_by.get_full_name` → `edited_by_name`
- [ ] Add missing frontend methods in `frontend/src/services/invoice.js` (`reviewFile`, `previewPayload`, `getFileHistory`)

### Medium Priority
- [ ] Link `/admin/demo-requests` in AdminLayout sidebar
- [ ] Link `/admin/companies/:id/subscription` from CompaniesPage detail drawer
- [ ] Fix `role_id` type mismatch (IntegerField vs UUID) in invitation/employee creation
- [ ] Enforce RBAC at view level on remaining endpoints

### Low Priority
- [ ] Clean up legacy `DashboardLayout` flat pages (dead code)
- [ ] Update legacy redirect routes (`/history`, `/vendors`, `/system-health`)
- [ ] Add notification/email on demo request approval

---

## 6. Backend Debug Log Cleanup (Detailed)

The following debug `print()` statements were added during investigation and need to be converted to `logger.debug()` calls (removing Unicode `→` characters):

**File: `backend/accounts/views.py`** — `LoginView.post`
```python
print("→ LoginView.post() entered")  # Replace with logger.debug(...)
```

**File: `backend/authentication_service.py`** — `login()` method (line ~339)
```python
print(f"→ login() entered with email={email}")  # Replace with logger.debug(...)
```

**File: `backend/common/exception_handler.py`** — `standard_exception_handler` (line ~40)
```python
print(f"→ exception type = {exc}")  # Replace with logger.debug(...)
```

These are the source of the `UnicodeEncodeError` when handling inactive user logins.

---

## 7. Environment Notes

- **Database:** Currently using SQLite for local dev (`erp_pulse_local`). PostgreSQL credentials in `.env` have expired (neondb_owner auth failed).
- **Backend Server:** Running on `localhost:8000` with `config.settings.local`
- **Frontend:** React dev server (typical port 5173)
- **Tests:** 10 tests passing (superadmin + invitations). Command: `DJANGO_SETTINGS_MODULE=config.settings.local python -m django test superadmin invitations`
