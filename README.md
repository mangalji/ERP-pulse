# AGSuite ERP

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6.x-green)
![DRF](https://img.shields.io/badge/DRF-REST-red)
![React](https://img.shields.io/badge/React-19-61dafb)
![Vite](https://img.shields.io/badge/Vite-8-646cff)
![Status](https://img.shields.io/badge/Status-Active%20Development-yellow)
![License](https://img.shields.io/badge/License-Private-lightgrey)

**AGSuite ERP** is a multi-tenant SaaS ERP aggregation platform built with **Django REST Framework** and **React (Vite)**. It provides a unified dashboard for businesses to manage ERP integrations (NetSuite, and more in the future), AI-powered analytics, OCR-based invoice processing, subscription/licensing, and enterprise reporting — all under a single subscription.

---

## Live Deployment

| Layer | URL | Host |
|-------|-----|------|
| Frontend | [https://agsuite-erp-gamma.vercel.app](https://agsuite-erp-gamma.vercel.app) | Vercel |
| Backend API | [https://agsuite-erp-backend.onrender.com](https://agsuite-erp-backend.onrender.com) | Render |
| Database | Neon PostgreSQL | Neon |
| Redis | Render Key Value | Render |

---

## Table of Contents

- [Platform Architecture](#platform-architecture)
- [Core Modules](#core-modules)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture & Design Principles](#architecture--design-principles)
- [Authentication & Security](#authentication--security)
- [Multi-Tenancy Model](#multi-tenancy-model)
- [Local Development](#local-development)
- [Docker](#docker)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [Testing](#testing)
- [Documentation](#documentation)
- [Roadmap & Long-Term Vision](#roadmap--long-term-vision)
- [Development Status](#development-status)
- [Design Principles (recap)](#design-principles-recap)
- [License](#license)

---

## Platform Architecture

```
AGSuite Platform
    │
    ▼
Super Admin (Platform operator)
    │
    ▼
Company (Tenant)
    │
    ├── Company Admin
    │     ├── Subscriptions / Plans / Modules
    │     ├── Employees
    │     └── ERP Connections (e.g. NetSuite)
    │
    └── Company Employees
          └── Assigned ERP Connections (no credentials exposure)
```

**Key concepts**

- **Platform** → top-level operator (Super Admin) manages companies, plans, modules, and global settings.
- **Company (Tenant)** → a subscribed organization. All data is company-scoped via `TenantMiddleware`.
- **Company Admin** → manages their own company: plans, modules, employees, ERP connections.
- **Employee** → can only use ERP connections explicitly assigned to them (credentials stay hidden).

---

## Core Modules

| # | Module | Description |
|---|--------|-------------|
| 1 | **accounts** | Custom User model, JWT auth (access + refresh), email OTP for registration/login, password reset, profile updates, login history |
| 2 | **tenancy** | Company model, tenant middleware, per-request company resolution, company lifecycle (suspend/activate/soft-delete/purge) |
| 3 | **rbac** | Role-based access control, role assignment per user/company |
| 4 | **audit** | Append-only audit log for critical lifecycle events |
| 5 | **notifications** | In-app notification system with unread counts, per-user channels |
| 6 | **common** | Shared utilities, email sending (SMTP + Brevo HTTP fallback), throttles |
| 7 | **demo** | Public demo request submission, superadmin approval/rejection, conversion to company |
| 8 | **invitations** | UUID-based invitation tokens, expiry (1–30 days), resend/expire flows |
| 9 | **subscriptions** | Plans, company-plan assignment, upgrade/downgrade/renew/cancel, automated trial expiry, history |
| 10 | **superadmin** | Companies, plans, modules, employees, demo requests, support sessions, platform notifications |
| 11 | **netsuite** | OAuth 2.0 Authorization Code Grant, connection management, employee assignment, REST Record API + SuiteQL, token lifecycle, connection health, OCR integration |
| 12 | **ai** | Pluggable AI providers (OpenAI, Gemini), business context, prompt versioning, per-call audit, short-TTL caching |
| 13 | **ocr** | Invoice/document extraction, preprocessing, field mapping to NetSuite, validation, posting |
| 14 | **invoice** | Invoice management |
| 15 | **dashboard** | Aggregated company dashboard (summary, recent activity, executive charts) |
| 16 | **reports** | Ad-hoc reports (sales trend, etc.) |
| 17 | **reports_engine** | Scheduled report generation, templates, schedules, history, email delivery |
| 18 | **monitoring** | Request monitoring, API usage tracking, error logs, health endpoint |
| 19 | **sync** | Sync orchestration (Celery tasks for NetSuite reference data, etc.) |
| 20 | **analytics** | Centralized analytics service shared by Dashboard / Reports / AI |
| 21 | **bi** | Business Intelligence dashboards (sales, purchase, customer, inventory, finance, alerts, insights) |

---

## Key Features

### 🔐 Authentication
- **JWT** with dual-mode auth:
  - In-memory access token + `Authorization: Bearer` header (primary for cross-origin frontend → backend)
  - httpOnly `access_token` / `refresh_token` cookies (fallback for same-origin)
- **Email OTP** for registration, login, and sensitive profile changes
- **Password reset** via OTP (no link in email — OTP-only)
- **Login history** per user
- Automatic access-token refresh with request queuing on 401 (no request thrashing under concurrent expiry)

### 🏢 Multi-Tenancy
- `TenantMiddleware` injects the active company into every authenticated request
- All tenant-scoped queries filter by `company_id`
- Company lifecycle: operational, suspended, soft-deleted, purged (with periodic Celery cleanup)
- Failed requests blocked on suspended/deleted companies with a clean 403

### 📝 Demo Request & Onboarding
- Public demo submission with validation
- Superadmin approval / rejection workflow
- 5-step conversion wizard → company:
  1. Company details
  2. Plan selection
  3. Module selection
  4. Usage limits
  5. Company Admin creation
- Automated invitation email for the first Company Admin

### 📨 Invitation System
- UUID-based, single-use tokens
- Configurable expiry (1–30 days)
- Public acceptance page with password setup
- Resend / expire / cancel flows
- Duplicate-active-invitation prevention

### 💳 Subscription & Licensing
- Plan assignment, upgrade, downgrade, renew, cancel
- Per-module usage tracking (OCR pages, AI requests, employee count, storage, etc.)
- License enforcement middleware on every request
- Client-facing subscription page with usage progress
- Superadmin subscription management with tabs: Subscription / Modules / Usage / History

### 🔗 NetSuite Integration
- **OAuth 2.0 Authorization Code Grant** (no client credentials ever stored in browser)
- Multiple connections per company (multi-account)
- One active connection per user (with switch endpoint)
- Employee assignment to connections (credentials stay server-side)
- **Token manager** with row-level locking for safe concurrent refresh
- **REST Record API + SuiteQL** support
- **Connection health**: test connection, consecutive failure tracking, unhealthy-threshold auto-flagging
- **OCR integration**: field catalogue, mapping suggestions, document validation, vendor bill posting
- Full **audit trail** for every connection lifecycle event
- Encrypted credentials at rest (Fernet `FIELD_ENCRYPTION_KEY`)

### 🤖 AI Assistant
- Pluggable providers: **OpenAI** and **Google Gemini** (configurable via `AI_PROVIDER`)
- Typed business-context objects (no free-form prompt injection)
- Per-call audit logging
- Short-TTL context caching
- Centralized `AnalyticsService` shared by Dashboard / Reports / AI
- Graceful degradation when API key is missing

### 📄 OCR & Invoice Posting
- Document upload + preprocessing
- Field extraction
- Field mapping to NetSuite (with auto-suggest)
- Document validation against NetSuite reference data
- Vendor Bill posting back to NetSuite

### 📊 Reporting & BI
- Ad-hoc reports (sales trend, etc.)
- Scheduled reports (templates + cron-style schedules)
- Email delivery of generated reports
- BI dashboards across sales / purchase / customer / inventory / finance
- Insights + alerts

### 🛡️ Security
- JWT in httpOnly cookies (XSS-resistant)
- Encrypted NetSuite credentials at rest (Fernet)
- Company-scoped data isolation enforced at the query layer
- License enforcement middleware
- Append-only audit trail
- CORS allowlist (no wildcard in production)
- CSRF + HSTS + Secure cookies in production
- Email-based throttling on registration / login / password reset

---

## Tech Stack

### Backend
- **Python** 3.12
- **Django** 6.x
- **Django REST Framework**
- **PostgreSQL** (Neon in production, Docker PostgreSQL container for local Docker development, SQLite for non-Docker local development)
- **SimpleJWT** (JWT auth)
- **OAuth 2.0** (NetSuite Authorization Code Grant)
- **Celery + Redis** (background tasks — NetSuite reference sync, subscription sync, company purge)
- **WhiteNoise** (static files)
- **django-cors-headers** (CORS)
- **python-decouple** (env management)
- **dj-database-url** (database URL parsing)
- **cryptography** (Fernet field-level encryption)

### Frontend
- **React 19**
- **Vite 8**
- **React Router 7**
- **Axios** (with interceptors for token refresh)
- **Tailwind CSS 4** (`@tailwindcss/vite` + `@tailwindcss/postcss`)
- **Recharts** (BI dashboards)
- **oxlint** (linting)

### AI Providers
- **OpenAI** (`gpt-4o-mini` by default)
- **Google Gemini** (`gemini-2.5-flash` by default)

### Hosting
| Layer | Host |
|-------|------|
| Backend | [Render](https://render.com) |
| Frontend | [Vercel](https://vercel.com) |
| Database | [Neon](https://neon.tech) (PostgreSQL) |
| Redis | Render Key Value |

---

## Project Structure

### Backend (`backend/`)

```
backend/
├── manage.py
├── requirements.txt
├── .env.example                 # Local env template
├── .env.render                  # Render-specific env documentation
│
├── config/                      # Django project config
│   ├── settings/                # Split settings: base / local / production / testing
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── production.py
│   │   ├── testing.py
│   │   ├── database.py
│   │   ├── email.py
│   │   ├── jwt.py
│   │   ├── rest_framework.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   ├── cache.py
│   │   └── ocr.py
│   ├── urls.py
│   ├── wsgi.py                  # Production entry point
│   ├── asgi.py
│   └── celery.py
│
├── accounts/                    # Users, JWT, OTP
├── tenancy/                     # Company, tenant middleware, lifecycle
├── rbac/                        # Roles, permissions
├── audit/                       # Audit log
├── notifications/               # In-app notifications
├── common/                      # Shared utils, email, throttles
├── demo/                        # Demo request workflow
├── invitations/                 # Invitation tokens
├── subscriptions/               # Plans, licensing
├── superadmin/                  # Platform operator portal
├── netsuite/                    # OAuth, token manager, REST + SuiteQL, OCR
│   ├── client.py                # The only file that talks HTTP to NetSuite
│   ├── http.py                  # Centralized timeout / retry / correlation ID
│   ├── errors.py                # Response → typed exception mapping
│   ├── token_manager.py         # Concurrent-safe token refresh
│   ├── oauth.py                 # Authorization URL + signed state
│   ├── services.py              # Orchestration (Views ↔ Repos ↔ Client)
│   └── repositories.py          # Persistence-only
├── ai/                          # Pluggable AI providers
├── ocr/                         # Extraction + mapping + validation
├── invoice/                     # Invoice management
├── dashboard/                   # Dashboard
├── reports/                     # Ad-hoc reports
├── reports_engine/              # Scheduled reports
├── monitoring/                  # Request monitoring, health, errors
├── sync/                        # Sync orchestration (Celery)
├── analytics/                   # Centralized analytics
└── bi/                          # BI dashboards
```

### Frontend (`frontend/`)

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── postcss.config.js
├── vercel.json                  # Vercel deployment config
├── .env.example                 # Local env template
├── .env.render                  # Render static-site env documentation
└── src/
    ├── assets/                  # Static assets
    ├── components/              # Reusable UI components
    │   ├── auth/                # Auth-related components
    │   ├── bi/                  # BI widgets (charts, etc.)
    │   ├── client/              # Client portal components
    │   ├── common/              # Shared (Layout, etc.)
    │   ├── layouts/             # Layout shells (Admin, Client, Public, Auth)
    │   ├── netsuite/            # NetSuite UI components
    │   └── superadmin/          # Super admin components
    ├── constants/               # App-wide constants
    ├── contexts/                # React contexts (auth, etc.)
    ├── hooks/                   # Custom React hooks
    ├── pages/                   # Page-level components
    │   ├── admin/               # Super admin pages
    │   ├── client/              # Client portal pages
    │   ├── invitations/         # Invitation acceptance
    │   └── public/              # Public marketing / demo pages
    ├── routes/                  # Centralized route definitions
    ├── services/                # API service layers
    │   ├── apiClient.js         # Axios instance + token-refresh interceptor
    │   └── *.js                 # Per-module service modules
    └── utils/                   # Helpers, constants, token storage
```

---

## Architecture & Design Principles

### Backend — Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│  View Layer (views.py)                                  │
│  • Authentication, request validation                   │
│  • Response formatting                                  │
│  • Delegates to services                                │
└─────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Service Layer (services.py)                            │
│  • Business logic, orchestration                       │
│  • Coordinates repos + external clients                 │
│  • Transaction boundaries                              │
└─────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Repository Layer (repositories.py)                     │
│  • DB queries only — no business logic                  │
│  • One repo per aggregate root                         │
└─────────────────────────────────────────────────────────┘
```

**Strict rules**
- ❌ No business logic in views
- ❌ No direct ORM calls in services (go through repos)
- ❌ No ORM calls in serializers except read-only convenience
- ✅ Repos own transactions for multi-row writes
- ✅ Services own transactions for cross-aggregate orchestration

### Frontend — Service-Layer Pattern

```
┌────────────────────────────────────────────┐
│  Pages (page-level components)             │
│  • Render UI, handle local state           │
│  • Call service methods                    │
└────────────────────────────────────────────┘
                  ↓
┌────────────────────────────────────────────┐
│  Services (services/*.js)                  │
│  • All API calls                            │
│  • Use unwrap() for consistent response    │
│  • Centralized in one axios instance       │
└────────────────────────────────────────────┘
                  ↓
┌────────────────────────────────────────────┐
│  apiClient.js                              │
│  • Axios instance                          │
│  • Injects Bearer token                    │
│  • Auto-refresh on 401                     │
│  • withCredentials for httpOnly cookies    │
└────────────────────────────────────────────┘
```

**Key abstractions**
- `unwrap(response)` — consistent response handler (`{ success, data, message }` envelope)
- `apiClient` — single axios instance with request + response interceptors
- `ProtectedRoute` — guards authenticated routes
- `AdminRoute` / `RoleRoute` — guards role-restricted routes

### General Principles
- **Thin Views, Thick Services**
- **Service-Oriented Architecture**
- **Repository Pattern**
- **Separation of Concerns**
- **Multi-Tenancy by Design**
- **Encrypted Credentials at Rest** (Fernet)
- **Auditable Lifecycle Events** (append-only)
- **Single Source of Truth** for business calculations
- **Reusable UI Components**
- **No secrets in the frontend**

---

## Authentication & Security

### JWT — Dual-Mode Design

AGSuite uses **both** an `Authorization: Bearer` header **and** httpOnly cookies:

| Mode | When | Why |
|------|------|-----|
| **In-memory access token + Authorization header** (primary) | Cross-origin: Vercel frontend → Render backend | Avoids CORS quirks with cookies across subdomains; in-memory storage means XSS can't persist-steal the token |
| **httpOnly cookies** (fallback) | Same-origin or when in-memory refresh isn't available | Browser attaches automatically, immune to JS-access |

**Refresh strategy** (`apiClient.js`):
- On 401, the first failing request triggers a single refresh
- All other in-flight 401s are queued behind that refresh
- After refresh, queued requests are retried with the new access token
- On refresh failure, all queued requests are rejected and the user is bounced to `/login`

### Security Headers & Cookies

Production (`config/settings/production.py`) enables:
- `SECURE_SSL_REDIRECT = True`
- `SECURE_HSTS_SECONDS = 31536000` (1 year, with subdomains + preload)
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `JWT_AUTH_COOKIE_SAMESITE = "None"` (required for cross-origin cookie auth)
- `JWT_AUTH_COOKIE_SECURE = True`
- `SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"`

### Field-Level Encryption

NetSuite `client_secret`, `access_token`, and `refresh_token` are encrypted at rest using Fernet (`FIELD_ENCRYPTION_KEY`). The key is generated with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **Important:** Rotating this key makes existing encrypted rows unreadable. Treat it as a long-lived secret.

### Throttling

Per-endpoint DRF throttle rates are env-driven:
- `THROTTLE_ANON` (default `100/min`)
- `THROTTLE_USER` (default `1000/min`)
- `THROTTLE_LOGIN_OTP` / `THROTTLE_REGISTER_OTP` (default `5/min`)
- `THROTTLE_AI_CHAT` (default `20/min`)
- `THROTTLE_DASHBOARD` (default `120/min`)
- `THROTTLE_NETSUITE_SYNC` (default `30/min`)
- `THROTTLE_HEALTH_CHECK` (default `60/min`)

---

## Multi-Tenancy Model

Every tenant-scoped model carries a `company_id` FK. The `TenantMiddleware`:

1. Resolves the active company from the authenticated user's session/profile
2. Blocks requests for suspended or soft-deleted companies with a 403
3. Provides the resolved company to downstream views/services via the request

**Rules enforced at the query layer:**
- Repositories always filter by `company_id`
- No service accepts a `company_id` from the user — it derives it from the request user
- Cross-company reads are impossible by construction (admin-only diagnostics go through superadmin endpoints)

---

## Local Development

### Prerequisites
- **Python 3.12**
- **Node.js 20+**
- **Redis** (for Celery background tasks)
- **Git**

### 1. Clone & install

```bash
git clone <your-repo-url> agsuite-erp
cd agsuite-erp
```

### 2. Backend

```bash
cd backend
python -m venv .venv

# Activate the venv:
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Copy and edit env
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY, DATABASE_URL (or leave SQLite), and
# FIELD_ENCRYPTION_KEY. For AI features, set OPENAI_API_KEY or GEMINI_API_KEY.

python manage.py migrate
python manage.py runserver
```

Backend will run at `http://localhost:8000`.

### 3. Frontend

```bash
cd frontend
npm install

# Copy and edit env
cp .env.example .env
# Default points to http://localhost:8000/api/v1 — fine for local dev.

npm run dev
```

Frontend will run at `http://localhost:5173`.

---

## Docker

AGSuite ERP is containerized for local development and deployment preparation using **Docker** and **Docker Compose**.

The Docker environment includes separate services for:

- Django backend
- React/Vite frontend
- PostgreSQL
- Redis
- Celery Worker
- Celery Beat

### Start the complete Docker environment

```bash
docker compose up -d --build
```

### Check running containers

```bash
docker compose ps
```

### Stop the Docker environment

```bash
docker compose down
```

### The application is available at:

```text
http://localhost
```

The Docker setup provides isolated and reproducible local services while keeping the development environment consistent across machines.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Django secret key |
| `DEBUG` | ✅ | `True` for local, `False` for production |
| `ALLOWED_HOSTS` | ✅ | Comma-separated host list |
| `DATABASE_URL` | ✅ | `postgresql://...` (Neon) for prod, leave blank for local SQLite |
| `FIELD_ENCRYPTION_KEY` | ✅ for NetSuite | Fernet key for NetSuite credential encryption |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | ❌ | Default `15` |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | ❌ | Default `7` |
| `CORS_ALLOWED_ORIGINS` | ✅ | Comma-separated frontend origins |
| `CSRF_TRUSTED_ORIGINS` | ✅ | Comma-separated trusted origins |
| `FRONTEND_URL` | ✅ | Used to build OAuth callback redirects |
| `NETSUITE_REDIRECT_URI` | ✅ for NetSuite | Must exactly match the Integration record |
| `OPENAI_API_KEY` | ❌ | If absent, AI gracefully returns "not configured" |
| `OPENAI_MODEL` | ❌ | Default `gpt-4o-mini` |
| `GEMINI_API_KEY` | ❌ | For Gemini provider |
| `GEMINI_MODEL` | ❌ | Default `gemini-2.5-flash` |
| `AI_PROVIDER` | ❌ | `openai` or `gemini` (default `gemini`) |
| `BREVO_API_KEY` | ❌ | Required on Render (SMTP ports are blocked there) |
| `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_PORT` / `EMAIL_USE_TLS` | ❌ | SMTP fallback (Gmail etc.) |
| `DEFAULT_FROM_EMAIL` / `DEFAULT_FROM_NAME` | ❌ | Outgoing mail identity |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | ❌ | Default `redis://127.0.0.1:6379/0` |
| `THROTTLE_*` | ❌ | Per-endpoint rate limits |

> For Render, all of the above are configured via the dashboard (not via `.env` files). `backend/.env.render` is a documentation-only file describing the production values.

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | ✅ | e.g. `https://agsuite-erp-backend.onrender.com/api/v1` for production, `http://localhost:8000/api/v1` for local |

---

## Deployment

### Backend — Render

The backend runs as a **Web Service** on Render using `gunicorn`:

- **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- **Start command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- **Settings module:** `config.settings.production` (set via `DJANGO_SETTINGS_MODULE` env var)

> SMTP ports are blocked on Render's free tier. Use the **Brevo HTTP API** (`BREVO_API_KEY`) for outbound mail.

### Frontend — Vercel

The frontend is deployed as a static site:

- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Env var:** `VITE_API_BASE_URL=https://agsuite-erp-backend.onrender.com/api/v1`

### Database — Neon

- Provision a free PostgreSQL instance on [neon.tech](https://neon.tech)
- Copy the connection string into Render's `DATABASE_URL`
- Append `?sslmode=require` if not present

### Periodic Tasks

- `purge_expired_deleted_companies` — runs daily
- `sync_company_subscription_statuses` — runs daily
- `sync_netsuite_reference_data` — runs on each new NetSuite OAuth callback

Celery Beat requires a separate long-running Background Worker service on Render when background job processing is enabled in production.

---

## Testing

### Backend

```bash
cd backend
python manage.py test
```

> Tests use an in-memory SQLite database (see `config/settings/testing.py`).

### Frontend

```bash
cd frontend
npm run build       # Production build (catches type/import errors)
npm run lint        # oxlint
```

### Manual smoke tests

- **Auth flow:** register → OTP verify → login → `/auth/me/`
- **Multi-tenancy:** log in as two different companies, verify zero data overlap
- **NetSuite:** create connection → OAuth → test connection → fetch a record
- **OCR:** upload invoice → field mapping → validate → post vendor bill

---

## Documentation

| File | Description |
|------|-------------|
| `backend/docs/` | Per-sprint implementation notes (Sprint 0 Phase 02/03, Async Processing) |
| `frontend/ROUTING_AUDIT_REPORT.md` | Full route tree + layout audit |
| `backend/.env.example` | All backend env variables with inline comments |
| `backend/.env.render` | Render-specific env documentation |
| `frontend/.env.example` | Frontend env template |
| `frontend/.env.render` | Render static-site env documentation |

---

## Development Status

### Implemented
- ✅ Custom User + JWT + Email OTP authentication
- ✅ Multi-tenancy with company lifecycle
- ✅ Demo request → company conversion flow
- ✅ Invitation system with UUID tokens
- ✅ Subscription plans, licensing, per-module usage
- ✅ NetSuite OAuth + connection management + employee assignment
- ✅ NetSuite REST Record API + SuiteQL
- ✅ NetSuite token manager with concurrent-safe refresh
- ✅ Connection health tracking + test connection
- ✅ OCR ingestion + field mapping + NetSuite validation
- ✅ Vendor Bill posting to NetSuite
- ✅ AI assistant (OpenAI + Gemini providers)
- ✅ Dashboard, BI dashboards, ad-hoc reports
- ✅ Scheduled reports engine
- ✅ Audit logging across critical actions
- ✅ Super admin portal
- ✅ Client portal
- ✅ Monitoring + health endpoint

### Active Work
- 🔄 Production deployment hardening
- 🔄 Production background job processing on Render (worker deployment deferred until required)
- 🔄 Connection reconnect flow when refresh tokens expire

---

## Design Principles (recap)

- Thin Views, Thick Services
- Service-Oriented Architecture
- Repository Pattern
- Separation of Concerns
- Multi-Tenancy by Design
- Encrypted Credentials at Rest
- Auditable Lifecycle Events
- Single Source of Truth for Business Calculations
- Reusable UI Components

---

## Long-Term Vision

AGSuite ERP aims to become a complete **ERP aggregation platform** — one dashboard, every ERP:

```
                User
                  │
                  ▼
            AGSuite ERP
                  │
   ┌──────┬──────┬──────┬──────┬──────┬──────┐
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
NetSuite SAP   Zoho   Tally  QuickBooks  MS Dynamics  ...
```

**One subscription. Every ERP. One unified dashboard.**

---

## License

This project is under active development. All rights reserved.
