# Changelog

All notable changes to ERP Pulse will be documented in this file.

This project follows a milestone-based changelog instead of release versioning during development.

---

# [Unreleased]

## Added

### Monitoring

- New `monitoring` app covering all four operational areas:
  - **NetSuite connection health** — `NetSuiteConnection` now tracks `last_synced_at`, `last_error`,
    and `consecutive_failures`, updated automatically on every data fetch and token refresh. A
    connection auto-flips to `error` status after 3 consecutive failures. Surfaced on the Connect
    NetSuite page (last synced time, failure count, token-expiry warning).
  - **Application error monitoring** — unhandled/server exceptions are persisted to a new `ErrorLog`
    model via the central DRF exception handler, plus a console `LOGGING` config as a second view
    onto the same errors.
  - **System uptime / health check** — `GET /api/v1/monitoring/health/` (public, for Render/uptime
    pingers) checks database connectivity, SMTP configuration, and the field-encryption key.
  - **API usage & rate limit monitoring** — `RequestMonitoringMiddleware` logs every `/api/v1/*`
    request to a new `RequestLog` model; `GET /api/v1/monitoring/api-usage/` (staff-only) aggregates
    request volume, error rate, throttling, and latency by endpoint.
- New frontend `/system-health` page showing health check status, API usage stats, and recent errors
  (admin-only sections degrade gracefully to "Admin access required" for non-staff users).
- 9 new tests covering health check, permissions, and middleware behavior (251/251 passing project-wide).

### Frontend

- Added persistent `Footer` component shown on every page (dashboard and auth layouts), linking to
  the developer's portfolio.
- Connect NetSuite page: added **Rename Connection** (inline edit), completing frontend connection
  management (List, Add, Rename, Delete, Switch Active, OAuth Redirect Handling).

### Documentation

- Added `Live Demo` section to README linking the deployed Vercel frontend.
- Added `Deployment` section to README with the Render backend API link, labeled for developers.

### Backend

- Configured SMTP email backend for OTP delivery via Gmail (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`).
- Fixed a typo in `EMAIL_BACKEND` (`smt` → `smtp`) that would have broken OTP email delivery in production.

## Fixed

- Fixed a pre-existing typo in a `netsuite` test helper (`refresh-token` → `refresh_token`) that was
  causing 16 tests to fail.

## Planned

### Backend

- Remove obsolete `/connect` endpoint (leftover commented-out route/import cleanup)
- Integration Testing (end-to-end OAuth against a live NetSuite sandbox)
- Background Sync
- Sync History
- Missing migration for `accounts.LoginActivity` — model exists in code but has no migration yet;
  needs a decision from the team before generating one (see Notes below).

### Frontend

- Settings Page (beyond current auth read-only view — connection defaults, notification prefs, etc.)

---

# Milestone 4 - Multi Account NetSuite Refactor (Current)

Status: 🚧 In Progress

## Added

### NetSuiteConnection Model

- Changed relationship from OneToOneField to ForeignKey.
- Added support for multiple NetSuite connections per user.
- Added `client_name`.
- Added `environment`.
- Added `client_id`.
- Added `client_secret`.
- Added `status`.
- Added `is_active`.
- Added uniqueness constraint on `(user, netsuite_account_id)`.
- OAuth token fields are nullable until OAuth callback completes.

---

### Repository Layer

Added:

- `create()`
- `list_by_user()`
- `get_by_user()`
- `get_by_id()`
- `rename()`
- `delete()`
- `switch_active_connection()`
- `complete_oauth()`
- `update_tokens()`

Repository is now fully responsible for persistence only.

---

### OAuth

Refactored OAuth flow.

Old:

```
state = user_id
```

New:

```
state = user_id:connection_id
```

Authorization URL now uses credentials stored inside each connection instead of global Django settings.

---

### NetSuite Client

Refactored client to become connection-aware.

Old:

```python
NetSuiteAuthClient()
```

New:

```python
NetSuiteAuthClient(
    account_id,
    client_id,
    client_secret,
    access_token,
)
```

Every request now uses the currently selected connection.

---

### Services

ConnectionService now supports:

- Create Connection
- OAuth Callback
- Rename Connection
- Delete Connection
- Switch Active Connection

DataService now supports:

- Automatic token refresh
- Authenticated client creation
- Record fetching
- SuiteQL

---

### URLs

Added:

```
GET    /connections/
POST   /connections/
PATCH  /connections/{id}/
DELETE /connections/{id}/
POST   /connections/{id}/switch/
```

---

### Architecture

Refactored project from:

```
User
    │
    ▼
NetSuiteConnection
```

to

```
User
    │
    ├── Connection A
    ├── Connection B
    └── Connection C
```

Only one connection remains active.

---

## Changed

- OAuth credentials are no longer loaded globally.
- Token refresh is now connection-specific.
- Services now create clients dynamically.
- Repository owns all persistence.
- Views remain thin.

---

## Remaining

- Finish CRUD Views.
- Remove obsolete `/connect` endpoint.
- End-to-end OAuth testing.
- Integration testing.

Estimated Completion:

Backend: **98%**

Overall Project: **45%**

---

# Milestone 3 - Generic NetSuite Data Layer

Status: ✅ Completed

## Added

- Generic REST Record API support.
- Generic `get_records()`.
- Generic `get_record()`.
- Generic `execute_suiteql()`.

Added support for:

- Customers
- Employees
- Vendors
- Items
- Sales Orders
- Purchase Orders
- Invoices

Implemented automatic token refresh before API requests.

---

# Milestone 2 - OAuth Integration

Status: ✅ Completed

## Added

Implemented OAuth 2.0 Authorization Code Flow.

Implemented:

- Authorization URL generation
- State signing
- Callback validation
- Token exchange
- Token refresh

---

# Milestone 1 - Initial NetSuite Integration

Status: ✅ Completed

## Added

Initial project structure.

Created:

- Models
- Repository
- Client
- Services
- Views
- OAuth Module

Implemented first successful NetSuite authentication and data retrieval.

---

# Future Milestones

## Milestone 5

Frontend Connection Management

- Connection List
- Add Connection
- Rename
- Delete
- Switch Active

---

## Milestone 6

Background Synchronization

- Celery
- Redis
- Scheduled Sync
- Sync Logs

---

## Milestone 7

ERP Abstraction Layer

Support multiple ERP providers:

- SAP
- Zoho
- Tally
- Dynamics
- QuickBooks

without changing the core architecture.

---

# Long-Term Vision

Transform ERP Pulse from a NetSuite integration into a complete ERP aggregation platform capable of connecting multiple ERP providers through a unified architecture.