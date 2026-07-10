# CODE_STYLE.md

# ERP Pulse

## Coding Standards & Development Guidelines

Version: 1.0

---

# Purpose

This document defines coding standards, naming conventions, architecture rules, and development principles for ERP Pulse.

Every generated code file should follow these rules to maintain consistency, readability, scalability, and production quality.

---

# General Philosophy

Write code for humans first.

The primary goals are:

* Readability
* Maintainability
* Simplicity
* Scalability
* Reusability

Avoid clever code.

Prefer clear code.

---

# General Principles

Follow:

* SOLID Principles
* DRY (Don't Repeat Yourself)
* KISS (Keep It Simple)
* Single Responsibility Principle
* Composition over Inheritance

Avoid premature optimization.

---

# Python Style Guide

Follow:

* PEP 8
* PEP 257 (Docstrings)
* PEP 484 (Type Hints)

Maximum line length:

100 characters

Use meaningful variable names.

Avoid single-letter variables except in loops.

---

# Naming Conventions

## Variables

Use

snake_case

Example

```python
customer_name
total_revenue
monthly_growth
```

---

## Functions

Use

snake_case

Examples

```python
calculate_profit()

sync_customers()

generate_report()
```

---

## Classes

Use

PascalCase

Examples

```python
CustomerService

NetSuiteClient

RevenueAnalytics
```

---

## Constants

Use

UPPER_CASE

Examples

```python
DEFAULT_PAGE_SIZE

API_TIMEOUT
```

---

## Files

Use

snake_case

Examples

```text
customer_service.py

analytics_engine.py

report_generator.py
```

---

# Function Design

Functions should:

* Do one thing
* Be short
* Return predictable results

Preferred length

20–40 lines

Avoid functions longer than 80 lines.

---

# Class Design

Each class should have one responsibility.

Examples

Good

```text
CustomerService

CustomerRepository

CustomerMapper
```

Bad

```text
CustomerManager

UtilityClass

HelperFunctions
```

---

# Views

Views should only:

* Authenticate
* Validate request
* Call service
* Return response

Views should NOT:

* Query database directly
* Call NetSuite
* Calculate analytics
* Build AI prompts

---

# Services

Services contain:

* Business logic
* Validation
* Transactions
* Workflow

Services may call:

* Repositories
* External clients
* Other services

---

# Repositories

Repositories handle:

* Create
* Read
* Update
* Delete
* Query

No business rules.

---

# Models

Models should:

* Define schema
* Define relationships
* Contain lightweight helpers if necessary

Models should NOT:

* Call APIs
* Perform analytics
* Generate reports

---

# React Components

Each component should have a single responsibility.

Good

```text
RevenueCard

ProfitCard

CustomerTable

SalesChart
```

Avoid

DashboardEverything.jsx

---

# Component Size

Preferred

Less than 200 lines

Split large components.

---

# API Services

All API requests belong inside

```text
services/
```

Never call Axios directly inside components.

Good

```text
Dashboard

↓

dashboardService

↓

Backend
```

---

# Error Handling

Catch expected exceptions.

Return meaningful messages.

Never expose stack traces.

Log unexpected exceptions.

---

# Logging

Log

* Synchronization
* Authentication
* API failures
* AI failures

Do not log

* Passwords
* API Keys
* JWT Tokens

---

# Comments

Write comments only when they explain *why*, not *what*.

Good

```python
# Prevent duplicate synchronization by using NetSuite Internal ID
```

Avoid

```python
# Increment i
i += 1
```

---

# Imports

Python import order

1. Standard Library

2. Third-party Libraries

3. Local Project Imports

Separate groups with one blank line.

---

# API Responses

Always use the standard response format.

```json
{
  "success": true,
  "message": "",
  "data": {}
}
```

Never return inconsistent response structures.

---

# Database Queries

Prefer:

Repository Layer

Avoid:

Raw SQL unless absolutely necessary.

Optimize ORM queries using:

* select_related()
* prefetch_related()

when appropriate.

---

# Type Hints

Use type hints for:

* Function arguments
* Return values
* Public methods

Example

```python
def sync_customers() -> list:
    ...
```

---

# Docstrings

Public classes and methods should include concise docstrings.

Example

```python
"""
Synchronize customers from NetSuite into the local database.
"""
```

---

# Testing

Write tests for:

* Services
* Repositories
* API endpoints

Do not rely only on manual testing.

---

# Git Commit Convention

Use Conventional Commits.

Examples

```text
feat: add customer synchronization

fix: handle NetSuite timeout

refactor: simplify analytics engine

docs: update API documentation

test: add customer service tests
```

---

# Pull Request Checklist

Every feature should:

* Build successfully
* Pass tests
* Follow architecture
* Follow coding standards
* Include documentation updates if required

---

# Performance

Avoid:

* N+1 queries
* Duplicate API calls
* Duplicate calculations

Cache only when necessary.

---

# Security

Always:

* Validate inputs
* Escape untrusted data where required
* Use environment variables
* Verify authorization before returning resources

Never:

* Hardcode secrets
* Trust external input

---

# AI Code Generation Rules

When generating code:

* Produce complete, production-ready implementations.
* Follow the Service → Repository → Database architecture.
* Avoid placeholder code unless explicitly requested.
* Use meaningful names.
* Keep modules focused.
* Prefer readability over clever abstractions.
* Explain assumptions if requirements are incomplete.

---

# Code Review Checklist

Before considering any implementation complete, verify:

* Architecture rules followed
* No business logic in Views
* No duplicated code
* Clear naming
* Proper error handling
* Logging added where appropriate
* Security considerations addressed
* Performance implications reviewed

---

# Development Philosophy

ERP Pulse should feel like software developed by an experienced engineering team.

Every line of code should contribute to:

* Reliability
* Maintainability
* Scalability
* Simplicity

If two solutions work, choose the one that is easier for the next developer to understand.

---

# End of CODE_STYLE.md
