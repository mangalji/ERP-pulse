# Changelog

All notable changes to ERP Pulse will be documented in this file.

This project follows a milestone-based changelog instead of release versioning during development.

---

# [Unreleased]

## Planned

### Backend

- Complete Connection CRUD Views
- Remove obsolete `/connect` endpoint
- Integration Testing
- Unit Testing
- Encrypt OAuth Tokens
- Background Sync
- Sync History

### Frontend

- Connection Management UI
- OAuth Redirect Handling
- Dashboard
- Settings Page

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