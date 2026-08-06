# ERP Pulse (AGSuite)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6.x-green)
![DRF](https://img.shields.io/badge/DRF-REST-red)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success)
![License](https://img.shields.io/badge/License-Private-lightgrey)

ERP Pulse is a **multi-tenant SaaS ERP aggregation platform** built with Django and React. It provides a unified interface for businesses to manage their ERP integrations, AI-powered analytics, invoicing, and enterprise reporting — all under a single subscription.

## Live Demo

- Frontend: [https://erp-pulse-gamma.vercel.app/](https://erp-pulse-gamma.vercel.app/)
- Backend API: [https://erp-pulse-backend.onrender.com](https://erp-pulse-backend.onrender.com)

---

## Platform Architecture

```
AGSuite (Platform)
    │
    ▼
Super Admin
    │
    ▼
Company
    │
    ├── Company Admin
    │
    └── Company Employees
```

### Core Modules

| Module | Description |
|--------|-------------|
| **Authentication** | JWT + Email OTP (registration & login) |
| **Multi-Tenancy** | Company-scoped data isolation |
| **Demo Request** | Public demo request submission with superadmin approval workflow |
| **Company Onboarding** | Convert approved demos into companies with plan/module assignment |
| **Invitation System** | UUID-based invitation links with expiry, acceptance, and role assignment |
| **Subscription & Licensing** | Plan management, usage tracking, module enable/disable, license enforcement |
| **NetSuite Integration** | OAuth 2.0 connection management, company-scoped credentials, employee assignment |
| **OCR** | Invoice/document extraction with preprocessing |
| **AI Assistant** | Pluggable AI providers (OpenAI, Gemini) with business context |
| **Invoice** | Invoice management |
| **BI Dashboard** | Business intelligence dashboards |
| **Reports Engine** | Scheduled and ad-hoc report generation |
| **Client Portal** | Company dashboard, employees, settings, subscription |
| **Super Admin Portal** | Company, plan, module, employee, demo request, and notification management |

---

## Key Features

### Demo Request & Onboarding
- Public demo request submission with validation
- Superadmin approval/rejection workflow
- Convert approved demos into companies with 5-step wizard:
  - Company details
  - Plan selection
  - Module selection
  - Usage limits
  - Company Admin creation
- Automated invitation email with setup link

### Invitation System
- UUID-based secure invitation tokens
- Configurable expiry (1–30 days)
- Public acceptance with password setup
- Resend/expire flows
- Duplicate active invitation prevention

### Subscription & Licensing
- Plan assignment, upgrade, downgrade, renew, cancel
- Automatic trial/plan expiry via management command
- Per-module usage tracking (OCR pages, AI requests, employees, storage, etc.)
- License enforcement middleware on every request
- Client-facing subscription page with usage progress
- Superadmin company subscription management with tabs:
  - Subscription
  - Modules
  - Usage
  - History

### NetSuite Integration
- Company-level NetSuite connection management
- OAuth 2.0 Authorization Code Grant
- Employee assignment to connections (employees never see credentials)
- Connection health tracking and test connection
- Connection audit trail
- REST Record API and SuiteQL support

### AI & Analytics
- Pluggable AI providers (OpenAI, Gemini)
- Typed business context objects
- Prompt versioning per request
- Per-call audit logging
- Short-TTL context caching
- Centralized `AnalyticsService` shared by Dashboard, Reports, and AI

### Security
- JWT authentication with httpOnly cookies
- Email OTP for registration and login
- Encrypted NetSuite credentials at rest
- Company-scoped data isolation
- License enforcement middleware
- Audit trail for all critical actions

---

## Tech Stack

### Backend
- Python 3.12
- Django 6.x
- Django REST Framework
- PostgreSQL (via Neon)
- JWT (SimpleJWT)
- OAuth 2.0 (NetSuite)

### Frontend
- React
- Vite
- React Router
- Axios

### AI Providers
- OpenAI
- Google Gemini

### Hosting
- Backend: [Render](https://render.com)
- Frontend: [Vercel](https://vercel.com)
- Database: [Neon](https://neon.tech)

---

## Project Structure

```
backend/
├── accounts/             # Authentication, users, OTP
├── tenancy/              # Company, modules, company-module links
├── rbac/                 # Role-based access control
├── audit/                # Audit logging
├── notifications/        # Notification system
├── common/               # Shared utilities, email, throttles
├── demo/                 # Demo request system
├── invitations/          # Invitation management
├── subscriptions/        # Subscription & licensing
├── superadmin/           # Super admin portal (companies, plans, modules, employees)
├── netsuite/             # NetSuite OAuth, sync, analytics
├── ai/                   # AI assistant
├── ocr/                  # OCR extraction
├── invoice/              # Invoice management
├── dashboard/            # Dashboard
├── reports/              # Reports
├── reports_engine/       # Scheduled reports
├── monitoring/           # Operational monitoring
├── sync/                 # Sync orchestration
├── analytics/            # Centralized analytics
├── bi/                   # BI dashboards
└── config/               # Django settings, URLs

frontend/
├── src/
│   ├── components/       # Reusable UI components
│   ├── pages/            # Page-level components
│   │   ├── superadmin/   # Super admin pages
│   │   ├── client/       # Client portal pages
│   │   └── invitations/  # Invitation acceptance pages
│   ├── services/         # API service layers
│   ├── contexts/         # React contexts (auth, etc.)
│   ├── routes/           # React Router routes
│   └── utils/            # Constants, helpers
```

---

## Architecture Principles

### Backend
- **Thin Views**: Views handle authentication, validation, and response formatting only
- **Service Layer**: All business logic lives in services
- **Repository Layer**: Database operations isolated in repositories
- **No Business Logic in Views**: Views delegate to services

### Frontend
- **Component Reusability**: Shared UI components in `components/`
- **Service Layer**: API calls centralized in `services/`
- **Route Protection**: `ProtectedRoute` wrapper for authenticated pages
- **Consistent Response Handling**: `unwrap()` pattern for API responses

---

## Development Status

### Completed Sprints
- ✅ **Sprint 8.0** — Demo Request Foundation
- ✅ **Sprint 8.1** — Company Onboarding & Invitation System
- ✅ **Sprint 8.2** — Subscription, Licensing & Tenant Feature Management
- ✅ **Sprint 8.3** — NetSuite Integration Management (Company/Employee)

### Backend Status
- All core modules implemented and tested
- 200+ tests passing
- `python manage.py check` passes with no issues
- Migrations up to date

### Frontend Status
- Super Admin portal complete
- Client portal complete
- NetSuite integration UI complete
- Subscription management UI complete
- Invitation acceptance flow complete
- Build successful

---

## Running Locally

### Backend
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
See `backend/.env.example` and `frontend/.env.example` for required variables.

---

## Testing

```bash
# Backend tests
cd backend
python manage.py test

# Frontend build
cd frontend
npm run build
```

---

## Documentation

| File | Description |
|------|-------------|
| `PROJECT_MEMORY.md` | Complete project context, architecture decisions, and progress |
| `SPRINT_8.0_8.1_SUMMARY.md` | Demo Request & Invitation System implementation details |
| `SPRINT_8.2_SUMMARY.md` | Subscription & Licensing implementation details |
| `SPRINT_8.3_SUMMARY.md` | NetSuite Integration Management implementation details |

---

## Design Principles

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

ERP Pulse aims to become a complete ERP aggregation platform supporting multiple ERP systems from a single dashboard.

```
User
    │
    ▼
ERP Pulse
    │
    ├── NetSuite
    ├── SAP
    ├── Zoho
    ├── Tally
    ├── QuickBooks
    └── Microsoft Dynamics
```

---

## License

This project is currently under active development.
