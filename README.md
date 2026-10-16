# AGSuite ERP

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6.x-green)
![DRF](https://img.shields.io/badge/DRF-REST-red)
![React](https://img.shields.io/badge/React-19-61dafb)
![Vite](https://img.shields.io/badge/Vite-8-646cff)
![Status](https://img.shields.io/badge/Status-Active%20Development-yellow)
![License](https://img.shields.io/badge/License-Private-lightgrey)

**AGSuite ERP** is a multi-tenant SaaS platform built with **Django REST Framework** and
**React (Vite)**. A company signs up, connects its **Oracle NetSuite** account, and uses
AI-assisted **OCR / data extraction** to turn invoices and other documents into validated
NetSuite records (for example Vendor Bills), under a subscription managed by a platform
operator (Super Admin).

---

## Live Deployment (Zoho Catalyst)

| Layer | URL | Host |
|-------|-----|------|
| Frontend | https://agsuiteerp-60086947932.catalystserverless.in | Catalyst Web Client Hosting |
| Backend API | https://agsuiteerp-50046369262.catalystappsail.in | Catalyst AppSail |
| Database | PostgreSQL | Supabase |
| Redis | Optional | The app runs without it |

> **Keep these in sync.** When the production URLs change, update the backend environment
> variables `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`
> and `NETSUITE_REDIRECT_URI`, and the frontend variable `VITE_API_BASE_URL`
> (see [Production configuration](#production-configuration-catalyst)).

---

## Table of Contents

- [Platform Architecture](#platform-architecture)
- [Backend Modules](#backend-modules)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Background Processing & Resilience](#background-processing--resilience)
- [Project Structure](#project-structure)
- [Authentication & Security](#authentication--security)
- [Multi-Tenancy Model](#multi-tenancy-model)
- [Local Development](#local-development)
- [Docker](#docker)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)
- [Documentation](#documentation)
- [Development Status](#development-status)
- [License](#license)

---

## Platform Architecture

```
AGSuite Platform
    │
    ▼
Super Admin (platform operator)
    │
    ▼
Company (tenant)
    │
    ├── Company Admin
    │     ├── Subscription / plan
    │     ├── Employees
    │     ├── NetSuite connections
    │     └── AI configuration + OCR extraction templates
    │
    └── Employees
          └── Use only the NetSuite connections assigned to them
              (credentials are never exposed)
```

- **Super Admin** manages companies, plans, employees and platform settings.
- **Company Admin** manages that company's admins, employees, invitations, connections and navigation.
- **Company (tenant)** owns all of its data; every tenant-scoped query is filtered by company.
- **Employees** work with the connections an admin assigned; Company Admins have company-wide access and
  do not require a connection assignment. Secrets stay server-side.

---

## Backend Modules

| App | Responsibility |
|-----|----------------|
| `accounts` | Custom user, JWT auth, email OTP (login / profile / password reset), login history |
| `tenancy` | `Company` model, `TenantMiddleware`, company lifecycle (suspend / reactivate / soft-delete / purge) |
| `rbac` | Roles |
| `audit` | Append-only audit log for lifecycle events |
| `invitations` | Single-use invitation tokens with expiry, public accept flow |
| `subscriptions` | Plan assignment and subscription lifecycle for companies |
| `superadmin` | Platform portal API: companies, plans, employees, settings |
| `netsuite` | OAuth 2.0 connections, token manager, REST Record API + SuiteQL, field catalogue, custom fields, OCR validation / posting, **batch validate / post jobs** |
| `ocr` | AI extraction engine, extraction templates, batches / uploads / documents with version history, per-company AI configuration, file storage, background execution |
| `navigation` | Admin-configurable dynamic navigation tabs |
| `transactions` | Company transaction records |
| `dashboard` | Company dashboard data |
| `monitoring` | Request log, error log, API usage, health and readiness endpoints |
| `common` | Shared utilities: email (SMTP + Brevo), field encryption, throttles, optional-Redis helpers, scheduled tasks |
| `core` | Shared base model |

---

## Key Features

### Authentication
- JWT access / refresh tokens, accepted from the `Authorization: Bearer` header **or** httpOnly cookies
- Email OTP for login, profile changes and password reset
- Login history per user
- Automatic access-token refresh in the frontend with queued retry of concurrent 401s

### Multi-tenancy
- `TenantMiddleware` resolves the active company for each authenticated request
- Company lifecycle: active, suspended, soft-deleted, purged after a retention period
- Requests for suspended or deleted companies are rejected

### Invitations and subscriptions
- Super Admin and Company Admin use the same invitation flow for their respective users
- UUID invitation tokens with expiry, resend and a public acceptance page; pending or expired
  invitations leave the user inactive until password setup is completed
- Plans and company subscriptions managed from the Super Admin portal; client-side subscription page

### NetSuite integration
- OAuth 2.0 Authorization Code flow; several connections per company; employee assignment
- Encrypted credentials and tokens at rest (Fernet)
- Concurrency-safe token refresh, connection health tracking and test connection
- REST Record API and SuiteQL; field catalogue and custom fields
- Validation of extracted documents against NetSuite reference data and **Vendor Bill posting**
- **Batch validate / post** runs as a background job with live progress; it resumes after a crash and
  never re-posts documents that already finished
- A successful Vendor Bill post returns its NetSuite internal ID and a direct **View in NetSuite** link.
  The browser URL is generated server-side from the connected NetSuite account ID and record ID.

### OCR and data extraction
- Upload a single file, several files, or a ZIP; PDFs and images are normalised into page images
- **Dynamic extraction templates** per company: choose standard fields, add custom fields with their
  own AI instruction and header / line scope
- AI providers: **Google Gemini**, **OpenAI** and **Anthropic**, configured per company
  (API key stored encrypted); Gemini calls are rate-limited (concurrency + requests per minute)
- Review screen: extracted data is a draft until a user reviews and saves it
- Save & Validate calculates line-item totals and taxes from the reviewed data before NetSuite posting
- Repeated unmatched line items with identical line-level data are grouped for validation diagnostics,
  so users receive one resolution instead of duplicate messages and AI diagnostics use fewer tokens
- Validation errors and AI diagnostics are stored with the document version. History reopens the
  workflow at its saved state: not validated, validated, or posted (including the NetSuite record link)
- History of batches, documents and document versions; every history row has a permanent sequential
  history number that is never reused after deletion
- Failures carry a stable `failure_code` and a user-safe message; technical detail goes to the logs

### Platform
- Admin-configurable navigation tabs and categories
- Navigation changes are reflected in the active client session without requiring a browser refresh
- Request monitoring, error log, API usage, system-health page
- Super Admin portal and client portal in the same React app; a deleted company can be permanently
  removed from the Super Admin's soft-deleted list when immediate removal is required

---

## Tech Stack

**Backend**: Python 3.12, Django 6.x, Django REST Framework, SimpleJWT, PostgreSQL
(`psycopg2`), WhiteNoise, django-cors-headers, python-decouple, dj-database-url,
`cryptography` (Fernet), Gunicorn. OCR: PyMuPDF, OpenCV (headless), Pillow, `google-genai`.
Optional: Celery + Redis.

**Frontend**: React 19, Vite 8, React Router 7, Axios, Tailwind CSS 4, oxlint.

**Hosting (production)**: Zoho Catalyst (AppSail for the API, Web Client Hosting for the UI),
Supabase PostgreSQL. Also runs on Docker, AWS, GCP, Render or a VPS - see
[DEPLOY_ANYWHERE.md](DEPLOY_ANYWHERE.md).

---

## Background Processing & Resilience

The backend is designed to run with **only PostgreSQL**. Redis, Celery and a persistent local disk
are optional accelerators; when one is missing, a throttled one-line warning is logged and the app
continues on a PostgreSQL fallback.

| Concern | With Redis / Celery | Without |
|---------|---------------------|---------|
| OCR result cache, extraction lock, Gemini rate limiter | Redis | PostgreSQL (`OCRGeminiLease`, DB cache) |
| OCR and NetSuite batch jobs | Celery worker | In-process background threads, or a dedicated `run_ocr_worker` process |
| Daily housekeeping (purge deleted companies, sync subscription status) | Celery beat | `manage.py run_scheduled_tasks`, or `run_ocr_worker` (runs it daily) |
| Uploaded files | local disk | `OCR_STORAGE_BACKEND=db` (PostgreSQL) or `s3` |

**How a job runs** (`OCR_EXECUTION_MODE`, default `auto`):

1. Celery is used only if a broker **and** a live worker answer a ping; otherwise
2. background threads in the web process run the job; `external` mode leaves jobs for
   `manage.py run_ocr_worker`.

**Job state lives in PostgreSQL** (status + lease). A running job keeps renewing its lease; if its
process dies, the job is re-queued automatically. Recovery is triggered by the frontend's status
polling, so no scheduler is needed. Duplicate dispatch is harmless because each job is claimed
atomically.

**Single-file OCR** is answered synchronously when it finishes within
`OCR_SINGLE_TIME_BUDGET_SECONDS` (180 s, or 20 s on Catalyst, which ends requests after 30 s).
Otherwise the request returns `202`, the file continues in the background and the UI polls the batch.

**Cache isolation**: cache and lock keys include the company and the company's AI provider/model,
so cached extractions are never shared between tenants.

---

## Project Structure

```
.
├── backend/
│   ├── manage.py, main.py (Catalyst entry), gunicorn.conf.py, app-config.json
│   ├── config/            # settings split by concern (base, database, ocr, security, ...), urls, celery
│   ├── accounts/  tenancy/  rbac/  audit/  invitations/  subscriptions/  superadmin/
│   ├── netsuite/          # client, oauth, token manager, services, batch jobs (jobs.py)
│   ├── ocr/               # views, tasks (engine), execution, leases, storage, error_taxonomy, ai/
│   ├── navigation/  transactions/  dashboard/  monitoring/  common/  core/
│   └── requirements.txt
├── frontend/
│   └── src/ { pages/{auth,client,superadmin,public,invitations}, components, services, contexts,
│              hooks, layouts, routes, utils }
├── catalyst.json          # AppSail (backend) + client (frontend/dist) deployment
├── Dockerfile.backend, Dockerfile.frontend, docker-compose.yml, nginx.conf
├── DEPLOY.md, DEPLOY_ANYWHERE.md
└── env.docker.example, env.postgres.example
```

---

## Authentication & Security

- **Tokens**: the frontend keeps the access token in memory and sends it as a Bearer header; the
  backend also accepts httpOnly `access_token` / `refresh_token` cookies. Lifetimes come from
  `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` / `JWT_REFRESH_TOKEN_LIFETIME_DAYS`.
- **Production settings** enable HSTS (1 year, subdomains, preload), secure session / CSRF cookies,
  a strict referrer policy and `SECURE_SSL_REDIRECT` (overridable by env).
- **Field-level encryption**: NetSuite secrets and AI API keys are encrypted with Fernet using
  `FIELD_ENCRYPTION_KEY`. Rotating the key makes existing encrypted rows unreadable.
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- **Throttling** is env-driven (`THROTTLE_ANON`, `THROTTLE_USER`, `THROTTLE_LOGIN_OTP`,
  `THROTTLE_REGISTER_OTP`, `THROTTLE_DASHBOARD`, `THROTTLE_NETSUITE_SYNC`, `THROTTLE_HEALTH_CHECK`).
- **Error hygiene**: API responses and the public health endpoint do not expose database or
  internal exception details; those go to the logs only.

---

## Multi-Tenancy Model

Every tenant-scoped model carries a company reference. `TenantMiddleware` resolves the company from
the authenticated user and blocks requests for suspended or deleted companies. Services derive the
company from the request user and never trust a company id sent by the client.

---

## Local Development

**Prerequisites**: Python 3.12, Node.js 20+, Git. PostgreSQL is recommended (some migrations expect it).
Redis is **not** required.

### Backend (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # set SECRET_KEY, DATABASE_URL (or LOCAL_DB_NAME), FIELD_ENCRYPTION_KEY
python manage.py migrate
python manage.py runserver
```

macOS / Linux: `python -m venv .venv && source .venv/bin/activate`, then the same commands (`cp` instead of `copy`).
The API runs at `http://localhost:8000`.

OCR jobs run in background threads of the dev server. To run them in a separate process instead,
set `OCR_EXECUTION_MODE=external` and start `python manage.py run_ocr_worker` in a second terminal.

### Frontend

```powershell
cd frontend
npm install
copy .env.example .env      # VITE_API_BASE_URL, e.g. http://localhost:8000/api/v1
npm run dev
```

The UI runs at `http://localhost:5173`. `npm run build` produces `frontend/dist`.

---

## Docker

```bash
cp env.docker.example .env.docker        # then fill in the values
docker compose up -d --build              # PostgreSQL + backend + frontend (minimal)
```

| Command | What it adds |
|---------|--------------|
| `docker compose --profile full up -d` | Redis, Celery worker and beat (uncomment the Redis lines in `.env.docker` first) |
| `docker compose --profile worker up -d` | PostgreSQL-queue worker (`run_ocr_worker`); set `OCR_EXECUTION_MODE=external` |

Stop with `docker compose down`; rebuild with `docker compose up -d --build`.

---

## Environment Variables

Full templates: `backend/.env.example`, `frontend/.env.example`, `env.docker.example`,
`env.postgres.example`.

**Required (backend)**

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret |
| `DATABASE_URL` | PostgreSQL connection string |
| `FIELD_ENCRYPTION_KEY` | Fernet key for encrypted fields |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` | Host and origin configuration |
| `NETSUITE_REDIRECT_URI` | OAuth redirect; the backend route `/api/v1/netsuite/callback/` |
| `EMAIL_*` / `BREVO_API_KEY` | Email delivery (OTP, invitations) |

**Optional (all have safe defaults)**: `REDIS_URL` / `REDIS_ENABLED`, `CELERY_BROKER_URL`,
`OCR_EXECUTION_MODE`, `OCR_BACKGROUND_WORKERS`, `OCR_STORAGE_BACKEND`, `OCR_S3_*`,
`OCR_SINGLE_TIME_BUDGET_SECONDS`, `OCR_SINGLE_ASYNC`, `OCR_MULTIPLE_ENABLED`, `OCR_JOB_*`,
`GUNICORN_WORKERS` / `GUNICORN_THREADS` / `GUNICORN_TIMEOUT`. The complete table is in
[DEPLOY_ANYWHERE.md](DEPLOY_ANYWHERE.md).

**Frontend**: `VITE_API_BASE_URL` (the production build falls back to the Catalyst backend URL).

---

## Deployment

### Production configuration (Catalyst)

Backend (AppSail `agsuiteerp`, source `backend`, command `python3 main.py`, Python 3.12, 2048 MB):

```env
ALLOWED_HOSTS=agsuiteerp-50046369262.catalystappsail.in
CORS_ALLOWED_ORIGINS=https://agsuiteerp-60086947932.catalystserverless.in
CSRF_TRUSTED_ORIGINS=https://agsuiteerp-60086947932.catalystserverless.in,https://agsuiteerp-50046369262.catalystappsail.in
FRONTEND_URL=https://agsuiteerp-60086947932.catalystserverless.in
NETSUITE_REDIRECT_URI=https://agsuiteerp-50046369262.catalystappsail.in/api/v1/netsuite/callback/

# Catalyst has no persistent disk and no worker process:
OCR_STORAGE_BACKEND=db          # or s3
OCR_EXECUTION_MODE=thread
```

Frontend build: set `VITE_API_BASE_URL=https://agsuiteerp-50046369262.catalystappsail.in/api/v1`,
then run `npm run build` and deploy `frontend/dist`.

Catalyst ends every request after **30 seconds**. Long OCR continues in the background and the UI polls
for the result. A background thread only runs while the AppSail instance is alive; if it is stopped, the
next status poll resumes the job.

Register the same `NETSUITE_REDIRECT_URI` in the NetSuite integration record.

### Other hosts

Docker, AWS, GCP Cloud Run, Render and VPS setups, with the processes and environment each needs, are in
[DEPLOY_ANYWHERE.md](DEPLOY_ANYWHERE.md). Database and general deployment notes are in [DEPLOY.md](DEPLOY.md).

After every deploy run `python manage.py migrate`.

---

## Operations

| Endpoint | Purpose |
|----------|---------|
| `GET /` and `GET /health/` | Liveness |
| `GET /api/v1/monitoring/health/` | Database, email, encryption, **storage**, **redis** and **ocr_execution** checks. Redis / Celery are reported but never degrade the status |
| `GET /api/v1/monitoring/readiness/` | Readiness |

| Command | Purpose |
|---------|---------|
| `python manage.py run_ocr_worker [--once] [--interval N]` | PostgreSQL-queue worker for OCR and NetSuite batch jobs; also runs the daily housekeeping |
| `python manage.py run_scheduled_tasks` | Daily housekeeping without Celery beat; safe to run from any scheduler |

**Logging policy**: expected conditions (Redis down, quota exhausted, a document NetSuite rejected) produce
a one-line warning with the reason. A traceback is written only for genuinely unexpected errors.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `400 DisallowedHost` / bad request on the API | `ALLOWED_HOSTS` does not include the deployed API host |
| Browser CORS or CSRF errors | `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` missing the frontend origin |
| Frontend loads but calls the wrong API | `VITE_API_BASE_URL` not set for the build |
| `Redis unavailable ... continuing without Redis` | Informational: PostgreSQL fallbacks are in use |
| `Celery is not available (...)` | Informational: jobs run in background threads |
| `Unknown command: run_ocr_worker` | The command file must be at `backend/ocr/management/commands/run_ocr_worker.py` |
| OCR file "no longer available on the server" | Local disk is not persistent; use `OCR_STORAGE_BACKEND=db` or `s3` |
| Job stays "processing" on Catalyst | Instance was stopped; open the batch again, polling resumes it |

---

## Testing

Run backend checks and tests from `backend/`:

```powershell
python manage.py check
python manage.py test
```

Run frontend checks from `frontend/`:

```powershell
npm run lint
npm run build
```

Smoke test after a deploy: check `/api/v1/monitoring/health/`, complete login OTP verification, invite and
accept a company user, upload one file, upload several files, validate them, and post one validated Vendor
Bill to NetSuite. Confirm that its internal ID and **View in NetSuite** link are returned.

---

## Documentation

- [DEPLOY.md](DEPLOY.md) - general deployment notes
- [DEPLOY_ANYWHERE.md](DEPLOY_ANYWHERE.md) - host-by-host guide and the full list of optional variables

---

## Development Status

**Implemented**: custom user + JWT + email OTP; multi-tenancy with company lifecycle; invitations;
subscriptions and plans; Super Admin and client portals; NetSuite OAuth, connections, REST + SuiteQL,
field catalogue, custom fields; OCR extraction with templates, history and versions; saved validation and
AI diagnostics; Vendor Bill posting with NetSuite record links; NetSuite batch jobs; optional Redis / Celery
with PostgreSQL fallbacks; storage backends (local / PostgreSQL / S3); monitoring and health.

**Active work**: production hardening on Catalyst, a new automated test suite, connection reconnect flow
when refresh tokens expire.

---

## License

This project is under active development. All rights reserved.
