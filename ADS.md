📘 ERP Pulse v2 – API Design Specification (ADS)

Ye document backend aur frontend dono ka contract hoga.

Rule:

Frontend kabhi database nahi dekhega. Sirf APIs.

API Standards
Base URL
/api/v1/

Future

/api/v2/

Versioning easy hogi.

Response Format

Har API same response degi.

Success
{
    "success": true,
    "message": "Invoice uploaded successfully.",
    "data": {},
    "meta": {}
}
Error
{
    "success": false,
    "message": "Validation failed.",
    "errors": {
        "invoice_number": [
            "This field is required."
        ]
    }
}

Pure project me same format.

Authentication APIs
POST   /auth/login/

POST   /auth/logout/

POST   /auth/refresh/

POST   /auth/forgot-password/

POST   /auth/reset-password/

GET    /auth/profile/

PATCH  /auth/profile/
AGSuite APIs
Companies
GET

/platform/companies/

Create Company

POST

/platform/companies/

Company Details

GET

/platform/companies/{id}/

Suspend Company

PATCH

/platform/companies/{id}/status/

Subscription

PATCH

/platform/subscription/

Feature Flags

PATCH

/platform/modules/
Company APIs

Dashboard

GET

/dashboard/

Employees

GET

/employees/

POST

/employees/

PATCH

/employees/{id}/

DELETE

/employees/{id}/

Customers

Same pattern.

OCR APIs

Upload

POST

/invoice-reader/upload/

Batch Upload

POST

/invoice-reader/batch-upload/

Status

GET

/invoice-reader/status/{batch_id}/

Results

GET

/invoice-reader/results/

Invoice Details

GET

/invoice-reader/results/{id}/

Raw JSON

GET

/invoice-reader/json/{id}/

Retry OCR

POST

/invoice-reader/retry/{id}/

Delete Upload

DELETE

/invoice-reader/{id}/
AI APIs

Chat

POST

/ai/chat/

History

GET

/ai/conversations/

Conversation

GET

/ai/conversations/{id}/
Reports
GET

/reports/

POST

/reports/

GET

/reports/{id}/

DELETE

/reports/{id}/
NetSuite

Connection

POST

/integrations/netsuite/connect/

Health

GET

/integrations/netsuite/status/

Sync

POST

/integrations/netsuite/sync/

Future

Post Invoice

POST

/integrations/netsuite/vendor-bill/
Monitoring
GET

/monitoring/health/

GET

/monitoring/jobs/

GET

/monitoring/logs/
Pagination Standard
{
    "count": 250,

    "next": "...",

    "previous": "...",

    "results": []
}
Filtering Standard

Example

?status=completed

?vendor=abc

?date_from=2026-01-01

?date_to=2026-02-01
Sorting
?ordering=created_at

?ordering=-created_at
Searching
?search=invoice
API Rules

No endpoint

Should return

500

Without logging.

Every endpoint

Must have

Tenant

User

Permission

Audit

validation.

File Upload Rules

Supported

PDF

PNG

JPEG

WEBP

Maximum

Plan based.

Long Running Tasks

Return

{
    "job_id": "...",

    "status": "QUEUED"
}

Never wait 10 minutes for response.

Error Codes
400

401

403

404

409

422

429

500

503

Use consistently.
