# AI_CONTEXT.md

# ERP Pulse

## AI Business Intelligence Context

Version: 1.0

---

# Purpose

This document defines the AI architecture, responsibilities, behavior, prompt engineering strategy, and implementation rules for ERP Pulse.

ERP Pulse uses AI to explain business performance, identify trends, detect risks, and generate executive recommendations.

AI is **an assistant**, not the source of truth.

---

# AI Philosophy

ERP Pulse follows one principle:

> **Facts come from analytics. Explanations come from AI.**

Never ask AI to calculate business metrics.

Always calculate them using the Analytics Engine.

AI should explain those metrics.

---

# AI Responsibilities

The AI layer is responsible for:

* Executive Summary
* Business Insights
* Trend Explanation
* Profit Analysis
* Customer Analysis
* Product Analysis
* Risk Detection
* Business Recommendations
* Monthly Business Summary

---

# AI Must NOT

AI must never:

* Calculate revenue
* Calculate profit
* Calculate taxes
* Calculate growth
* Query NetSuite
* Query PostgreSQL
* Guess missing values
* Invent business facts

Those responsibilities belong to the Analytics Engine.

---

# AI Architecture

```text id="eik4j7"
NetSuite

↓

Synchronization

↓

PostgreSQL

↓

Analytics Engine

↓

Structured Metrics

↓

AI Engine

↓

Executive Report
```

---

# Input Philosophy

AI receives structured business metrics.

Never raw ERP records.

---

# Correct Input

```json id="g0w8jd"
{
  "revenue": 4820000,
  "profit": 874000,
  "growth": 14,
  "top_customers": [],
  "top_products": [],
  "monthly_orders": 421
}
```

---

# Incorrect Input

Entire

Customer JSON

Sales Order JSON

Invoice JSON

Database Records

Never send large ERP payloads.

---

# AI Workflow

```text id="epxg1v"
Analytics

↓

Input Validator

↓

Prompt Builder

↓

LLM

↓

JSON Validator

↓

Response Parser

↓

Repository

↓

Dashboard
```

---

# AI Layers

ERP Pulse AI consists of:

Business Summary Engine

Trend Analysis Engine

Recommendation Engine

Risk Analysis Engine

Forecast Engine (Future)

Chat Assistant (Future)

---

# Business Summary Engine

Generate:

* Executive Summary
* Monthly Summary
* Quarterly Summary

Example

Revenue increased by 14% compared to last month.

Top customer contributed 31% of total sales.

Overall business performance is healthy.

---

# Trend Analysis Engine

Explain:

* Revenue Trends
* Profit Trends
* Customer Trends
* Product Trends

Never calculate.

Only explain.

---

# Recommendation Engine

Generate recommendations such as:

* Increase inventory
* Contact inactive customers
* Promote high-margin products
* Reduce slow-moving inventory
* Focus on high-performing regions

Recommendations must always be supported by data.

---

# Risk Analysis Engine

Identify:

* Declining sales
* Falling profit
* Customer inactivity
* Low inventory
* Concentrated revenue risk

Explain why the risk exists.

---

# Prompt Philosophy

Prompts should:

* Be deterministic
* Be structured
* Be short
* Be reusable

Avoid conversational prompts.

---

# Prompt Structure

Role

↓

Context

↓

Business Metrics

↓

Task

↓

Output Format

---

# Example Prompt Flow

System

"You are an ERP business analyst."

↓

Context

"This data comes from NetSuite."

↓

Business Metrics

Revenue

Profit

Growth

Customers

Products

↓

Task

Generate executive insights.

↓

Output

JSON

---

# Output Rules

AI must always return JSON.

Never markdown.

Never HTML.

Never plain paragraphs.

---

# Example Response

```json id="hrl6ub"
{
  "summary": "",
  "insights": [],
  "risks": [],
  "recommendations": []
}
```

---

# Response Validation

Every AI response passes through:

JSON Validation

↓

Schema Validation

↓

Business Validation

↓

Database

Reject invalid responses.

---

# Hallucination Prevention

Never allow AI to:

Invent numbers.

Invent customers.

Invent products.

Invent revenue.

Invent percentages.

If information is unavailable:

Return

"Insufficient data."

---

# Explainability

Every recommendation should explain:

Why?

Expected impact.

Priority.

Example

Increase stock of Product A.

Reason:

Demand increased by 26%.

Priority:

High.

---

# Confidence

Future

Every recommendation should include:

Confidence Score

High

Medium

Low

---

# AI Provider

ERP Pulse should never depend on one provider.

Supported

OpenAI

Claude

Gemini

Ollama

Future Models

Always use Provider Abstraction.

---

# Token Optimization

Never send:

Entire ERP database.

Only send:

Business Metrics.

Top Customers.

Top Products.

Growth Statistics.

KPIs.

This reduces cost and improves quality.

---

# Retry Strategy

Retry

Network Failure

Timeout

Temporary API Error

Do not retry:

Validation Errors

Bad Requests

---

# Logging

Log

Prompt ID

Provider

Latency

Token Usage

Response Time

Errors

Never log:

API Keys

Sensitive customer information

---

# Security

Mask sensitive information before sending it to AI.

Avoid sending:

Email addresses

Phone numbers

Addresses

Payment information

Personally identifiable information

---

# Future AI Features

* Forecasting
* Customer Churn Prediction
* Sales Prediction
* Inventory Optimization
* AI Chat with ERP Data
* Natural Language Queries

---

# Development Philosophy

AI enhances analytics.

AI never replaces analytics.

Business decisions should always be traceable back to real business metrics.

The AI layer should improve understanding, not generate unverifiable facts.

---

# AI Assistant Instructions

When generating AI-related code:

* Consume structured analytics only.
* Never calculate business metrics.
* Always validate AI output.
* Return structured JSON.
* Keep prompts modular and reusable.
* Use provider abstraction.
* Prioritize explainability over creativity.
* Produce enterprise-grade, maintainable code.

---

# End of AI_CONTEXT.md
