# ERP Pulse - Project Memory

> This document provides complete project context for developers and AI assistants working on ERP Pulse.
>
> Read this file before making architectural or implementation changes.

---

# Project Overview

ERP Pulse is a Django + React based ERP Integration Platform.

The long-term vision is to provide a single platform where users can connect multiple ERP systems (NetSuite, SAP, Zoho, Tally, QuickBooks, Microsoft Dynamics, etc.) and access all ERP data from one unified dashboard.

Current ERP supported:

- Oracle NetSuite

Future ERPs:

- SAP
- Zoho
- Tally
- Microsoft Dynamics
- QuickBooks
- Others

---

# Primary Goal

Allow a single ERP Pulse user to connect multiple ERP accounts.

Example:

User

├── NetSuite Account A

├── NetSuite Account B

├── SAP Account

├── Zoho Account

└── Tally Account

Only one connection of each ERP type should be active at a time.

---

# Backend Architecture

The backend follows a layered architecture.

```
APIView
    ↓
Service
    ↓
Repository
    ↓
Model

Client (HTTP Layer)
    ↓
NetSuite API
```

Responsibilities:

### Views

- Authentication
- Validation
- Response formatting

Views must never contain business logic.

---

### Services

Business logic.

Responsible for:

- OAuth Flow
- Token Refresh
- Connection Management
- Business Rules

---

### Repository

Database only.

Responsible for:

- CRUD
- Queries
- Transactions

Never call HTTP APIs here.

---

### Client

Only HTTP communication with NetSuite.

Responsible for:

- OAuth Token Exchange
- Token Refresh
- REST API Requests
- SuiteQL Requests

Never store database objects here.

---

# Original Architecture

Originally ERP Pulse supported only ONE NetSuite account.

```
User
   │
   ▼
NetSuiteConnection
```

Problems:

- One account only
- Global credentials
- No account switching
- Impossible to support future ERPs

---

# New Architecture

Now ERP Pulse supports multiple NetSuite accounts.

```
User
   │
   ▼
NetSuiteConnection
NetSuiteConnection
NetSuiteConnection
```

One connection is marked active.

```
User
     │
     ├── Connection A
     │      active=False
     │
     ├── Connection B
     │      active=True
     │
     └── Connection C
            active=False
```

Future ERPs should follow the same design.

---

# Major Refactor Completed

## Model

Completed

Changes:

- OneToOneField → ForeignKey
- Added:

    client_name

    environment

    client_id

    client_secret

    status

    is_active

- OAuth fields nullable until callback
- Unique constraint
- Multiple connections per user

Status:

✅ Complete

---

## Repository

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

Status:

✅ Complete

---

## OAuth

Old state:

```
user_id
```

New state:

```
user_id:connection_id
```

Authorization URL now uses credentials stored inside the selected connection instead of Django settings.

Status:

✅ Complete

---

## Client

Previously:

```
NetSuiteAuthClient()
```

Now:

```
NetSuiteAuthClient(
    account_id,
    client_id,
    client_secret,
    access_token,
)
```

Client is now completely connection-aware.

Status:

✅ Complete

---

## Service Layer

Implemented:

ConnectionService

- OAuth callback
- Create Connection
- Rename
- Delete
- Switch
- Authorization URL

DataService

- Token Refresh
- Authenticated Client
- Fetch Records
- SuiteQL

Status:

✅ Complete

---

# Current APIs

OAuth

GET /callback/

Connections

GET /connections/

POST /connections/

PATCH /connections/{id}/

DELETE /connections/{id}/

POST /connections/{id}/switch/

Records

Customers

Employees

Items

Invoices

Sales Orders

Purchase Orders

Vendors

SuiteQL

---

# Current Progress

## Backend

Models

✅ 100%

Repository

✅ 100%

OAuth

✅ 100%

Client

✅ 100%

Services

✅ 100%

Views

🟡 Almost Complete

Testing

❌ Pending

---

# Remaining Backend Work

Still remaining:

- Finish Connection CRUD Views
- Remove obsolete /connect endpoint
- Integration Testing
- Token encryption
- Unit Tests

Estimated backend remaining work:

≈ 2%

---

# Frontend Remaining

Need UI for:

- Connection List
- Add Connection
- Rename Connection
- Delete Connection
- Switch Connection
- OAuth Redirect
- Settings Page

Estimated frontend completion:

≈ 20%

---

# Long-Term Roadmap

Backend

- Background Sync
- Incremental Sync
- Celery
- Redis
- Webhooks
- Audit Logs

Frontend

- Dashboard
- Reports
- Analytics
- Connection Manager
- ERP Explorer

Infrastructure

- Docker
- Monitoring
- CI/CD
- Rate Limiting
- Background Jobs

Future Integrations

- SAP

- Zoho

- Dynamics

- Tally

- QuickBooks

---

# Important Design Rules

Always follow these rules.

1.

Views must stay thin.

2.

Business logic belongs only in Services.

3.

Repositories never call HTTP APIs.

4.

Client never touches database models.

5.

Never use global NetSuite credentials except redirect URI.

6.

Every OAuth flow belongs to one specific connection.

7.

Only one active NetSuite connection per user.

8.

Future ERP integrations should reuse the same architecture.

---

# Current Estimated Completion

Backend Architecture

98%

Backend Functionality

95%

Frontend

20%

Production Ready

60%

Overall ERP Pulse

≈ 45%

---

# Next Immediate Task

Current work is focused on finishing multi-account support.

Remaining immediate tasks:

1.

Implement Connection CRUD Views

2.

Complete frontend connection management

3.

End-to-end OAuth testing

4.

Integration testing

After these are complete, multi-account support for NetSuite will be finished.

---

# Notes For Future Developers / AI

This project has already undergone a large architectural refactor.

Do NOT redesign the architecture back to single-account support.

Preserve the layered architecture.

When adding new ERP systems, reuse the existing connection architecture instead of creating ERP-specific implementations.

Whenever making architectural changes, update this PROJECT_MEMORY.md file so it always reflects the latest project state.