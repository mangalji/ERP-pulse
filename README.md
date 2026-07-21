# ERP Pulse

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-5.x-green)
![DRF](https://img.shields.io/badge/DRF-REST-red)
![Status](https://img.shields.io/badge/Status-Under%20Development-orange)
![License](https://img.shields.io/badge/License-Private-lightgrey)

ERP Pulse is a backend platform built with **Django** that integrates with ERP systems to provide a unified interface for accessing business data.

The long-term vision of ERP Pulse is to become a centralized ERP integration platform where users can connect multiple ERP systems (NetSuite, SAP, Zoho, Tally, QuickBooks, Microsoft Dynamics, etc.) from a single application.

Currently, Oracle NetSuite integration is under active development.

---

# Live Demo

[https://erp-pulse-gamma.vercel.app/](https://erp-pulse-gamma.vercel.app/)

---

# Features

## Current Features

- OAuth 2.0 Authentication with Oracle NetSuite
- Multiple NetSuite Account Support
- Automatic Access Token Refresh
- REST Record API Integration
- SuiteQL Query Support
- Connection Management
- Layered Architecture
- Repository Pattern
- Service-Oriented Design

Supported NetSuite Records:

- Customers
- Employees
- Vendors
- Items
- Sales Orders
- Purchase Orders
- Invoices

---

# Project Architecture

The backend follows a layered architecture.

```
                APIView
                   │
                   ▼
               Service Layer
                   │
                   ▼
            Repository Layer
                   │
                   ▼
               Database Models

                   │

           NetSuite Client Layer
                   │
                   ▼
             Oracle NetSuite APIs
```

Responsibilities

### Views

- Authentication
- Request validation
- Response formatting

No business logic.

---

### Services

Responsible for business logic.

Examples:

- OAuth Flow
- Token Refresh
- Connection Management
- Business Rules

---

### Repository

Responsible only for database operations.

Examples:

- CRUD
- Transactions
- Queries

No HTTP communication.

---

### Client

Responsible only for communication with NetSuite.

Examples:

- OAuth Token Exchange
- Token Refresh
- REST API Requests
- SuiteQL Requests

---

# Current Architecture

Each ERP Pulse user can connect multiple NetSuite accounts.

```
User

├── NetSuite Connection A

├── NetSuite Connection B

└── NetSuite Connection C
```

Only one connection is active at a time.

Each connection stores:

- Client Name
- Environment
- Account ID
- Client ID
- Client Secret
- OAuth Tokens
- Connection Status

---

# Tech Stack

Backend

- Python
- Django
- Django REST Framework

Database

- PostgreSQL (planned / configurable)

Authentication

- JWT
- OAuth 2.0 Authorization Code Flow

External APIs

- Oracle NetSuite REST API
- NetSuite SuiteQL

---

# API Modules

Current backend includes:

```
accounts/
common/
netsuite/
```

The NetSuite module contains:

- OAuth
- Client
- Services
- Repository
- Models
- Views
- Serializers

---

# Current Progress

Backend

- Models
- Repository
- OAuth
- Client
- Services

Mostly completed.

Current focus:

- Connection CRUD APIs
- Integration Testing
- Frontend Integration

Overall backend completion:

Approximately **98%**

---

# Roadmap

Upcoming Features

## Backend

- Background Sync
- Celery
- Redis
- Scheduled Jobs
- Audit Logs
- Token Encryption

## Frontend

- Connection Manager
- Dashboard
- Reports
- ERP Explorer

## Future ERP Integrations

- SAP
- Zoho
- Tally
- QuickBooks
- Microsoft Dynamics

---

# Deployment

- Frontend: Vercel
- Backend API (for developers): [https://erp-pulse-backend.onrender.com](https://erp-pulse-backend.onrender.com)

---

# Project Documentation

Additional project documentation is available.

| File | Description |
|------|-------------|
| PROJECT_MEMORY.md | Complete project context, architecture decisions, current progress and future plans |
| CHANGELOG.md | History of major development milestones and refactors |

---

# Development Status

Current milestone:

**Multi-Account NetSuite Integration**

Status:

🟡 In Progress

Remaining work:

- Complete Connection CRUD APIs
- End-to-End Testing
- Frontend Integration

---

# Design Principles

The project follows these principles:

- Thin Views
- Service-Oriented Architecture
- Repository Pattern
- Separation of Concerns
- Connection-based OAuth
- Scalable Multi-ERP Design

---

# Long-Term Vision

ERP Pulse aims to evolve into a complete ERP aggregation platform.

```
User

        │

        ▼

ERP Pulse

        │

 ┌──────┼────────┬────────┬────────┐

 ▼      ▼        ▼        ▼        ▼

NetSuite SAP    Zoho    Tally   Dynamics
```

Users will be able to manage multiple ERP systems from a single dashboard without switching between different ERP applications.

---

# License

This project is currently under active development.