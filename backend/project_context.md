# PROJECT_CONTEXT.md

# ERP Pulse - Project Context & Architecture Guide

> **Purpose**
>
> This document is the single source of truth for this project.
>
> Every developer, AI assistant (Copilot, Cline, Claude, ChatGPT), or contributor must read this document before implementing any feature.
>
> Do not redesign the architecture unless explicitly instructed.

---

# 1. Project Overview

ERP Pulse is a **multi-tenant SaaS platform** developed for **AGSuite**.

AGSuite sells this platform to multiple client companies.

Every client receives an isolated workspace.

The platform is primarily designed around **Oracle NetSuite integration**.

The first major module is **Invoice Reader**, followed by dashboards, analytics, reports, and AI-powered business assistance.

---

# 2. Business Goal

The goal is to eliminate manual data entry into NetSuite.

Current workflow:

User manually creates invoices inside NetSuite.

Future workflow:

Invoice PDF/Image

↓

OCR

↓

AI Extraction

↓

User Review

↓

Approval

↓

Generate NetSuite Payload

↓

Post to NetSuite

↓

Invoice Created

The user should only review extracted data instead of typing everything manually.

---

# 3. Product Architecture

There are only **two portals**.

## Portal 1

### AGSuite Super Admin Portal

Used only by AGSuite employees.

Responsibilities:

- Manage client companies
- Manage subscription plans
- Enable/Disable modules
- View system analytics
- Manage AGSuite employees
- Support client companies
- Access client portals for support
- Monitor OCR and AI jobs
- Monitor NetSuite integration
- View audit logs

---

## Portal 2

### Client Portal

Every client company gets an isolated portal.

Each company can only access its own data.

Inside every client portal:

- Company Admin
- Employees

Client responsibilities:

- Invoice Reader
- Dashboard
- Reports
- Employees
- Notifications
- Company Settings
- NetSuite Connection

---

# 4. Multi-Tenant Rules

Every company is isolated.

Never expose one company's data to another company.

AGSuite Super Admin can access every company.

Support access must always be audited.

Never bypass tenancy middleware.

---

# 5. RBAC

This project DOES NOT use Django Groups.

Roles are implemented using:

Role

Permission

UserRole

Never use:

django.contrib.auth.models.Group

Never introduce Groups.

Always reuse the existing RBAC implementation.

---

# 6. Existing Modules

Already implemented:

- Core
- Accounts
- Common
- Tenancy
- RBAC
- Audit
- Notifications (Foundation)
- OCR
- AI
- Invoice
- Async Processing
- Celery
- Redis

Reuse existing modules.

Do not duplicate functionality.

---

# 7. Invoice Workflow

Upload

↓

Batch Created

↓

Files Created

↓

Celery Queue

↓

OCR

↓

Gemini AI

↓

Extracted JSON

↓

Validation

↓

Review

↓

Approve

↓

Ready for NetSuite

↓

Future Posting

Never bypass this workflow.

---

# 8. NetSuite Strategy

Current:

Generate Preview Payload.

Future:

Actual NetSuite Posting.

NetSuite integration must always use normalized extracted data.

Never post raw OCR output.

---

# 9. AI Strategy

Gemini is used only where it adds business value.

Examples:

- OCR correction
- Invoice field extraction
- Confidence scoring
- Business insights

Never use AI where deterministic code is sufficient.

Prefer validation rules before AI.

---

# 10. Async Processing

Background processing uses:

Celery

Redis

Flower

Never introduce threading for long-running jobs.

---

# 11. Folder Responsibilities

core/

Shared infrastructure.

---

accounts/

Authentication.

---

tenancy/

Companies.

Modules.

Settings.

Multi-tenancy.

---

rbac/

Roles.

Permissions.

UserRole.

---

invoice/

Invoice business workflow.

---

ocr/

OCR processing.

---

ai/

Gemini integration.

---

audit/

Audit logs.

---

notifications/

Notifications.

---

superadmin/

AGSuite Portal.

---

dashboard/

Business dashboards.

---

analytics/

Analytics engine.

---

netsuite/

NetSuite integration.

---

sync/

Synchronization.

---

reports/

Reports.

---

monitoring/

System monitoring.

---

# 12. Coding Rules

Reuse existing architecture.

Never duplicate services.

Never duplicate models.

Never duplicate serializers.

Never redesign modules.

Views must stay thin.

Business logic belongs inside services.

Use repositories when available.

Always use AuditService.

Always respect tenancy.

Always respect RBAC.

Use select_related().

Use prefetch_related().

Avoid N+1 queries.

Use pagination.

Use filtering.

Use ordering.

---

# 13. Things Never To Do

Never use Django Groups.

Never bypass RBAC.

Never bypass tenancy.

Never create fake dashboard data.

Never create placeholder notifications.

Never create duplicate Company models.

Never duplicate OCR.

Never duplicate AI.

Never redesign architecture.

Never introduce breaking changes.

---

# 14. Development Workflow

Every feature follows:

Business Requirement

↓

Architecture

↓

Backend

↓

Frontend

↓

Integration

↓

Testing

↓

Review

↓

Approval

Never skip review.

---

# 15. Current Roadmap

Completed

✔ Core Foundation

✔ Multi-Tenancy

✔ RBAC

✔ Audit

✔ Invoice Reader

✔ OCR Integration

✔ AI Integration

✔ Celery + Redis

✔ Invoice Review

✔ Payload Preview

In Progress

• AGSuite Super Admin

Upcoming

• Client Portal

• NetSuite Integration

• Dashboard

• Analytics

• Reports

• AI Assistant

---

# 16. AI Assistant Instructions

If you are an AI assistant:

Read this document first.

Reuse existing code.

Do not redesign architecture.

Do not duplicate functionality.

Implement only the requested feature.

When unsure, prefer consistency over creativity.

Always preserve backward compatibility.

This document is the project's single source of truth.