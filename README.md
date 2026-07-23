# ERP Pulse

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6.x-green)
![DRF](https://img.shields.io/badge/DRF-REST-red)
![Status](https://img.shields.io/badge/Status-Under%20Development-orange)
![License](https://img.shields.io/badge/License-Private-lightgrey)

ERP Pulse is a backend platform built with **Django** that integrates with ERP systems to provide a unified interface for accessing business data.

The long-term vision of ERP Pulse is to become a centralized ERP integration platform where users can connect multiple ERP systems (NetSuite, SAP, Zoho, Tally, QuickBooks, Microsoft Dynamics, etc.) from a single application.

Currently, Oracle NetSuite integration is under active development.

---

# Live Demo

- Frontend: [https://erp-pulse-gamma.vercel.app/](https://erp-pulse-gamma.vercel.app/)
- Backend API: [https://erp-pulse-backend.onrender.com](https://erp-pulse-backend.onrender.com)

---

# Features

## Current Features

- OAuth 2.0 Authorization Code Grant with Oracle NetSuite
- Multiple NetSuite Account Support (connect, rename, switch active, delete)
- Automatic Access Token Refresh
- NetSuite Credentials Encrypted at Rest (client secret, access token, refresh token)
- Connection Health Tracking (consecutive failure count, computed health status)
- Connection Audit Trail (created / renamed / switched / deleted / OAuth completed)
- Manual Sync Manager — orchestrated, per-entity-stage sync runs with independent retry of failed stages
- REST Record API Integration
- SuiteQL Query Support
- Centralized Analytics Service — single source of truth for KPI/business calculations, shared by Dashboard, Reports, and AI
- Sales & Revenue Trend Reporting (SuiteQL-aggregated, month-over-month)
- AI Business Intelligence Assistant — pluggable providers (OpenAI, Gemini), typed business context objects, prompt versioning, per-call audit logging, short-TTL context caching
- User Login/Activity History
- JWT Authentication with Email OTP (registration + login)
- Operational Monitoring (request/error logging)
- Layered Architecture — Repository Pattern, Service-Oriented Design

Supported NetSuite Records:

- Customers
- Employees
- Vendors
- Items
- Sales Orders
- Purchase Orders
- Invoices

---

# Project Architecture

The backend follows a layered architecture.

```
                APIView
                   │
                   ▼
               Service Layer
                   │
                   ▼
            Repository Layer
                   │
                   ▼
               Database Models

                   │

           NetSuite Client Layer
              (HTTP + Errors + Pagination)
                   │
                   ▼
             Oracle NetSuite APIs
```

Responsibilities

### Views

- Authentication
- Request validation
- Response formatting

No business logic.

---

### Services

Responsible for business logic.

Examples:

- OAuth Flow
- Token Refresh
- Connection Management
- Sync Orchestration (Sync Manager)
- KPI/Business Calculations (Analytics Service)
- Business Rules

---

### Repository

Responsible only for database operations.

Examples:

- CRUD
- Transactions
- Queries

No HTTP communication.

---

### Client

Responsible only for communication with NetSuite.

Split into focused pieces:

- `client.py` — builds and issues NetSuite requests (OAuth token exchange/refresh, REST Record reads, SuiteQL)
- `http.py` — generic HTTP sending: timeout, correlation ID, retry/backoff on idempotent calls
- `errors.py` — maps NetSuite HTTP responses to typed exceptions
- `pagination.py` — walks NetSuite REST collection responses across all pages

---

# Current Architecture

Each ERP Pulse user can connect multiple NetSuite accounts. The same NetSuite account may also be connected independently by different ERP Pulse users.

```
User

├── NetSuite Connection A

├── NetSuite Connection B

└── NetSuite Connection C
```

Only one connection is active at a time.

Each connection stores:

- Client Name
- Environment
- Account ID
- Client ID
- Client Secret (encrypted at rest)
- OAuth Tokens (encrypted at rest)
- Connection Status
- Health (computed from status + consecutive failure count)
- Last Used / Last Synced timestamps

Every lifecycle event on a connection (created, renamed, switched active, deleted, OAuth completed) is recorded in a connection audit log.

---

# Analytics & AI Architecture

## Analytics

`AnalyticsService` is the single source of truth for KPI/business calculations (top customers, overdue invoices, sales summary, revenue by period/customer, sales trend by month). Dashboard, Reports, and AI all consume it — no module runs its own duplicate NetSuite aggregation query.

```
Dashboard ──┐
Reports   ──┼──▶  AnalyticsService  ──▶  NetSuite (SuiteQL)
AI        ──┘
```

## AI

- AI never communicates with NetSuite directly — only with `AnalyticsService`/`DashboardService` via a dedicated Context Builder.
- Business context passed to the AI is a typed object (`BusinessContext`/`AIRequestContext`), not a bare dict.
- Prompt construction is separated into its own module, with a version tag (`PROMPT_VERSION`) tracked per request.
- Every AI provider call is recorded in an `AIAuditLog` (provider, model, prompt version, latency, success/failure) — distinct from the user-facing conversation transcript.
- The assembled business context (not the AI's answer) is cached for a short TTL per user, avoiding redundant SuiteQL calls on rapid follow-up questions without risking a stale or mismatched answer.
- AI providers are pluggable (OpenAI, Gemini) behind a common interface.

---

# Sync Manager

A manual, on-demand sync orchestration layer sits above the NetSuite Client and Data Service.

```
SyncRun (one per sync execution)
   │
   ├── SyncStage: customer
   ├── SyncStage: employee
   ├── SyncStage: vendor
   ├── SyncStage: salesOrder
   ├── SyncStage: purchaseOrder
   └── SyncStage: invoice
```

- A run's overall status rolls up from its stages (`success` / `partial_failure` / `failed`)
- A failed stage can be retried on its own, without re-running stages that already succeeded
- Only one sync can run at a time per connection
- Incremental sync uses the connection's last successful sync as a watermark

**Scheduled/background sync is not yet implemented** — it requires a task queue (Celery + Redis), which isn't part of the stack yet. Currently sync is triggered on demand via the API.

---

# Tech Stack

Backend

- Python
- Django
- Django REST Framework

Database

- PostgreSQL (via [Neon](https://neon.tech))

Authentication

- JWT
- OAuth 2.0 Authorization Code Flow
- Email OTP (registration and login)

External APIs

- Oracle NetSuite REST API
- NetSuite SuiteQL

AI Providers

- OpenAI
- Google Gemini

Hosting

- Backend: [Render](https://render.com)
- Frontend: [Vercel](https://vercel.com)
- Database: [Neon](https://neon.tech)

---

# API Modules

Current backend includes:

```
accounts/
common/
netsuite/
ai/
dashboard/
analytics/
reports/
monitoring/
sync/
```

The NetSuite module contains:

- OAuth
- Client (+ http / errors / pagination)
- Services
- Repository
- Models
- Views
- Serializers

---

# Current Progress

Backend

- Models, Repository, OAuth, Client — Complete
- Multi-connection CRUD, Connection Health, Audit Trail — Complete
- Token Encryption at Rest — Complete
- Centralized Analytics Service (Dashboard + Reports + AI share one source of truth) — Complete
- AI: typed business context, prompt versioning, audit logs, context caching, pluggable providers — Complete
- Sync Manager (manual/on-demand) — Complete
- Login/Activity History — Complete
- Monitoring (error/request logging) — Complete

Current focus:

- Test suite cleanup — several tests still target pre-refactor code shape (old NetSuite client mocks, old dict-based AI context, the pre-move Analytics service location) and need updating; not a functional regression, but real coverage gaps until addressed
- Verifying a handful of SuiteQL/REST field assumptions against a live NetSuite sandbox (flagged inline in code docstrings where relevant)
- Scheduled/background sync (requires Celery + Redis)
- Frontend surfacing for connection health, audit trail, and Sync Manager

---

# Roadmap

Upcoming Features

## Backend

- Test suite cleanup and expanded coverage for recently added/moved modules
- Sandbox verification of flagged SuiteQL/REST assumptions
- Scheduled Background Sync (Celery + Redis)
- Rate-limit-aware retry tuned against a live NetSuite sandbox

## Frontend

- Sync run history / trigger UI
- Connection health & audit trail UI
- ERP Explorer

## Future ERP Integrations

- SAP
- Zoho
- Tally
- QuickBooks
- Microsoft Dynamics

---

# Deployment

- Frontend: Vercel — [https://erp-pulse-gamma.vercel.app/](https://erp-pulse-gamma.vercel.app/)
- Backend API: [https://erp-pulse-backend.onrender.com](https://erp-pulse-backend.onrender.com)
- Database: Neon (managed PostgreSQL)

---

# Project Documentation

Additional project documentation is available.

| File | Description |
|------|-------------|
| PROJECT_MEMORY.md | Complete project context, architecture decisions, current progress and future plans |
| CHANGELOG.md | History of major development milestones and refactors |

---

# Development Status

Current milestone:

**Analytics & AI Architecture**

Status:

🟡 In Progress (backend complete, test coverage and sandbox verification pending)

Remaining work:

- Test suite cleanup (see Current Progress above)
- Sandbox verification of flagged SuiteQL/REST assumptions
- Frontend surfacing of health/audit/sync/analytics data
- Scheduled sync (Celery + Redis)

---

# Design Principles

The project follows these principles:

- Thin Views
- Service-Oriented Architecture
- Repository Pattern
- Separation of Concerns
- Connection-based OAuth
- Encrypted Credentials at Rest
- Auditable Connection Lifecycle
- Single Source of Truth for Business Calculations
- Scalable Multi-ERP Design

---

# Long-Term Vision

ERP Pulse aims to evolve into a complete ERP aggregation platform.

```
User

        │

        ▼

ERP Pulse

        │

 ┌──────┼────────┬────────┬────────┐

 ▼      ▼        ▼        ▼        ▼

NetSuite SAP    Zoho    Tally   Dynamics
```

Users will be able to manage multiple ERP systems from a single dashboard without switching between different ERP applications.

---

# License

This project is currently under active development.
