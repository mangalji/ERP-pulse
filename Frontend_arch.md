ERP Pulse v2
Frontend Architecture & UX Specification (FAS)
1. Platform Structure

Application ke 2 completely separate portals honge.

                ERP Pulse

                     │

         ┌───────────┴────────────┐

         │                        │

 AGSuite Portal             Company Portal

In dono ka login alag nahi hoga, role decide karega ki user kis portal me jayega.

2. Login Flow
User

↓

Login

↓

JWT

↓

User

↓

Tenant

↓

Role

↓

Portal Decide

↓

Redirect

Example

AGSuite Super Admin

↓

/platform

Example

ABC Company Admin

↓

/workspace
3. AGSuite Portal
Sidebar
Dashboard

Companies

Subscriptions

Modules

Users

Usage Analytics

Support

Audit Logs

Billing

Platform Settings
Dashboard

Widgets

Total Companies

Total Users

Monthly Revenue

OCR Requests

AI Requests

API Calls

Storage Usage

NetSuite Connections

Active Sessions

System Health
Companies Page

Table

Company

Plan

Users

Storage

OCR

AI

NetSuite

Status

Actions

Action

View

Edit

Suspend

Login As Company

Upgrade Plan
Company Details

Tabs

Overview

Users

Modules

Usage

NetSuite

OCR

AI

Audit

Billing
4. Company Portal

Sidebar

Dashboard

Invoice Reader

AI Assistant

Reports

Analytics

Employees

Customers

NetSuite

Settings
Dashboard

Widgets

Today's Revenue

Invoices

Pending OCR

NetSuite Sync

Recent Activity

Employees

Top Vendors

Alerts
5. Invoice Reader

This will become the flagship module.

Layout

-----------------------------------------------------

Invoice Reader

-----------------------------------------------------

Upload

History

Review

Exports

-----------------------------------------------------
Upload Screen
----------------------------------------

Drop PDF/Image Here

or

Select Files

----------------------------------------

Supported

PDF

PNG

JPEG

WEBP

----------------------------------------

Upload

----------------------------------------
Upload Progress
invoice1.pdf

██████████

100%

Completed

----------------------------------

invoice2.pdf

█████░░░░░

45%

Processing
Processing Queue
Queued

Processing

Completed

Failed
Results Table
Invoice

Vendor

Date

Amount

Status

Confidence

Review

Action
Invoice Details

Tabs

Overview

Line Items

JSON

Validation

History
Overview
Invoice Number

Vendor

GST

Date

Currency

Subtotal

Tax

Total
Line Items
Description

Qty

Rate

GST

Amount

Spreadsheet style.

JSON Viewer

Developer mode.

Pretty JSON.

Copy JSON.

Download JSON.

Validation

Example

Invoice Number

✔

Vendor

✔

GST

Missing

Total

Mismatch
Review

Low confidence fields

Yellow

Missing fields

Red

Correct fields

Green

Editable

AI Assistant

ChatGPT style.

Left

Conversation History

Right

Chat

Example

Show invoices pending approval.

-----------------------------------

Explain purchase trend.

-----------------------------------

Which vendor generated highest expenses?
Reports

Cards

Financial

Purchase

Vendor

Customer

Inventory

Executive

Export

PDF

Excel

CSV
Employees

Table

Name

Role

Department

Status

Actions
Customers

Same.

NetSuite

Tabs

Connection

Sync

Jobs

Logs

Settings
Settings

Tabs

Company

Users

Roles

Permissions

Modules

Notifications
Notifications

Bell icon.

Unread.

Archive.

Search.

Profile

Avatar

↓

My Profile

↓

Preferences

↓

Logout

Responsive

Desktop first.

Tablet.

Mobile.

Theme

Support

Light

Dark

System

Component Structure
Layout

Sidebar

Header

Breadcrumb

Content

Footer
Shared Components
DataTable

SearchBox

FilterPanel

Modal

Drawer

Confirmation Dialog

Loader

Progress

StatusBadge

ChartCard

StatCard

EmptyState

ErrorState

No duplicate UI.

Design Language

Modern SaaS.

Simple.

Minimal.

Professional.

Inspired by

Notion
Linear
Stripe Dashboard
Vercel
GitHub
Zoho
Microsoft 365 Admin

Not copied, but similar design philosophy:

Clean spacing
Consistent typography
Reusable components
Information density where needed
Navigation Rules

Maximum

3 Click Rule

Any feature

Within

3 clicks.

Color Meaning
Green

Success

Blue

Information

Orange

Warning

Red

Critical
UX Rules

Every long task

Shows progress.

Every destructive action

Shows confirmation.

Every error

Shows solution.

Every empty page

Shows CTA.