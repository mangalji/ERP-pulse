# BACKEND_CONTEXT.md

# ERP Pulse Backend Development Context

Version: 1.0

---

# Purpose

This document defines the backend architecture, coding standards, and implementation rules for ERP Pulse.

All backend code must follow these guidelines.

---

# Tech Stack

* Python 3.x
* Django
* Django REST Framework
* PostgreSQL
* JWT Authentication

Future

* Redis
* Celery
* Docker

---

# Backend Architecture

The application follows a **Modular Monolith** architecture.

```text
React
    │
    ▼
Django REST API
    │
    ▼
Views
    │
    ▼
Services
    │
    ▼
Repositories
    │
    ▼
PostgreSQL
```

Business logic must never exist in Views.

---

# Django Apps

accounts

netsuite

customers

items

sales

analytics

ai

reports

common

Each app owns its own:

* Models
* Serializers
* Services
* Repositories
* URLs
* Tests
* Validators

---

# Folder Structure

```text
apps/

customers/

├── models.py
├── serializers.py
├── urls.py
├── views.py
├── services.py
├── repositories.py
├── validators.py
├── selectors.py
├── exceptions.py
└── tests.py
```

---

# Layer Responsibilities

## Views

Responsible for:

* Authentication
* Request validation
* Calling services
* Returning HTTP responses

Views must NOT contain:

* Business rules
* Database queries
* Complex calculations

---

## Services

Responsible for:

* Business logic
* Validation beyond serializer level
* Workflow orchestration
* Transactions

Services may call:

* Repositories
* Other services
* External integrations

---

## Repositories

Responsible only for database operations.

Repositories should:

* Read
* Create
* Update
* Delete
* Query

No business logic.

---

## Selectors

Selectors are read-only query helpers.

Examples:

* Dashboard statistics
* Customer search
* Revenue summaries

Selectors should never modify data.

---

# NetSuite Integration

Only the `netsuite` app communicates with NetSuite.

Never call NetSuite APIs from:

* Views
* Analytics
* AI
* Dashboard

Always use:

NetSuite Client

↓

Sync Service

↓

Repository

---

# Synchronization Flow

```text
NetSuite

↓

REST API

↓

NetSuite Client

↓

Sync Service

↓

Repository

↓

PostgreSQL
```

Dashboards and analytics must always use PostgreSQL.

---

# Analytics Rules

Analytics consumes synchronized data only.

Never calculate analytics directly from NetSuite responses.

Examples:

* Revenue
* Profit
* Customer Performance
* Product Performance
* Monthly Growth

---

# AI Rules

The AI layer receives structured business metrics.

Never send raw ERP payloads to the AI provider.

Preferred input:

* Revenue
* Profit
* Monthly Growth
* Top Customers
* Top Products

Preferred output:

* Executive Summary
* Business Insights
* Recommendations
* Risk Alerts

All AI responses must be validated before saving.

---

# API Standards

Base URL

/api/v1/

Authentication

JWT

Standard Response

```json
{
  "success": true,
  "message": "",
  "data": {}
}
```

---

# Database Rules

* PostgreSQL
* snake_case naming
* UUID preferred
* Soft delete where appropriate
* Foreign keys for relationships
* Avoid duplicate data

---

# Coding Standards

* Follow PEP 8
* Use type hints where practical
* Keep functions short
* Prefer readability
* Avoid code duplication
* Use meaningful names
* Write reusable services

---

# Logging

Log:

* Login
* Synchronization
* API failures
* AI failures
* Unexpected exceptions

Never log:

* Passwords
* Tokens
* Secrets

---

# Error Handling

Create custom exceptions.

Examples:

* NetSuiteException
* CustomerException
* ValidationException
* AnalyticsException
* AIException

Return meaningful API responses.

---

# Security

* JWT Authentication
* Validate all inputs
* Validate uploaded files
* Use environment variables
* Never hardcode secrets
* Check object ownership before returning data

---

# Testing

Every major service should have unit tests.

Priority:

* Services
* Repositories
* API endpoints

---

# Development Philosophy

Write backend code that is:

* Modular
* Testable
* Scalable
* Maintainable
* Production-ready

Always prioritize clean architecture over shortcuts.
