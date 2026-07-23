# Changelog

All notable changes to ERP Pulse will be documented in this file.

This project follows a milestone-based changelog instead of release versioning during development.

---

# [Unreleased]

Nothing shipped yet beyond Milestone 6 below. Open items are tracked under
"Next Task" at the bottom of this file and in the Roadmap section of
README.md.

---

# Milestone 6 - Connection Health, Audit Trail, Manual Sync Manager & Reporting

Status: ✅ Completed (backend) / 🟡 Partial (frontend not yet surfaced)

## Added

### NetSuite Client Split

- `netsuite/client.py` refactored into three focused pieces:
  - `http.py` — generic HTTP sending: centralized timeout, correlation-ID
    header, retry-with-backoff on 429/5xx for idempotent calls only
    (never the OAuth token endpoint — an authorization code is single-use).
  - `errors.py` — centralized mapping of NetSuite HTTP responses to typed
    exceptions (previously duplicated three times across `_get`/`_post`/
    `_post_token_request`).
  - `pagination.py` — helper to walk NetSuite REST collection responses
    (`hasMore`/`offset`) across all pages. Not yet wired into existing
    endpoints (would change their public response shape); first consumer
    is available for the Sync Manager.
- All public `NetSuiteAuthClient` method signatures unchanged — this was
  an internal restructuring, not an API change.

### Connection Health & Audit Trail

- `NetSuiteConnection` gained `last_used_at` (separate from
  `last_synced_at` — broader, updated on any successful live API call,
  not just sync runs) and a computed `health` property (`healthy` /
  `degraded` / `unhealthy` / `disconnected`, derived from `status` +
  `consecutive_failures` so there's one source of truth).
- New `NetSuiteConnectionAuditLog` model — one row per lifecycle event
  (created, renamed, switched active, deleted, OAuth completed). FK is
  `SET_NULL` on connection delete so a deleted connection's audit trail
  survives the deletion.
- Wired into `NetSuiteConnectionService` at every lifecycle point.
- Migration: `netsuite/migrations/0005_netsuiteconnection_last_used_at_and_more.py`.

### Sync Manager (new `sync` app)

- `SyncRun` (one per sync execution) + `SyncStage` (one per entity type
  within a run) — lets a partially-failed run retry only its failed
  stages instead of re-running everything.
- `SyncManager` service: pure orchestration, zero NetSuite HTTP logic
  (delegates to the existing `NetSuiteDataService`).
- Endpoints: `GET/POST /api/v1/sync/runs/`, `GET /api/v1/sync/runs/{id}/`,
  `POST /api/v1/sync/runs/{id}/retry/`.
- Concurrent-trigger guard — rejects a new sync while one is already
  pending/running for that connection.
- Incremental sync via `lastModifiedDate` filter, using the connection's
  `last_synced_at` as the watermark (⚠️ not yet confirmed against a live
  NetSuite sandbox — same caveat as other unverified SuiteQL/REST filter
  shapes already flagged elsewhere in the codebase).
- **Scope note:** manual/on-demand sync only. Scheduled/background sync
  needs a task queue (Celery + Redis), not in the stack yet — explicitly
  deferred to Milestone 7, not attempted here.

### Reports (new `reports` app)

- `GET /api/v1/reports/sales-trend/?months=N` — month-bucketed sales
  order + invoice revenue totals via SuiteQL, reusing the same
  `foreigntotal`/`type` field conventions already established in
  `dashboard/services.py`.
- Frontend: `ReportsPage` rebuilt on real data — `recharts` bar chart
  (sales orders vs. invoice revenue by month), 3/6/12-month toggle,
  loading/error/empty states. Dummy data (`reportsList`) removed.

### Login/Activity History

- New `LoginActivity` model — one row per successful login (IP address,
  user agent, timestamp).
- `VerifyLoginOTPView` now records a `LoginActivity` row right after JWT
  issuance.
- `GET /api/v1/auth/login-history/` — most recent logins first.
- Frontend: `HistoryPage` rebuilt on real data — real login timestamps/
  IP/user-agent list, loading/error/empty states. Dummy data
  (`historyTimeline`) removed.
- Resolves the "Missing migration for accounts.LoginActivity" item from
  the previous changelog entry — migration exists and is applied.

## Fixed

- **`resend_login_otp` was completely broken** — three compounding bugs,
  zero test coverage to catch any of them:
  1. The method was de-indented out of the `AuthenticationService` class
     entirely (module-level function, not a class method).
  2. It referenced `self.otp_repository`, which doesn't exist —
     `AuthenticationService` only exposes `otp_service` (which wraps
     its own repository).
  3. The view called `self.authentication_service` (undefined on the
     view) instead of the module-level `authentication_service`
     singleton every other view in the file correctly uses.
  - Added 6 tests (service + view level) — this endpoint had none before.
- **`reports` app was mounted in `config/urls.py` but missing from
  `INSTALLED_APPS`** — fixed.
- **`netsuite/tests.py` rewritten** — was importing `NetSuiteConnectView`,
  a view removed during the Milestone 4 multi-connection refactor,
  which silently broke the entire test module's import (35 tests never
  ran). Rewritten against the current multi-connection architecture —
  now 64 tests, covering the connection CRUD lifecycle that previously
  had zero coverage.
- **`requirements.txt` encoding corruption** — fixed twice; root cause
  is `pip freeze` piped through Windows PowerShell's `Out-File`, which
  defaults to UTF-16. Now plain UTF-8/ASCII.
- **`.env.example` was out of sync with `settings.py`** — documented the
  old split `DATABASE_NAME/USER/PASSWORD/HOST/PORT` vars after the code
  had already moved to a single `DATABASE_URL` (via `dj-database-url`).
- Removed `backend/staticfiles/` (160 files, `collectstatic` output) from
  git tracking — was accidentally committed; now regenerated at deploy
  time and gitignored.

## Known gaps (carried forward, not fixed this round)

- `netsuite/tests.py`'s `NetSuiteAuthClientTests` mock `netsuite.client.requests`
  directly — broken by the HTTP client split above (client.py no longer
  imports `requests` directly). 10 tests currently fail for this reason;
  needs mock retargeting to `netsuite.http.send`. Deliberately deferred —
  test coverage work was explicitly paused this round to prioritize
  shipping the features above.
- No tests written yet for the Sync Manager, Connection Audit Trail, or
  Login History endpoints.
- Frontend does not yet surface connection health, the audit trail, or
  any Sync Manager UI (trigger/history/retry) — backend-only this round.

---

# Milestone 5 - Operational Monitoring, Connection Management UI & Deployment

Status: ✅ Completed

## Added

### Monitoring

- New `monitoring` app covering four operational areas:
  - NetSuite connection health fields (`last_synced_at`, `last_error`,
    `consecutive_failures`), auto-updated on every data fetch/token
    refresh; auto-flips to `error` status after 3 consecutive failures.
  - Application error monitoring — unhandled exceptions persisted to
    `ErrorLog` via the central DRF exception handler.
  - `GET /api/v1/monitoring/health/` — public health check (DB
    connectivity, SMTP config, field-encryption key), for Render/uptime
    pingers.
  - `RequestMonitoringMiddleware` + `RequestLog` — logs every
    `/api/v1/*` request; `GET /api/v1/monitoring/api-usage/` (staff-only)
    aggregates volume, error rate, throttling, and latency by endpoint.
- Frontend `/system-health` page (admin sections degrade gracefully for
  non-staff users).
- 9 new tests for health check, permissions, and middleware behavior.

### Frontend

- Persistent `Footer` component on every page.
- Connect NetSuite page: **Rename Connection** (inline edit) — completes
  frontend connection management (List, Add, Rename, Delete, Switch
  Active, OAuth Redirect Handling).

### Backend

- SMTP email backend configured for OTP delivery via Gmail.
- Fixed a typo in `EMAIL_BACKEND` (`smt` → `smtp`) that would have
  broken OTP delivery in production.

### Deployment

- Live on Render (backend) + Vercel (frontend) + Neon (PostgreSQL).
- README updated with Live Demo and Deployment sections.

## Fixed

- Fixed a typo in a `netsuite` test helper (`refresh-token` →
  `refresh_token`) that was causing 16 tests to fail.

---

# Milestone 4 - Multi Account NetSuite Refactor

Status: ✅ Completed

## Added

### NetSuiteConnection Model

- Changed relationship from OneToOneField to ForeignKey.
- Added support for multiple NetSuite connections per user.
- Added `client_name`, `environment`, `client_id`, `client_secret`, `status`, `is_active`.
- Added uniqueness constraint on `(user, netsuite_account_id)`.
- OAuth token fields nullable until OAuth callback completes.

### Repository Layer

Added `create()`, `list_by_user()`, `get_by_user()`, `get_by_id()`,
`rename()`, `delete()`, `switch_active_connection()`, `complete_oauth()`,
`update_tokens()`.

### OAuth

State changed from `user_id` to `user_id:connection_id`. Authorization
URL now uses credentials stored per-connection instead of global Django
settings.

### NetSuite Client

Refactored to become connection-aware — every request now uses the
currently selected connection's credentials instead of global settings.

### Services

`ConnectionService`: Create, OAuth Callback, Rename, Delete, Switch
Active. `DataService`: automatic token refresh, authenticated client
creation, record fetching, SuiteQL.

### URLs

```
GET    /connections/
POST   /connections/
PATCH  /connections/{id}/
DELETE /connections/{id}/
POST   /connections/{id}/switch/
```

### Architecture

```
User
    │
    ├── Connection A
    ├── Connection B
    └── Connection C
```

Only one connection remains active.

## Changed

- OAuth credentials no longer loaded globally.
- Token refresh is connection-specific.
- Services create clients dynamically.
- Repository owns all persistence. Views remain thin.

---

# Milestone 3 - Generic NetSuite Data Layer

Status: ✅ Completed

Generic `get_records()`, `get_record()`, `execute_suiteql()`. Added
support for Customers, Employees, Vendors, Items, Sales Orders,
Purchase Orders, Invoices. Automatic token refresh before API requests.

---

# Milestone 2 - OAuth Integration

Status: ✅ Completed

Authorization Code Flow: authorization URL generation, state signing,
callback validation, token exchange, token refresh.

---

# Milestone 1 - Initial NetSuite Integration

Status: ✅ Completed

Initial project structure — Models, Repository, Client, Services, Views,
OAuth Module. First successful NetSuite authentication and data
retrieval.

---

# Future Milestones

## Milestone 7 - Background Synchronization

- Celery + Redis
- Scheduled sync (build on top of the manual Sync Manager from
  Milestone 6 — `SyncRun.trigger='scheduled'` already exists as a
  forward-compatible choice, just not triggerable yet)
- Sync logs UI

## Milestone 8 - ERP Abstraction Layer

Support multiple ERP providers (SAP, Zoho, Tally, Dynamics, QuickBooks)
without changing the core architecture.

---

# Long-Term Vision

Transform ERP Pulse from a NetSuite integration into a complete ERP
aggregation platform capable of connecting multiple ERP providers
through a unified architecture.

---

# Current Estimated Completion

| Area | Estimate | Notes |
|------|----------|-------|
| Backend (features in current scope) | ~90% | Excludes scheduled sync (Milestone 7, needs Celery/Redis — not started) |
| Backend test coverage | ~75% | Sync Manager, audit trail, login history untested; NetSuite client tests need mock retargeting |
| Frontend | ~65% | Core pages + Reports/History done; connection health/audit trail/sync UI not yet surfaced |
| Overall project | ~70% | Up from 45% at the end of Milestone 4 |

These are rough estimates, not a formal metric — treat as directional.

---

# Next Task

In priority order:

1. **Retarget the 10 broken `netsuite/tests.py` mocks** to `netsuite.http.send`
   instead of `netsuite.client.requests` — quick, unblocks a clean full
   test-suite run.
2. **Write tests for what shipped untested this round**: Sync Manager,
   Connection Audit Trail, Login History.
3. **Surface the new backend data in the frontend**: connection
   health/audit trail on the Connect NetSuite page, a Sync Manager UI
   (trigger a run, view history, retry failed stages).
4. **Verify the SuiteQL/REST assumptions flagged as unconfirmed** against
   a live NetSuite sandbox — the sales-trend query, the incremental-sync
   `lastModifiedDate` filter, and the earlier `foreigntotal`/`type`
   fields all carry a "not yet confirmed against a live sandbox" caveat.
5. Once 1-4 are solid: start Milestone 7 (Celery + Redis, scheduled sync).
