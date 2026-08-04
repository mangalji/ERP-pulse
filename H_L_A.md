ERP Pulse v2 - Architecture Blueprint (Version 1)
Vision

ERP Pulse is a Multi-Tenant AI Platform built specifically for NetSuite customers.

Ye ERP nahi hai.

Ye NetSuite ke upar intelligence layer hai.

                           AGSuite
                    (Platform Owner)

                             │
                    Super Admin Portal
                             │
────────────────────────────────────────────────────────

                     ERP Pulse Platform

────────────────────────────────────────────────────────

        Tenant A         Tenant B         Tenant C

      (Company A)      (Company B)      (Company C)

────────────────────────────────────────────────────────

Company Admin

↓

Managers

↓

Employees

↓

Customers

↓

Business Modules


Two Portals
1. AGSuite Portal

Ye sirf AGSuite use karegi.

Modules

Dashboard

Companies

Subscriptions

Feature Management

Users

Support

Analytics

Monitoring

Billing

Audit Logs

Platform Settings

Ye pura SaaS manage karega.

2. Company Portal

Har company ka alag portal.

Modules

Dashboard

NetSuite

Invoice Reader

AI Assistant

Reports

Analytics

Employees

Customers

Settings

Har company ko sirf apna data dikhega.

Core Architecture

Ab mujhe lagta hai backend kuch is tarah hona chahiye.

backend/

accounts/

core/

tenant/

subscription/

rbac/

netsuite/

ocr/

ai/

dashboard/

reports/

monitoring/

notifications/

audit/

common/

config/

Ye final structure hoga.


Responsibility of Every App
accounts

Authentication

JWT

Login

OTP

Password

Session

core

Platform level entities.

Company

Feature

Settings

Constants

Base Models

tenant

Tenant management.

Tenant

Tenant Settings

Tenant Storage

Tenant Status
subscription
Plans

Billing

Limits

Usage
rbac
Roles

Permissions

Groups

Access Control
netsuite
Connection

Sync

REST API

SuiteQL

Token

Jobs
ocr
Invoice Reader

Upload

Processing

Extraction

Validation
ai
Chat

Analytics

Planning

Tool Calling

Prompting
reports
Financial

Inventory

Sales

Exports
dashboard

Charts

KPIs

Widgets

Database Philosophy

Sabse important rule.

Every business table

Must contain

tenant_id

Example

Invoice

tenant

vendor

...

User

tenant

...

Conversation

tenant

...

Report

tenant

...

Never

Invoice

without tenant
Roles
Platform
Super Admin

Support

Sales

Developer
Company
Admin

Finance

HR

Purchase

Sales

Manager

Employee

Viewer
Feature Flags

Instead of

if plan == Enterprise

Use

Feature

↓

Enabled

Disabled

Per Tenant.

Example

OCR

AI

Reports

Monitoring

Dashboard

NetSuite
OCR Position

OCR is not a product.

OCR is

Invoice Reader

↓

Upload

↓

AI Extraction

↓

Validation

↓

Review

↓

NetSuite
AI Position

AI is not chatbot only.

AI is

Invoice Extraction

Business Analytics

Natural Language Search

Executive Insights

Recommendations
NetSuite Position

NetSuite remains

Source of Truth

ERP Pulse becomes

Intelligence Layer
