ERP Pulse v2
Backend Development Standards (BDS)

Version 1.0

1. Architecture Rule

Every request follows

Request

↓

View

↓

Service

↓

Repository

↓

Database

Views never contain business logic.

2. Folder Structure

Every app

app/

models/

repositories/

services/

serializers/

views/

urls/

permissions/

validators/

exceptions/

tests/

constants/

utils/

Never create random files.

3. Models

Models only define

Data
Relationships
Constraints

Models never

call APIs
perform business logic
send emails
call AI
4. Views

Views only

authenticate
validate request
call service
return response

Views never

query multiple models
contain calculations
contain business rules
5. Services

Everything business related belongs here.

Examples

InvoiceService

OCRService

NetSuiteService

ReportService

DashboardService
6. Repository

Repositories own

Database access.

Never

Invoice.objects.filter(...)

inside Views.

Instead

InvoiceRepository.get_pending()
7. Serializers

Only

Validation

Transformation

Nothing else.

8. Permissions

Every endpoint checks

Authentication

↓

Tenant

↓

Role

↓

Permission

↓

Feature Enabled

No shortcut.

9. Multi Tenant Rule

Every business query

Must filter

tenant=request.tenant

Never

Invoice.objects.all()

Critical.

10. Logging

Every request logs

request_id

tenant_id

user_id

module

execution_time

status

Never use print().

Use structured logging.

11. Exceptions

Custom exceptions only.

Example

ValidationException

BusinessRuleException

OCRException

AIException

IntegrationException
12. Transactions

Whenever multiple writes happen

Use

transaction.atomic()
13. External APIs

Never

inside View.

Use

Integration Service

↓

Provider

↓

API
14. AI Rules

Planner

Never accesses database.

Planner

Never calls ORM.

Planner

Uses services only.

15. OCR Rules

OCR

Never posts directly to NetSuite.

Always

OCR

↓

Review

↓

Approval

↓

NetSuite
16. Testing

Every new feature

Must include

Unit tests
Integration tests

Never merge untested code.

17. Migrations

Rules

No interactive migrations
UUID primary keys
Add indexes early
Backward compatible where possible
18. API Response

Every endpoint

Returns

{
  "success": true,
  "message": "...",
  "data": {},
  "meta": {}
}

Same format everywhere.

19. Configuration

Never hardcode

MODEL_NAME = "gemini..."

Everything goes to

settings.py

.env
20. Constants

Magic strings

Not allowed.

Create

constants.py
21. Dependency Injection

Services receive dependencies.

Never instantiate large services repeatedly.

22. Code Style
Python 3.12+
PEP8
Type hints
Docstrings
Ruff/Black compatible
No commented-out code
No TODOs in merged code
23. Security
Validate every upload
Encrypt secrets
Never expose stack traces
Rate limit sensitive endpoints
Validate MIME + file contents
Audit critical actions
24. Performance
Use select_related()
Use prefetch_related()
Paginate lists
Avoid N+1 queries
Cache where appropriate
Background jobs for long tasks
25. Git Rules

Branch strategy

main

develop

feature/<name>

bugfix/<name>

hotfix/<name>

Commit style

feat:

fix:

refactor:

docs:

test:

chore:
26. Pull Request Checklist

Before merge

Tests pass
No debug code
No print()
No secrets
Documentation updated
Changelog updated
Migration reviewed
Security reviewed
27. Cline Rules (Very Important)

Every prompt to Cline must follow:

Review previous implementation.
Fix technical debt if found.
Implement current phase only.
Do not modify unrelated modules.
Run tests.
Update documentation.
Return summary of changes.

No exceptions.

28. Code Review Rules (My Responsibility)

Main har PR ko review karunga based on:

Runtime bugs
Logic bugs
Security
Scalability
Multi-tenancy
Performance
Clean Architecture
Django best practices
Production readiness

Severity levels:

🔴 Critical
🟠 High
🟡 Medium
🔵 Low