# ERP Pulse - Project Memory

Last Updated: July 2026

---

# 1. Project Overview

ERP Pulse is a Django + React based ERP integration platform.

Current primary integration:
- Oracle NetSuite

Future integrations:
- SAP
- Zoho
- Tally
- QuickBooks
- Microsoft Dynamics
- Others

Goal:

Allow a user to connect one or multiple ERP accounts and fetch business
data into ERP Pulse through a clean service-oriented architecture.

The backend follows a layered architecture.

View
↓

Service
↓

Repository

↓

Client (HTTP)

↓

NetSuite API

Business logic belongs only inside Services.

HTTP communication belongs only inside Client.

Database access belongs only inside Repository.

Views must stay thin.

---

# 2. Original Architecture

Initially the project supported only ONE NetSuite account per user.

Architecture:

User
↓

NetSuiteConnection

Problems:

- Only one ERP account
- Credentials stored globally
- No account switching
- Not scalable for future ERPs

---

# 3. Major Refactor

The project was redesigned to support multiple NetSuite accounts.

Current architecture:

User
↓

Many NetSuiteConnections

↓

One Active Connection

Every connection stores:

- Client Name
- Environment
- Account ID
- Client ID
- Client Secret
- OAuth Tokens
- Status
- Active Flag

OAuth is now performed per connection instead of globally.

---

# 4. Refactors Completed

## Models

Completed

Changes:

- OneToOne → ForeignKey
- Added multiple connection support
- Added status
- Added active flag
- Added environment
- Added client credentials
- Added uniqueness constraint

Progress:
100%

---

## Repository

Completed

Implemented:

- create()
- list_by_user()
- get_by_user()
- get_by_id()
- rename()
- delete()
- switch_active_connection()
- complete_oauth()
- update_tokens()

Progress:
100%

---

## OAuth

Completed

Changes:

State now stores:

user_id:connection_id

instead of

user_id

Authorization URL now uses:

- account_id
- client_id

instead of Django settings.

Progress:
100%

---

## Client

Completed

Refactor:

Client is no longer global.

Every request creates a client using the selected connection.

Settings only contain:

NETSUITE_REDIRECT_URI

Everything else comes from database.

Progress:
100%

---

## Services

Completed

ConnectionService

Handles:

- OAuth
- Create connection
- Rename
- Delete
- Switch
- Callback

DataService

Handles:

- Token refresh
- Authenticated client
- Record fetching

Progress:
100%

---

## Views

Current Status

CRUD views are being implemented.

Endpoints:

GET /connections/

POST /connections/

PATCH /connections/{id}/

DELETE /connections/{id}/

POST /connections/{id}/switch/

Progress:
Almost complete.

---

# 5. Current API

OAuth

GET /callback/

Connection Management

GET /connections/

POST /connections/

PATCH /connections/{id}/

DELETE /connections/{id}/

POST /connections/{id}/switch/

Data APIs

Customers

Employees

Items

Vendors

Sales Orders

Purchase Orders

Invoices

SuiteQL

---

# 6. Current Progress

Overall Backend

≈ 98%

Remaining backend work:

- Finish CRUD views
- Remove obsolete /connect endpoint
- Minor cleanup
- Testing

Estimated remaining backend work:

2%

---

# 7. Frontend Status

Still needs:

- Connection management UI
- Add Connection screen
- Connection List
- Rename
- Delete
- Switch Active
- OAuth Redirect handling

---

# 8. Long-Term Vision

ERP Pulse should become an ERP aggregation platform.

One user

↓

Many ERP Systems

↓

Many Accounts

↓

Unified Dashboard

↓

Analytics

↓

Reports

↓

AI Insights

NetSuite is only the first ERP implementation.

Future architecture should allow adding SAP, Zoho, Tally, Dynamics etc.
without changing the core architecture.

---

# 9. Important Architecture Rules

Never put business logic inside Views.

Never call requests directly outside Client.

Repository must never contain business logic.

Services orchestrate everything.

One active connection per ERP.

OAuth credentials belong to each connection.

Do not use global ERP credentials except redirect URI.

---

# 10. Future Tasks

Backend

- Finish CRUD views
- Integration tests
- Better exception handling
- Encrypt OAuth tokens
- Background sync
- Webhooks
- Sync history

Frontend

- Connection Management
- Dashboard
- Data Explorer
- Settings

Infrastructure

- Redis
- Celery
- Scheduled Sync
- Docker
- Monitoring

---

# 11. Overall Project Completion

Backend Architecture:
98%

Backend APIs:
95%

Frontend:
20%

Production Readiness:
60%

Overall ERP Pulse:
~45%

---

# 12. Notes for Future AI / Developers

This project has already undergone a major architecture refactor from
single-account support to multi-account support.

Do not reintroduce global NetSuite credentials.

Always preserve the layered architecture.

When making changes, prefer extending Services and Repository instead of
adding logic to Views.

The long-term goal is to support multiple ERP systems with minimal
changes to the core architecture.