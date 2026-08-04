ERP Pulse v2
Database Design Document (DDD) v1.0
1. Design Principles
Rules
Multi-tenant by default
Soft delete support
Audit support
UUID primary keys
created_at / updated_at in every business table
Foreign keys with proper constraints
Indexes on frequently queried fields
No business data without tenant ownership
2. Core Entity Relationship
Platform (AGSuite)
        │
        ▼
Tenant (Client Company)
        │
        ├──────────────┐
        ▼              ▼
Subscription      NetSuite Connection
        │
        ▼
Users
        │
        ▼
Roles
        │
        ▼
Permissions

──────────────────────────────

Business Modules

OCR

AI

Reports

Dashboard

Monitoring
3. Core Tables
Tenant

Represents a client/company.

Fields:

id (UUID)
name
company_code
email
phone
status
timezone
currency
country
logo
created_at
updated_at
Subscription

Fields

tenant_id
plan
start_date
end_date
max_users
max_storage
ai_enabled
ocr_enabled
reports_enabled
netsuite_enabled
Module

Master table

OCR

AI

Dashboard

Reports

Monitoring

NetSuite
TenantModule

Many-to-many

tenant

↓

module

↓

enabled

↓

limits
4. User Tables
User

Use Django custom user.

Additional

tenant_id
employee_code
designation
department
last_activity
status
Role

Examples

Company Admin

Finance

Purchase

HR

Sales

Viewer
Permission

Examples

invoice.create

invoice.view

invoice.edit

report.download

ai.chat

ocr.upload
RolePermission

Many-to-many.

UserRole

Many-to-many.

5. NetSuite Tables
NetSuiteConnection

Fields

tenant_id
account_id
environment (Sandbox / Production)
auth_method
access_token (encrypted)
refresh_token (encrypted)
token_expiry
last_sync
status
SyncJob

Fields

tenant_id
job_type
started_at
completed_at
status
records_processed
records_failed
6. OCR Tables

(Reuse existing work)

OCRUpload

Existing model

Need

tenant_id

uploaded_by

processing_status
Invoice

Extracted invoice.

InvoiceItem

Invoice lines.

OCRExtraction

Raw AI response.

OCRValidation

Warnings

Confidence

Errors

7. AI Tables
Conversation
tenant
user
title
Message
conversation
role
content
ToolExecution

Store

AI Tool Calls.

8. Dashboard Tables

Mostly cached analytics.

9. Reports
Report

Generated reports.

ReportExport

Export history.

10. Monitoring
HealthCheck

API

NetSuite

AI

OCR

UsageLog

AI

OCR

Reports

Downloads

11. Audit

Very important.

AuditLog

Fields

tenant
user
module
action
entity
entity_id
old_value
new_value
ip
timestamp
12. Notification

Future

Email

In-app

Push

13. Common Base Model

Every business model inherits

BaseModel

id

created_at

updated_at

created_by

updated_by

is_deleted
14. Tenant Base Model

Every business model also contains

tenant

So

Invoice

↓

TenantBaseModel

↓

BaseModel
15. Relationships
Tenant

↓

Users

↓

Roles

↓

Invoices

↓

Invoice Items

↓

OCR

↓

AI

↓

Reports
16. Future ERP Providers

Instead of

NetSuiteConnection

Eventually

IntegrationConnection

↓

NetSuite

SAP

Dynamics

Odoo

NetSuite will be first provider.

17. Migration Strategy

Rules

Never interactive migrations
UUID everywhere
Indexes added immediately
Constraints from day one
Soft delete only where required
18. Naming Rules

Models

Singular

Tenant

Invoice

Report

Tables

Plural (default Django naming is fine)

19. Database Rules
No business logic in models.
Services own business rules.
Repositories own database access.
Models define data only.
20. Scaling Strategy

Current

SQLite (Development)

↓

Production

Neon PostgreSQL

↓

Future

PostgreSQL + Read Replicas

↓

Redis

↓

Object Storage