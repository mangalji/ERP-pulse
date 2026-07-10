# IMPLEMENT_FEATURE.md

## Objective

Implement a new feature for ERP Pulse following the project's architecture and coding standards.

---

## Context Files

Always read these files before generating code:

* PROJECT_CONTEXT.md
* BACKEND_CONTEXT.md or FRONTEND_CONTEXT.md (depending on the task)
* DATABASE_CONTEXT.md (if database changes are required)
* NETSUITE_CONTEXT.md (if NetSuite integration is involved)
* AI_CONTEXT.md (if AI features are involved)
* CODE_STYLE.md

---

## Requirements

Implement the following feature:

<FEATURE_DESCRIPTION>

---

## Rules

* Follow the Modular Monolith architecture.
* Keep business logic inside Services.
* Use the Repository Pattern for database access.
* Do not place business logic in Views or React components.
* Follow existing naming conventions.
* Produce production-ready code.
* Include validation and error handling.
* Add logging where appropriate.
* Do not introduce unnecessary dependencies.

---

## Expected Output

Provide:

1. File structure (if new files are needed)
2. Complete implementation
3. Explanation of design decisions
4. Any required migrations
5. API changes (if applicable)
6. Testing considerations
