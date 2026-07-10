# PROJECT_CONTEXT.md

# ERP Pulse

**Version:** 1.0

---

# Project Overview

ERP Pulse is an AI-powered Business Intelligence Platform that integrates with NetSuite and transforms ERP data into actionable business insights.

The application synchronizes business data from NetSuite, stores it in a local PostgreSQL database, performs business analytics, and generates AI-powered executive reports and recommendations.

ERP Pulse is **not** an ERP system.

ERP Pulse is an **AI Analytics Layer** built on top of NetSuite.

---

# Project Vision

Help business owners, managers, and decision-makers understand their ERP data through intelligent dashboards, analytics, and AI-generated insights.

The goal is to reduce manual reporting and enable faster business decisions.

---

# Target Users

* Business Owners
* Sales Managers
* Finance Managers
* Operations Managers
* NetSuite Administrators
* Executives

---

# Core Workflow

```text
NetSuite
      │
      ▼
REST APIs
      │
      ▼
Synchronization Layer
      │
      ▼
PostgreSQL
      │
      ▼
Business Analytics Engine
      │
      ▼
AI Intelligence Engine
      │
      ▼
Executive Dashboard
      │
      ▼
Reports & Recommendations
```

---

# Primary Features

* User Authentication
* NetSuite Integration
* Customer Synchronization
* Item Synchronization
* Sales Order Synchronization
* Business Dashboard
* Business Analytics
* AI Executive Insights
* Executive Reports
* PDF Export

---

# Technology Stack

## Backend

* Python 3.x
* Django
* Django REST Framework

## Frontend

* React (Vite)
* Tailwind CSS
* React Router
* Axios

## Database

* PostgreSQL

## Charts

* Chart.js

## AI

* OpenAI API (Provider abstraction)
* Future support for Ollama, Gemini, Claude

## Deployment

* Docker (Future)
* Nginx
* Gunicorn

---

# Architecture

The application follows a Modular Monolith architecture.

```text
React

↓

Django REST API

↓

Service Layer

↓

Repository Layer

↓

PostgreSQL
```

Business logic must remain independent of the frontend.

---

# Backend Modules

accounts

netsuite

customers

items

sales

analytics

ai

reports

common

Each module owns its own:

* Models
* Services
* Serializers
* Repositories
* URLs
* Tests

---

# NetSuite Integration

ERP Pulse never exposes NetSuite directly to the frontend.

Flow

```text
React

↓

ERP Pulse API

↓

NetSuite Client

↓

NetSuite REST API
```

The frontend must never communicate directly with NetSuite.

---

# Synchronization Strategy

ERP Pulse stores synchronized ERP data locally.

Flow

```text
NetSuite

↓

Sync Service

↓

PostgreSQL

↓

Analytics
```

Analytics should always use local database data.

Never generate dashboards directly from NetSuite API responses.

---

# Business Entities

Primary entities include:

* Users
* Customers
* Items
* Sales Orders
* Sales Order Items
* AI Insights
* Reports

Future entities may include:

* Invoices
* Purchase Orders
* Vendors
* Inventory
* Employees

---

# Analytics Engine

The Analytics Engine is responsible for calculating business metrics.

Examples:

* Revenue
* Profit
* Total Orders
* Average Order Value
* Customer Revenue
* Top Products
* Monthly Growth
* Customer Performance

The Analytics Engine should not call AI providers.

---

# AI Intelligence Engine

The AI layer consumes structured analytics rather than raw ERP data.

Input:

* Revenue metrics
* Profit metrics
* Customer statistics
* Product statistics
* Trend analysis

Output:

* Executive Summary
* Business Insights
* Trend Analysis
* Risk Analysis
* Recommendations

AI responses should always be structured and validated before being stored or returned.

---

# Dashboard Philosophy

The dashboard should answer one question:

**"How is the business performing today?"**

Primary KPI Cards:

* Business Health Score
* Revenue
* Profit
* Orders
* Customers
* Average Order Value

Supporting visualizations:

* Revenue Trend
* Profit Trend
* Top Customers
* Top Products
* Monthly Growth

---

# Backend Development Rules

Business logic belongs in Services.

Database operations belong in Repositories.

Views should:

* Validate requests
* Call Services
* Return Responses

Views must not contain business logic.

---

# Frontend Development Rules

Frontend should remain presentation-focused.

Responsibilities:

* API Calls
* State Management
* Rendering UI
* User Interaction

Business calculations must never be performed in React.

---

# API Standards

Base URL

/api/v1/

Authentication

JWT

Response Format

```json
{
  "success": true,
  "message": "",
  "data": {}
}
```

Every endpoint should:

* Validate input
* Return meaningful errors
* Follow REST conventions

---

# Coding Standards

General

* Follow PEP 8
* Use type hints where practical
* Use meaningful variable names
* Keep functions small and focused
* Prefer composition over duplication

Python

* Avoid business logic inside models
* Avoid long views
* Keep services reusable

React

* Use functional components
* Reusable UI components
* Avoid duplicated code

---

# Security Principles

* JWT Authentication
* HTTPS in production
* Validate every request
* Validate uploaded files
* Never expose secrets
* Store secrets in environment variables

---

# Performance Principles

* Query local PostgreSQL instead of NetSuite for analytics.
* Minimize unnecessary database queries.
* Optimize ORM usage.
* Prepare the architecture for caching in future versions.

---

# Non-Goals

ERP Pulse is NOT intended to:

* Replace NetSuite
* Modify ERP business processes
* Manage accounting
* Replace ERP transactions

Its purpose is analytics, reporting, and business intelligence.

---

# Development Philosophy

ERP Pulse should be built as if it were an enterprise SaaS product.

Every feature should prioritize:

* Maintainability
* Scalability
* Readability
* Modularity
* Reusability
* Security

Code quality is more important than rapid implementation.

---

# AI Assistant Instructions

When generating code for ERP Pulse:

* Follow the architecture defined in this document.
* Respect the Service Layer and Repository Pattern.
* Do not place business logic inside Views or React components.
* Generate production-quality code.
* Avoid unnecessary dependencies.
* Write clean, modular, and maintainable code.
* If requirements are unclear, ask for clarification instead of making assumptions.

---

# End of PROJECT_CONTEXT.md
