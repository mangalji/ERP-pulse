# AGSuite ERP - Zoho Catalyst Deployment Guide

This guide details step-by-step instructions to deploy the AGSuite ERP application to **Zoho Catalyst** using **AppSail** (for the Django backend) and **Catalyst Web Client** (for the React frontend).

---

## Architecture Overview

- **Backend**: Python 3.12 / Django REST Framework running on Zoho Catalyst AppSail container service (`agsuite-backend`).
- **Frontend**: React 18 / Vite 8 static build hosted on Catalyst Web Client.
- **Database**: PostgreSQL / Supabase connected via secure SSL connection string.

---

## Deployment Steps

### STEP 1: CLI Installation
Ensure the Zoho Catalyst CLI is installed globally:
```bash
npm install -g zcatalyst-cli
```

### STEP 2: Authentication
Log in to your Zoho Catalyst account:
```bash
catalyst login
```
*(Verify account with `catalyst whoami`)*

### STEP 3: Associate Catalyst Project
From the root directory of the AGSuite ERP codebase (`AGSuite-ERP/`), initialize or link your Zoho Catalyst project:
```bash
catalyst project:use <your-catalyst-project-name-or-id>
```
Or run `catalyst init` to link your local project resources.

### STEP 4: Configure AppSail Service (If not already linked)
If `agsuite-backend` AppSail service is not initialized in the console:
```bash
catalyst appsail:add
```
Select the following options:
- **Feature**: AppSail
- **Runtime**: Catalyst-Managed Runtime
- **Stack**: Python 3.12
- **Source Path**: `backend/`
- **Service Name**: `agsuite-backend`

*(The repository already contains `catalyst.json` at root and `backend/app-config.json` pre-configured for Python 3.12 and Gunicorn)*

---

### STEP 5: Set Production Environment Variables
In the **Zoho Catalyst Console**:
1. Navigate to **AppSail** -> **agsuite-backend** -> **Environment Variables**.
2. Add the following environment variables (refer to `backend/.env.example`):

| Variable Name | Description / Example Value |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `SECRET_KEY` | Generate a strong secret key string |
| `DEBUG` | `False` |
| `DJANGO_DEBUG` | `False` |
| `DATABASE_URL` | `postgresql://user:password@host:5432/dbname?sslmode=require` |
| `FIELD_ENCRYPTION_KEY` | Fernet key for NetSuite data encryption |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,agsuite-backend-<org>.catalystappsail.com` |
| `CORS_ALLOWED_ORIGINS` | `https://agsuite-erp-<org>.catalystserverless.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://agsuite-erp-<org>.catalystserverless.com` |
| `FRONTEND_URL` | `https://agsuite-erp-<org>.catalystserverless.com` |
| `JWT_AUTH_COOKIE_SAMESITE` | `None` |
| `JWT_AUTH_COOKIE_SECURE` | `True` |
| `SECURE_SSL_REDIRECT` | `True` |
| `NETSUITE_REDIRECT_URI` | `https://agsuite-backend-<org>.catalystappsail.com/api/v1/netsuite/callback/` |
| `AI_PROVIDER` | `gemini` (or `openai`) |
| `GEMINI_API_KEY` | Your Gemini API Key |
| `GEMINI_MODEL` | `gemini-2.5-flash` |

---

### STEP 6: Deploy Django Backend to AppSail
From the root directory, run:
```bash
catalyst deploy appsail
```
The CLI will build the Python container, run `collectstatic`, start Gunicorn, and output your live AppSail URL.

---

### STEP 7: Retrieve Deployed AppSail Backend Endpoint
Copy the live AppSail backend URL provided by the CLI output.
Example:
`https://agsuite-backend-100800000.catalystappsail.com`

---

### STEP 8: Configure Frontend API Base URL
Create or update `frontend/.env.production` (or supply during build):
```env
VITE_API_BASE_URL=https://agsuite-backend-100800000.catalystappsail.com/api/v1
```

---

### STEP 9: Build React Frontend
Navigate to the `frontend/` directory and create the production build:
```bash
cd frontend
npm run build
```
Verify that `frontend/dist/` contains the generated static assets.

---

### STEP 10: Deploy React Frontend to Catalyst Web Client
From the root directory, deploy the web client assets:
```bash
catalyst deploy client
```

---

### STEP 11: Final Origin Synchronization
Return to **Zoho Catalyst Console** -> **AppSail** -> **agsuite-backend** -> **Environment Variables**, and confirm:
- `CORS_ALLOWED_ORIGINS` includes your live frontend domain.
- `CSRF_TRUSTED_ORIGINS` includes your live frontend domain.

---

### STEP 12: Verification
1. Open your deployed Catalyst frontend URL in the browser.
2. Verify API authentication (`/api/v1/auth/me/`).
3. Verify static files and assets load correctly.
