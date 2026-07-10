# DATABASE_CONTEXT.md

# ERP Pulse

## Database Development Context

Version: 1.0

---

# Purpose

This document defines the database architecture, entity relationships, naming conventions, and database rules for ERP Pulse.

It is intended for AI coding assistants and developers implementing backend features.

This is **not** the detailed database design document.

---

# Database Philosophy

ERP Pulse stores a normalized analytical copy of NetSuite ERP data.

NetSuite remains the **Source of Truth**.

ERP Pulse stores synchronized data for:

* Analytics
* Reporting
* AI Insights

ERP Pulse should never replace NetSuite.

---

# Database Engine

PostgreSQL

---

# Naming Convention

Tables

snake_case

Examples

customer

item

sales_order

sales_order_item

Columns

snake_case

Examples

customer_id

created_at

updated_at

deleted_at

Foreign Keys

entity_id

Examples

customer_id

item_id

sales_order_id

---

# Primary Keys

Preferred

UUID

MVP

Auto Increment Integer (acceptable)

---

# Audit Columns

Every table should contain:

* created_at
* updated_at

Optional

* deleted_at
* created_by
* updated_by

---

# Core Entities

```text id="yt2l4o"
User

↓

Customer

↓

Sales Order

↓

Sales Order Item

↓

Item

↓

Analytics Snapshot

↓

AI Insight

↓

Report
```

---

# Entity Ownership

## Accounts Module

Owns

* User

---

## Customers Module

Owns

* Customer

---

## Items Module

Owns

* Item

---

## Sales Module

Owns

* Sales Order
* Sales Order Item

---

## Analytics Module

Owns

* Analytics Snapshot

---

## AI Module

Owns

* AI Insight

---

## Reports Module

Owns

* Report

---

# Customer Entity

Purpose

Represents a NetSuite customer.

Store

* NetSuite Internal ID
* Entity ID
* Company Name
* Email
* Phone
* Currency
* Status

Never use customer name as a unique identifier.

Always use NetSuite Internal ID.

---

# Item Entity

Purpose

Represents products or services.

Store

* NetSuite Internal ID
* Item Name
* SKU
* Category
* Unit Price
* Cost
* Status

---

# Sales Order Entity

Purpose

Represents a sales transaction.

Store

* NetSuite Internal ID
* Transaction Number
* Customer
* Order Date
* Status
* Total
* Currency

Relationship

One Customer

↓

Many Sales Orders

---

# Sales Order Item

Purpose

Represents line items inside a Sales Order.

Store

* Sales Order
* Item
* Quantity
* Rate
* Amount
* Tax

Relationship

One Sales Order

↓

Many Sales Order Items

---

# Analytics Snapshot

Purpose

Stores calculated business metrics.

Examples

Revenue

Profit

Monthly Growth

Average Order Value

Top Customers

Top Products

AI should consume this table rather than raw transactional data whenever appropriate.

---

# AI Insight

Purpose

Stores AI-generated business insights.

Examples

Executive Summary

Recommendations

Trend Analysis

Risk Analysis

Do not overwrite historical insights.

Each generation should create a new record.

---

# Report

Purpose

Stores generated business reports.

Examples

Monthly Report

Customer Report

Executive Report

Product Report

Store metadata only.

Generated PDF files should be stored separately.

---

# Relationships

```text id="mbw40d"
User

↓

Customer

↓

Sales Order

↓

Sales Order Item

↓

Item

Analytics Snapshot

↓

AI Insight

↓

Report
```

---

# Synchronization Rules

Synchronization should:

Insert new records.

Update existing records.

Never create duplicates.

Never delete historical analytical data.

Use NetSuite Internal ID to identify records.

---

# Deletion Strategy

Transactional data synchronized from NetSuite should not be permanently deleted.

Preferred approach

Soft Delete

using

deleted_at

---

# Database Constraints

Examples

Customer

NetSuite Internal ID must be unique.

Item

NetSuite Internal ID must be unique.

Sales Order

Transaction Number should be unique.

---

# Indexing

Create indexes for:

* NetSuite Internal ID
* Customer ID
* Item ID
* Sales Order ID
* Order Date
* Status

Future

Composite indexes for reporting queries.

---

# Transactions

Use database transactions for:

* Synchronization
* Bulk Imports
* Report Generation
* AI Insight Persistence

Rollback on failure.

---

# Data Integrity

Always validate:

* Foreign Keys
* Required Fields
* Duplicate Records
* Invalid Status Values

Never trust external API responses.

---

# Performance Rules

Dashboard queries should never scan entire transaction tables.

Use:

* Aggregation
* Indexes
* Materialized summaries (future)

Analytics should be optimized for read performance.

---

# Security Rules

Never store:

* NetSuite credentials
* API secrets
* Authentication tokens

Sensitive values belong in environment variables.

---

# Future Entities

Planned additions

* Invoice
* Payment
* Purchase Order
* Vendor
* Inventory
* Employee
* Location
* Subsidiary
* Warehouse

The schema should support future expansion without major redesign.

---

# Development Philosophy

ERP Pulse follows a normalized database design.

Transactional ERP data and analytical data should remain logically separated.

Every table should have a single responsibility.

Avoid duplicate storage whenever possible.

Design for maintainability before optimization.

---

# AI Assistant Instructions

When generating database-related code:

* Follow normalized design principles.
* Respect entity ownership.
* Use repositories for database access.
* Never place SQL inside Views.
* Prevent duplicate synchronization.
* Use transactions for bulk operations.
* Preserve historical analytical data.
* Write scalable and maintainable database code.

---

# End of DATABASE_CONTEXT.md
