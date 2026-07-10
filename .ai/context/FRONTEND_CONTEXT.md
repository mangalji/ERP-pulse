# FRONTEND_CONTEXT.md

# ERP Pulse Frontend Development Context

Version: 1.0

---

# Purpose

This document defines the frontend architecture, UI principles, and coding conventions for ERP Pulse.

The frontend should present business insights clearly while remaining lightweight, responsive, and maintainable.

---

# Tech Stack

* React (Vite)
* Tailwind CSS
* React Router
* Axios

Future

* React Query
* Zustand
* ECharts

---

# Design Philosophy

ERP Pulse should feel like a modern enterprise SaaS application.

Inspiration:

* Stripe Dashboard
* Vercel
* Linear
* Notion
* GitHub

The interface should prioritize clarity over decoration.

---

# Application Structure

```text
src/

assets/

components/

layouts/

pages/

hooks/

services/

contexts/

utils/

routes/

constants/
```

---

# Folder Responsibilities

## pages/

Contains route-level pages.

Examples

* Dashboard
* Customers
* Items
* Sales Orders
* Reports
* Login

---

## components/

Reusable UI components.

Examples

* Sidebar
* Navbar
* KPI Card
* Chart Card
* Data Table
* Modal
* Button
* Loader

---

## services/

Contains API communication only.

Examples

* authService
* customerService
* dashboardService
* analyticsService

Business calculations must never exist here.

---

## hooks/

Reusable React hooks.

Examples

* useAuth
* useDashboard
* useCustomers

---

# Dashboard Philosophy

The dashboard should answer:

"How is the business performing today?"

Primary KPI Cards:

* Business Health Score
* Revenue
* Profit
* Orders
* Customers
* Average Order Value

Charts:

* Revenue Trend
* Profit Trend
* Top Customers
* Top Products
* Monthly Growth

---

# Component Rules

Components should:

* Be reusable
* Be small
* Have a single responsibility

Avoid large components.

Split when necessary.

---

# State Management

Local state:

React Hooks

Global state:

Context API

Future:

Zustand

Do not overuse global state.

---

# API Communication

All HTTP requests should pass through service files.

Never call Axios directly inside UI components.

Flow

```text
Page

↓

Service

↓

Backend API
```

---

# UI Rules

Use:

* Cards
* Tables
* Charts
* Badges
* Progress Indicators

Avoid:

* Long paragraphs
* Dense layouts
* Unnecessary popups

---

# Loading States

Always display:

* Skeletons
* Progress indicators
* Loading buttons

Avoid blank screens.

---

# Empty States

Every data page should provide:

* Friendly message
* Explanation
* Call-to-action

Example

"No customers synchronized yet."

Button:

"Sync NetSuite Data"

---

# Error States

Display meaningful messages.

Include retry actions whenever possible.

Never expose backend errors directly.

---

# Responsive Design

Desktop-first.

Support:

* Large Desktop
* Laptop
* Tablet

Mobile optimization is a future enhancement.

---

# Styling Rules

Use Tailwind utility classes.

Keep spacing consistent.

Use reusable utility components where possible.

Do not use inline styles unless necessary.

---

# Naming Convention

Components:

PascalCase

Examples

CustomerTable

RevenueChart

BusinessHealthCard

ExecutiveSummary

Files:

camelCase

---

# Performance

* Lazy load pages
* Avoid unnecessary re-renders
* Memoize expensive components when justified
* Minimize API requests

---

# Accessibility

* Semantic HTML
* Keyboard navigation
* Visible focus states
* Accessible labels
* Sufficient color contrast

---

# Development Philosophy

The frontend should:

* Consume APIs
* Render data
* Handle user interactions

The frontend must never contain business logic or analytics calculations.

ERP Pulse should look and behave like an enterprise analytics platform rather than a CRUD application.
