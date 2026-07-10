# NETSUITE_CONTEXT.md

# ERP Pulse

## NetSuite Integration Context

Version: 1.0

---

# Purpose

This document defines how ERP Pulse communicates with NetSuite.

ERP Pulse is **not an ERP system**.

ERP Pulse is an **AI-powered Business Intelligence Platform** that reads business data from NetSuite, synchronizes it into a local PostgreSQL database, performs analytics, and generates executive insights.

All NetSuite integration must follow this document.

---

# Integration Philosophy

NetSuite is the **Source of Truth**.

ERP Pulse is the **Analytics Layer**.

ERP Pulse should never modify business transactions inside NetSuite.

ERP Pulse is primarily a **Read-Only Integration**.

---

# High-Level Architecture

```text
                 NetSuite ERP

                      │

          SuiteTalk REST Record API

                      │

            NetSuite Client Layer

                      │

             Synchronization Service

                      │

              Repository Layer

                      │

                 PostgreSQL

                      │

              Analytics Engine

                      │

            AI Intelligence Engine

                      │

              Executive Dashboard
```

---

# Responsibilities

NetSuite

* Stores ERP data
* Customer records
* Sales Orders
* Items
* Transactions

ERP Pulse

* Synchronize data
* Store local copy
* Perform analytics
* Generate AI insights
* Generate reports

---

# Integration Rules

Only the **netsuite** Django app may communicate with NetSuite.

No other module should directly call NetSuite APIs.

Forbidden:

Dashboard

↓

NetSuite API

Correct:

Dashboard

↓

Analytics

↓

PostgreSQL

---

# Folder Structure

```text
apps/

netsuite/

├── clients/
├── services/
├── sync/
├── mappers/
├── repositories/
├── exceptions.py
├── constants.py
└── utils.py
```

---

# Client Layer

Responsible for:

* Authentication
* HTTP Requests
* Pagination
* Retry
* Error Handling

The Client Layer should never contain business logic.

---

# Service Layer

Responsible for:

* Synchronization
* Validation
* Mapping
* Logging

Examples

CustomerSyncService

ItemSyncService

SalesOrderSyncService

InvoiceSyncService (Future)

---

# Mapper Layer

Purpose

Convert NetSuite response into ERP Pulse models.

Example

NetSuite JSON

↓

CustomerMapper

↓

Customer Model

Never expose raw NetSuite responses outside this layer.

---

# Repository Layer

Responsible only for:

* Insert
* Update
* Delete
* Search

Repositories should never call NetSuite APIs.

---

# Synchronization Strategy

Synchronization Flow

```text
NetSuite

↓

REST API

↓

NetSuite Client

↓

Mapper

↓

Repository

↓

PostgreSQL
```

Dashboard queries PostgreSQL only.

---

# Synchronization Rules

Synchronization must:

* Avoid duplicate records
* Update changed records
* Preserve local analytics data
* Log synchronization activity

Never delete historical analytics automatically.

---

# MVP Synchronization

Manual Synchronization

User clicks:

"Sync NetSuite"

↓

ERP Pulse

↓

Download Data

↓

Update PostgreSQL

Future

Scheduled Synchronization

Cron

Celery

Webhooks

---

# NetSuite Records (MVP)

Synchronize

Customers

Items

Sales Orders

Sales Order Lines

---

Future

Invoices

Payments

Vendors

Purchase Orders

Inventory

Employees

Locations

Subsidiaries

---

# Customer Data

Synchronize

* Internal ID
* Entity ID
* Company Name
* Email
* Phone
* Currency
* Status
* Address

Store NetSuite Internal ID.

Never use customer name as a unique identifier.

---

# Item Data

Synchronize

* Internal ID
* Item Name
* SKU
* Category
* Unit Price
* Cost
* Status

---

# Sales Orders

Synchronize

* Internal ID
* Transaction Number
* Customer
* Date
* Status
* Total
* Currency

---

# Sales Order Lines

Synchronize

* Item
* Quantity
* Rate
* Amount
* Tax

---

# Synchronization Frequency

MVP

Manual

Future

* Hourly
* Daily
* On Demand
* Webhook Based

---

# Error Handling

Retry

Network Failures

API Timeout

Rate Limit

Unauthorized

Log all failures.

Do not stop synchronization because one record fails.

Continue processing remaining records.

---

# Authentication

Authentication credentials must come from environment variables.

Never hardcode:

* Account ID
* Consumer Key
* Consumer Secret
* Token ID
* Token Secret

---

# Environment Variables

Example

```text
NETSUITE_ACCOUNT=

NETSUITE_BASE_URL=

NETSUITE_CONSUMER_KEY=

NETSUITE_CONSUMER_SECRET=

NETSUITE_TOKEN_ID=

NETSUITE_TOKEN_SECRET=
```

---

# API Design

All NetSuite communication should pass through:

NetSuiteClient

No module may call requests.get() directly.

---

# Logging

Log

* Authentication
* Sync Start
* Sync Finish
* API Errors
* Retry Attempts
* Records Processed

Never log credentials.

---

# Performance Rules

Batch requests where possible.

Avoid unnecessary API calls.

Use pagination.

Minimize duplicate synchronization.

Analytics should never query NetSuite directly.

---

# Security Rules

Always

* Validate responses
* Validate authentication
* Handle expired tokens
* Catch HTTP errors

Never expose NetSuite errors directly to frontend users.

---

# AI Rules

AI should never receive raw NetSuite records.

Instead generate business metrics first.

Example

Good

Revenue

Profit

Top Customers

Growth

Monthly Trend

Bad

Entire Sales Order JSON

Entire Customer JSON

---

# Future Enhancements

Support

* SuiteQL
* Saved Searches
* Webhooks
* Multi-Account Sync
* Incremental Synchronization
* Change Detection
* Background Jobs

---

# Development Philosophy

ERP Pulse should be loosely coupled to NetSuite.

Only the NetSuite module understands NetSuite.

Every other module should work with normalized ERP Pulse models.

If NetSuite is replaced by another ERP in the future, only the NetSuite module should require modification.

---

# AI Assistant Instructions

When generating NetSuite-related code:

* Use the NetSuite Client.
* Follow Service → Mapper → Repository architecture.
* Never expose raw NetSuite responses.
* Store normalized data.
* Prevent duplicate synchronization.
* Handle API failures gracefully.
* Generate production-quality code.
* Follow clean architecture principles.

---

# End of NETSUITE_CONTEXT.md
