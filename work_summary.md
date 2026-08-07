# ERP Pulse — Super Admin Company Management Work Summary

**Date:** August 7, 2026  
**Session:** Super Admin Company Management (Tasks 1-3)  
**Duration:** ~45 minutes  
**Status:** ALL 3 TASKS COMPLETED

**Additional:** Added back navigation buttons to CompaniesPage, CompanyDetailPage, DemoRequestDetailPage, and CompanySubscriptionPage (all four detail/list pages now have back arrow buttons returning to their parent pages).

---

## Executive Summary

Implemented three Super Admin company management workflows: (1) clickable company names in dashboard leading to a new company detail page, (2) fixed the companies listing page bug that showed "No companies found" even when companies existed, and (3) added Accept/Reject + company creation workflow for demo requests. All changes reuse existing APIs and components, follow AGSuite styling, and pass build + test verification.

---

## Task 1 — Dashboard → Recent Companies → Company Detail

### Problem
Dashboard's "Recent Companies" table showed company names as plain text — clicking did nothing.

### Solution
Made company names clickable, navigating to a new `/admin/companies/:id` detail page.

### Files Changed

| File | Change |
|------|--------|
| `frontend/src/pages/superadmin/DashboardPage.jsx` | Company name `<td>` changed from static text to a `<button>` that calls `navigate('/admin/companies/${company.id}')` |
| `frontend/src/pages/superadmin/CompanyDetailPage.jsx` | **New file** — Complete company detail page |
| `frontend/src/routes/AppRoutes.jsx` | Added `<Route path="/admin/companies/:id">` with `ProtectedRoute requiredRole="admin"` |

### Company Detail Page Sections
1. **Basic Information** — Name, Code, Status, Created Date, Updated Date
2. **Contact Information** — Email, Phone, Country
3. **Subscription** — Assigned Plan, Plan Type, Start Date, Expiry Date, Auto-Renew
4. **NetSuite** — Connected status, Account ID, Environment, Last Sync
5. **Employees** — Total count, Active count
6. **Assigned Modules** — List of all enabled modules with names and codes
7. **Actions** — View Subscription, View Employees, Assign Plan, Assign Modules, Suspend/Activate

### Backend Support
- `CompanyDetailSerializer` added to `backend/superadmin/serializers.py` with `SerializerMethodField`s for:
  - `user_count`, `active_user_count`, `module_count`
  - `current_plan` (via `CompanyPlanSummarySerializer`)
  - `assigned_modules` (list of module dicts)
  - `netsuite_connected`, `netsuite_account_id`, `netsuite_environment`, `netsuite_last_sync`

---

## Task 2 — Companies Page (Load ALL Companies)

### Problem
Companies page showed "No companies found" even though companies existed in the dashboard.

### Root Cause
The `CompanyViewSet` used DRF's default `ModelViewSet.list()` which returns a raw JSON array. The frontend's `unwrap()` function extracted `data` from the response, but the frontend expected `data.results` (from the success envelope). Since the backend didn't use the custom `paginated_response()` builder, the frontend couldn't find `data.results`.

### Solution

**Backend (`backend/superadmin/views.py`):**
- Added `list()` override to `CompanyViewSet` that calls `paginated_response()` with offset/limit pagination from query params, returning the standard `{ success: true, data: { count, next, previous, results } }` envelope

**Frontend (`frontend/src/pages/superadmin/CompaniesPage.jsx`):**
- Company name in table now navigates to `/admin/companies/:id` (detail page) instead of opening the old drawer
- Table columns updated:
  - Removed: "Modules" column
  - Added: "Employees" column (replaces "Users"), "Created" column
  - Added missing "Assigned Plan" column placeholder
- Old detail drawer code **commented out** (not deleted) per project guidelines
- `handleCreate` now navigates to detail page instead of opening drawer

### Backend Changes

| File | Change |
|------|--------|
| `backend/superadmin/views.py` | Override `list()` method; override `retrieve()` method; `get_queryset()` adds `.prefetch_related('company_plans')` and uses `distinct=True` on Count annotations; imports `Role`, `UserRole` |
| `backend/superadmin/serializers.py` | Added `CompanyDetailSerializer`, `CompanyPlanSummarySerializer`; added `admin_email`, `admin_first_name`, `admin_last_name` write-only fields to `CompanySerializer` with `create()` override for auto-invitation |

---

## Task 3 — Demo Request Workflow (Accept / Reject + Company Creation)

### Problem
Demo Request detail page only opened details. No Accept/Reject flow existed.

### Solution
Added Accept/Reject buttons, rejection popup with reason, and connected Accept → approve → convert wizard flow.

### Files Changed

| File | Change |
|------|--------|
| `frontend/src/pages/superadmin/DemoRequestDetailPage.jsx` | Added Accept/Reject buttons, rejection popup, converted company display, fixed `module_ids` bug in `handleConvert` |

### Detailed Changes

**Accept Button** (when status is `NEW` or `PROPOSAL_SENT`):
- Calls `demoApi.approve(id)` → updates request status to `APPROVED`
- Opens the existing "Convert to Company" wizard with pre-filled data from the demo request

**Reject Button** (when status is `NEW` or `PROPOSAL_SENT`):
- Opens a popup dialog with a textarea for rejection reason
- Calls `demoApi.reject(id, reason)` → updates request status to `REJECTED`
- Reason is saved as notes on the demo request

**Converted Company Display** (after conversion):
- Shows company name, code, admin email, creation date
- "View Company" button navigates to `/admin/companies/:companyId`

### Bug Fix
- Fixed `module_ids` → `moduleIds` typo in `handleConvert` (was referencing undefined variable)

---

## Verification

### Backend Tests
```
python -m django test superadmin invitations -v 2
Ran 10 tests in 3.326s — OK
```

### Frontend Build
```
npm run build
transforming...✓ 786 modules transformed
✓ built in 593ms
```

### Frontend Lint
```
npm run lint
No new errors — only pre-existing warnings
```

### API Endpoints Used (All Existing)
- `GET /api/v1/superadmin/companies/` — list (now properly paginated with envelope)
- `GET /api/v1/superadmin/companies/{id}/` — retrieve (now returns extended detail)
- `GET /api/v1/superadmin/plans/` — plans list (for company detail subscription)
- `GET /api/v1/superadmin/modules/` — modules list (for company detail)
- `GET /api/v1/employees/` — employees list (filterable by company_id)
- `POST /api/v1/demo/{id}/approve/` — approve demo request
- `POST /api/v1/demo/{id}/reject/` — reject demo request with notes
- `POST /api/v1/demo/{id}/convert/` — convert to company (already existed)

---

## What Was NOT Changed

- Authentication/login flow (already fixed in prior session)
- CookieJWTAuthentication (already verified correct)
- OCR, AI Assistant, Invoice Reader features
- NetSuite integration logic
- Plans, Modules, Employees management pages
- Support sessions, notifications pages
- Role-based permissions

---

## Code Cleanup Notes

Per project guidelines ("Comment out old code, don't delete"):
- Old CompaniesPage detail drawer is fully commented out
- `InfoCard` import is commented out (was only used in old drawer)
- Old `openDrawer` function is commented out
- `selected`/`drawerOpen` state declarations are commented out

---

## Files Summary

### New Files Created
- `frontend/src/pages/superadmin/CompanyDetailPage.jsx`

### Files Modified (Backend)
- `backend/superadmin/views.py` — Added `list()` and `retrieve()` overrides, `get_queryset()` enhancement, import additions
- `backend/superadmin/serializers.py` — Added `CompanyDetailSerializer`, `CompanyPlanSummarySerializer`, admin fields on `CompanySerializer`

### Files Modified (Frontend)
- `frontend/src/pages/superadmin/DashboardPage.jsx` — Company name clickable
- `frontend/src/pages/superadmin/CompaniesPage.jsx` — Company name → detail page, column changes, drawer commented out, back button added
- `frontend/src/pages/superadmin/CompanyDetailPage.jsx` — **New file** — Added back button navigating to Companies list
- `frontend/src/pages/superadmin/CompanySubscriptionPage.jsx` — Added back button navigating to Company Detail page
- `frontend/src/pages/superadmin/DemoRequestDetailPage.jsx` — Accept/Reject buttons, rejection popup, converted company display, bug fix, back button added
- `frontend/src/routes/AppRoutes.jsx` — Added `/admin/companies/:id` route

### Files Modified (Documentation)
- `frontend/ROUTING_AUDIT_REPORT.md` — Updated with company creation flow documentation