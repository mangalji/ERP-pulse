# ARCHITECTURE_DECISIONS.md

# ERP Pulse

## Architecture Decision Records (ADR)

Version: 1.0

---

# Purpose

This document records the important architectural decisions made during the development of ERP Pulse.

Every significant technical decision should include:

* Context
* Decision
* Reason
* Consequences

The purpose is to preserve engineering knowledge and ensure consistent future development.

---

# ADR-001

## Decision

ERP Pulse is an Analytics Platform, not an ERP.

### Status

Accepted

### Context

Many ERP implementations already exist.

Building another ERP system would increase complexity and duplicate existing functionality.

### Decision

ERP Pulse will focus on:

* Business Analytics
* Executive Dashboards
* AI Insights
* Reporting

It will not manage ERP transactions.

### Benefits

* Smaller scope
* Faster development
* Clear product identity
* Easier integration with multiple ERP systems in the future

---

# ADR-002

## Decision

NetSuite is the Source of Truth.

### Status

Accepted

### Context

Business data already exists in NetSuite.

### Decision

ERP Pulse reads data from NetSuite but does not own or modify transactional records.

### Benefits

* Prevents data inconsistency
* Reduces business risk
* Simplifies synchronization

---

# ADR-003

## Decision

Use Local PostgreSQL Synchronization.

### Status

Accepted

### Context

Calling NetSuite APIs for every dashboard request would be slow and could be affected by API limits.

### Decision

Synchronize NetSuite data into PostgreSQL and run analytics locally.

### Benefits

* Faster dashboards
* Better reporting performance
* Lower API usage
* Supports AI without repeatedly calling NetSuite

---

# ADR-004

## Decision

Separate Analytics Engine from AI Engine.

### Status

Accepted

### Context

AI models should explain business metrics, not calculate them.

### Decision

Analytics calculates facts.

AI interprets those facts.

### Benefits

* More reliable insights
* Lower hallucination risk
* Easier testing
* Better explainability

---

# ADR-005

## Decision

Use a Modular Monolith.

### Status

Accepted

### Context

The project is being developed by a single developer.

### Decision

Keep one deployable application with clearly separated modules.

### Benefits

* Faster development
* Simpler deployment
* Easier debugging
* Clear ownership of features

Future migration to microservices remains possible.

---

# ADR-006

## Decision

Adopt the Service + Repository Pattern.

### Status

Accepted

### Context

Business logic inside Views becomes difficult to maintain.

### Decision

Views coordinate requests.

Services implement business logic.

Repositories manage database operations.

### Benefits

* Clean architecture
* Better testing
* Improved maintainability

---

# ADR-007

## Decision

Create a Dedicated NetSuite Module.

### Status

Accepted

### Context

ERP-specific logic should not spread across the application.

### Decision

All NetSuite communication must occur inside the `netsuite` module.

### Benefits

* Loose coupling
* Easier maintenance
* Supports replacing NetSuite with another ERP in the future

---

# ADR-008

## Decision

Normalize NetSuite Data Before Storage.

### Status

Accepted

### Context

NetSuite API responses contain ERP-specific structures.

### Decision

Map NetSuite records into ERP Pulse models before saving.

### Benefits

* Cleaner database
* ERP-independent domain model
* Simpler analytics

---

# ADR-009

## Decision

Manual Synchronization for MVP.

### Status

Accepted

### Context

Real-time synchronization increases complexity.

### Decision

Users manually trigger synchronization in version 1.0.

### Benefits

* Faster MVP
* Easier debugging
* Simpler deployment

Future versions may support scheduled sync and webhooks.

---

# ADR-010

## Decision

Provider Abstraction for AI.

### Status

Accepted

### Context

AI providers may change over time.

### Decision

Use an abstraction layer instead of directly depending on a single provider.

### Supported Providers

* OpenAI
* Claude
* Gemini
* Ollama

### Benefits

* Avoid vendor lock-in
* Easier experimentation
* Flexible deployment

---

# ADR-011

## Decision

Business Health Score as the Primary KPI.

### Status

Accepted

### Context

Executives need one high-level indicator before exploring detailed metrics.

### Decision

ERP Pulse will calculate and display a Business Health Score derived from key business metrics.

### Benefits

* Quick business overview
* Better executive experience
* Clear dashboard focus

---

# ADR-012

## Decision

AI Consumes Structured Metrics Only.

### Status

Accepted

### Context

Sending raw ERP data increases token usage and reduces response quality.

### Decision

AI receives summarized business metrics instead of transactional records.

### Benefits

* Lower AI costs
* Faster responses
* Better consistency
* Easier prompt design

---

# ADR-013

## Decision

Use Conventional Git Commits.

### Status

Accepted

### Context

Consistent commit history improves collaboration and release tracking.

### Decision

Follow Conventional Commits.

Examples

* feat:
* fix:
* docs:
* refactor:
* test:
* chore:

### Benefits

* Cleaner Git history
* Easier changelog generation
* Better release management

---

# ADR-014

## Decision

Documentation-First Development.

### Status

Accepted

### Context

The project aims to reflect enterprise software engineering practices.

### Decision

Major features should be documented before implementation.

### Benefits

* Clear requirements
* Better planning
* Easier onboarding
* Consistent implementation

---

# Future ADRs

Whenever a major technical decision is made, add a new ADR instead of modifying old ones.

Examples

* Background job processing with Celery
* Scheduled synchronization
* Multi-company support
* Role-Based Access Control
* Data warehouse integration
* Forecasting engine
* Event-driven architecture

---

# Decision Template

Use this template for future ADRs.

```text
ADR-XXX

Title

Status

Accepted / Proposed / Deprecated

Context

Decision

Reason

Benefits

Consequences

Future Considerations
```

---

# Engineering Principle

Every architectural decision should favor:

* Simplicity
* Maintainability
* Scalability
* Testability
* Security
* Explainability

Avoid adding complexity unless it solves a demonstrated problem.

---

# End of ARCHITECTURE_DECISIONS.md
