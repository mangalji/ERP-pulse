ERP Pulse v2
System Architecture Document (SAD) v1.0
1. System Overview
Product

ERP Pulse

Type

Multi-Tenant SaaS Platform

Focus

NetSuite Business Intelligence

Purpose

ERP Pulse NetSuite ko replace nahi karega.

ERP Pulse NetSuite ke upar Intelligence Layer provide karega.

Example

NetSuite

↓

Business Data

↓

ERP Pulse

↓

AI

OCR

Analytics

Dashboards

Reports

Monitoring

Automation
2. High Level Architecture
                         Internet
                             │
──────────────────────────────────────────────────────────

                    ERP Pulse Platform

──────────────────────────────────────────────────────────

             AGSuite Portal

             Company Portal

──────────────────────────────────────────────────────────

Authentication

Tenant

RBAC

Subscription

Feature Flags

──────────────────────────────────────────────────────────

Business Modules

Dashboard

OCR

AI

Reports

Monitoring

NetSuite Integration

──────────────────────────────────────────────────────────

PostgreSQL

Redis

Storage

Logs

──────────────────────────────────────────────────────────

External Services

NetSuite

Gemini

Email

Future Integrations
3. Architecture Layers
Layer 1

Platform Layer

Responsible for

Authentication
Tenant Management
Subscription
Roles
Permissions
Feature Flags

No business logic.

Layer 2

Business Layer

Contains

Dashboard

OCR

AI

Reports

Analytics

NetSuite

Invoice Reader

Business logic lives here.

Layer 3

Infrastructure Layer

Contains

Database

Redis

Storage

Email

LLM

Logging

External APIs

No business rules.

4. User Types
Platform Users
Super Admin

Support

Sales

Developer
Company Users
Company Admin

Finance

Purchase

Sales

HR

Manager

Employee

Viewer
5. Tenant Architecture
Platform

↓

Tenant

↓

Department

↓

Role

↓

Users

↓

Business Data

Tenant isolation is mandatory.

Every business table contains

tenant_id
6. Authentication Flow
User

↓

Login

↓

JWT

↓

Resolve Tenant

↓

Load Roles

↓

Load Permissions

↓

Access Modules
7. Authorization

Access Control

Tenant

↓

Role

↓

Permission

↓

Feature Flag

↓

API

Every API checks

Tenant
Role
Permission
Module Enabled
8. Module Architecture

Current modules

Dashboard

OCR

AI

Reports

Monitoring

Notifications

Audit

NetSuite

Every module is independent.

9. Integration Architecture

Current

NetSuite

Future

Integrations

↓

NetSuite

SAP

Dynamics

Oracle

Odoo

Business modules never call providers directly.

Instead

Integration Interface

↓

Provider

↓

External API
10. OCR Architecture
Invoice Reader

↓

Upload

↓

Queue

↓

OpenCV

↓

Gemini

↓

Validation

↓

Review

↓

Invoice

↓

(Post to NetSuite)
11. AI Architecture
User

↓

AI Service

↓

Planner

↓

Tools

↓

Business Services

↓

Validator

↓

LLM

↓

Response

Exactly as we've been building.

12. NetSuite Architecture
NetSuite Connection

↓

REST API

↓

SuiteQL

↓

Sync

↓

Local Database

↓

Analytics

NetSuite remains Source of Truth.

13. Dashboard

Two dashboards

Platform Dashboard

Company Dashboard

Never mixed.

14. Data Ownership
AGSuite

owns

Platform

----------------

Company

owns

Business Data

----------------

Employee

owns

Personal Preferences
15. Logging

Every request

Request ID

Tenant ID

User ID

Module

Execution Time

Status

Mandatory.

16. Audit

Every critical action stored.

Examples

Login

Role Change

Invoice Upload

NetSuite Sync

AI Query

Settings Change

Nothing important happens without audit.

17. Storage
PostgreSQL

↓

Business Data

----------------

Redis

↓

Queue

Cache

----------------

Object Storage

↓

Invoices

Exports

Attachments
18. Deployment
Nginx

↓

Django

↓

Gunicorn

↓

Celery

↓

Redis

↓

PostgreSQL

↓

Object Storage

Future Kubernetes compatible.

19. Folder Structure
backend/

accounts/

core/

tenant/

subscription/

rbac/

integrations/
    base/
    netsuite/

ocr/

ai/

dashboard/

reports/

monitoring/

notifications/

audit/

common/

config/
20. Development Principles

Views

↓

Services

↓

Repositories

↓

Database

No business logic inside Views.

No external API inside Views.

No database access inside AI Planner.

21. Engineering Rules
Multi-tenant by design
SOLID
DRY
Clean Architecture
Repository Pattern
Service Layer
Dependency Injection where appropriate
No magic numbers
Configuration-driven
Structured logging
Audit-first mindset
22. Future Expansion

ERP Pulse should support:

Multiple ERP providers
Multiple AI providers
Multiple OCR providers
Multi-language
Mobile app
Public APIs
Marketplace/Plugins

without major architectural changes.