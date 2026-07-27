# ERP Pulse - Production Deployment Checklist

This document provides a comprehensive checklist for deploying the ERP Pulse application to production. It covers both backend (Django) and frontend (React/Vite) deployments.

---

## 📋 Pre-Deployment Requirements

### Infrastructure Prerequisites
- [ ] **PostgreSQL Database** (Neon, Supabase, AWS RDS, or self-hosted)
- [ ] **Redis** (for caching, sessions, Celery - optional but recommended)
- [ ] **Object Storage** (AWS S3, Cloudflare R2, or similar for static/media files)
- [ ] **SSL Certificate** (Let's Encrypt or managed by platform)
- [ ] **Domain Name** configured with DNS

### Required Accounts & Services
- [ ] **NetSuite Account** with Integration record (Auth Code Grant enabled)
- [ ] **AI Provider API Key** (OpenAI or Google Gemini)
- [ ] **Email Service** (SendGrid, Mailgun, Postmark, or SMTP credentials)
- [ ] **Error Tracking** (Sentry, optional but recommended)
- [ ] **Monitoring** (Datadog, New Relic, or platform-native)

---

## 🔐 Environment Variables

### Backend (Django) - Required

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `SECRET_KEY` | Django secret key (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`) | `django-insecure-xyz...` | ✅ |
| `DEBUG` | Set to `False` in production | `False` | ✅ |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `api.yourdomain.com,yourdomain.com` | ✅ |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/dbname` | ✅ |
| `FIELD_ENCRYPTION_KEY` | Fernet key for encrypting NetSuite tokens at rest. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | `base64-encoded-key` | ✅ |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | Access token lifetime | `15` | ⚠️ |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Refresh token lifetime | `7` | ⚠️ |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins | `https://yourdomain.com,https://www.yourdomain.com` | ✅ |
| `FRONTEND_URL` | Frontend base URL (for redirects) | `https://yourdomain.com` | ✅ |
| `NETSUITE_REDIRECT_URI` | NetSuite OAuth callback URL | `https://api.yourdomain.com/api/v1/netsuite/callback/` | ✅ |
| `OPENAI_API_KEY` | OpenAI API key (or use Gemini) | `sk-...` | ⚠️ |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o-mini` | ⚠️ |
| `AI_PROVIDER` | AI provider: `openai` or `gemini` | `openai` | ⚠️ |
| `GEMINI_API_KEY` | Google Gemini API key (if using Gemini) | `...` | ⚠️ |
| `GEMINI_MODEL` | Gemini model to use | `gemini-2.5-flash` | ⚠️ |

### Backend - Email Configuration (Required for Production)

| Variable | Description | Example |
|----------|-------------|---------|
| `EMAIL_HOST` | SMTP server hostname | `smtp.sendgrid.net` |
| `EMAIL_PORT` | SMTP port (usually 587) | `587` |
| `EMAIL_HOST_USER` | SMTP username | `apikey` |
| `EMAIL_HOST_PASSWORD` | SMTP password/API key | `SG.xxx...` |
| `EMAIL_USE_TLS` | Use TLS | `True` |
| `EMAIL_TIMEOUT` | Connection timeout (seconds) | `10` |
| `DEFAULT_FROM_EMAIL` | Default sender address | `noreply@yourdomain.com` |

### Backend - Optional/Advanced

| Variable | Description | Default |
|----------|-------------|---------|
| `SECURE_HSTS_SECONDS` | HSTS max-age (set to 31536000 for 1 year after testing) | `0` |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Include subdomains in HSTS | `True` |
| `SECURE_HSTS_PRELOAD` | Enable HSTS preload | `True` |
| `SESSION_COOKIE_SECURE` | Secure session cookies | `True` |
| `CSRF_COOKIE_SECURE` | Secure CSRF cookies | `True` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF | Same as CORS_ALLOWED_ORIGINS |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DJANGO_DB_LOG_LEVEL` | Database query logging | `WARNING` |
| `MONITORING_LOG_LEVEL` | Monitoring app log level | `INFO` |
| `THROTTLE_ANON` | Anonymous user rate limit | `100/min` |
| `THROTTLE_USER` | Authenticated user rate limit | `1000/min` |
| `THROTTLE_LOGIN_OTP` | Login OTP rate limit | `5/min` |
| `THROTTLE_REGISTER_OTP` | Register OTP rate limit | `5/min` |
| `THROTTLE_AI_CHAT` | AI chat rate limit | `20/min` |
| `THROTTLE_DASHBOARD` | Dashboard rate limit | `120/min` |
| `THROTTLE_NETSUITE_SYNC` | NetSuite sync rate limit | `30/min` |

### Frontend (Vite/React) - Required

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API base URL | `https://api.yourdomain.com/api/v1` |

---

## 🏗️ Backend Deployment Steps

### 1. Prepare the Codebase
```bash
# Ensure all migrations are created
cd backend
python manage.py makemigrations --check

# Collect static files (test locally first)
python manage.py collectstatic --noinput --dry-run
```

### 2. Database Setup
```bash
# Run migrations on production database
python manage.py migrate --settings=config.settings.production

# Create superuser (optional, for admin access)
python manage.py createsuperuser --settings=config.settings.production
```

### 3. Static Files
```bash
# Collect static files for production
python manage.py collectstatic --noinput --settings=config.settings.production
```

### 4. Verify Configuration
```bash
# Run Django system checks
python manage.py check --deploy --settings=config.settings.production

# Test database connection
python manage.py dbshell --settings=config.settings.production
```

### 5. Gunicorn Configuration
Create `gunicorn.conf.py`:
```python
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 5
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

### 6. Run with Gunicorn
```bash
gunicorn config.wsgi:application -c gunicorn.conf.py --settings=config.settings.production
```

---

## 🎨 Frontend Deployment Steps

### 1. Build for Production
```bash
cd frontend
npm ci  # Clean install
npm run build
```

### 2. Verify Build Output
```bash
# Check build output
ls -la dist/
# Should contain: index.html, assets/ (JS, CSS)
```

### 3. Deploy Static Files
Deploy the `dist/` folder to your static hosting:
- **Vercel**: Connect repo, set build command `npm run build`, output directory `dist`
- **Netlify**: Same as Vercel
- **Cloudflare Pages**: Build command `npm run build`, output `dist`
- **AWS S3 + CloudFront**: Sync `dist/` to S3 bucket
- **Nginx**: Copy `dist/` to `/var/www/html/`

### 4. Configure SPA Routing
Ensure your web server handles client-side routing:

**Nginx:**
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

**Vercel/Netlify/Cloudflare Pages:** Automatic via `_redirects` or config.

---

## 🔗 NetSuite Integration Setup

### 1. Create NetSuite Integration Record
1. Go to **Setup > Integration > Manage Integrations > New**
2. Name: `ERP Pulse`
3. Enable **Auth Code Grant**
4. Note down: **Client ID**, **Client Secret**
5. Set **Redirect URI** to match `NETSUITE_REDIRECT_URI` env var
6. Save and note the **Account ID**

### 2. Configure Scopes
Required scopes for the integration:
- `rest_webservices` (or specific record-type scopes)
- `user_access_token` (for token refresh)

### 3. Test Connection
After deployment, use the "Connect NetSuite" page in the frontend to initiate OAuth flow.

---

## 🤖 AI Provider Setup

### Option A: OpenAI
1. Get API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Set `OPENAI_API_KEY` and `AI_PROVIDER=openai`

### Option B: Google Gemini
1. Get API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set `GEMINI_API_KEY` and `AI_PROVIDER=gemini`

---

## 📧 Email Service Setup

### SendGrid Example
1. Create SendGrid account
2. Verify sender domain
3. Create API key with "Mail Send" permissions
4. Set environment variables:
   - `EMAIL_HOST=smtp.sendgrid.net`
   - `EMAIL_PORT=587`
   - `EMAIL_HOST_USER=apikey`
   - `EMAIL_HOST_PASSWORD=SG.your-api-key`
   - `DEFAULT_FROM_EMAIL=noreply@yourdomain.com`

---

## 🔒 Security Hardening Checklist

### Django Settings
- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` is strong and unique
- [ ] `ALLOWED_HOSTS` only includes production domains
- [ ] `SECURE_HSTS_SECONDS = 31536000` (after testing)
- [ ] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- [ ] `SECURE_HSTS_PRELOAD = True`
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] `SECURE_SSL_REDIRECT = True` (if not handled by proxy)
- [ ] `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- [ ] `CORS_ALLOWED_ORIGINS` only includes production frontend URLs
- [ ] `CSRF_TRUSTED_ORIGINS` matches CORS origins

### Database
- [ ] Use connection pooling (PgBouncer for PostgreSQL)
- [ ] Enable SSL for database connections
- [ ] Regular automated backups configured
- [ ] Read replica for reporting queries (optional)

### Network
- [ ] Application behind load balancer/reverse proxy
- [ ] WAF configured (Cloudflare, AWS WAF, etc.)
- [ ] Rate limiting on API endpoints
- [ ] Private network for database/Redis

---

## 📊 Monitoring & Observability

### Health Checks
- [ ] `/api/v1/monitoring/health/` endpoint accessible
- [ ] Load balancer health check configured
- [ ] Database connection health check

### Logging
- [ ] Structured JSON logging enabled
- [ ] Log aggregation (ELK, Datadog, CloudWatch, etc.)
- [ ] Error alerting (Sentry, PagerDuty, etc.)
- [ ] Audit logging for sensitive operations

### Metrics
- [ ] Request latency (p50, p95, p99)
- [ ] Error rates by endpoint
- [ ] Database query performance
- [ ] Cache hit rates
- [ ] Background job queue depth

---

## 🚀 Deployment Pipeline (CI/CD)

### GitHub Actions Example
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          python manage.py test --settings=config.settings.testing
      - name: Run migrations
        run: |
          cd backend
          python manage.py migrate --settings=config.settings.production
      - name: Collect static
        run: |
          cd backend
          python manage.py collectstatic --noinput --settings=config.settings.production
      - name: Deploy to server
        # Use your deployment method (SSH, Docker, etc.)

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Build
        run: |
          cd frontend
          npm run build
      - name: Deploy
        # Deploy dist/ to static hosting
```

---

## ✅ Post-Deployment Verification

### Backend
- [ ] Health endpoint returns 200: `GET /api/v1/monitoring/health/`
- [ ] Admin panel accessible: `GET /admin/`
- [ ] API docs accessible (if using drf-spectacular)
- [ ] Authentication flow works (register → OTP → login → OTP → JWT)
- [ ] NetSuite OAuth callback works
- [ ] AI chat responds correctly
- [ ] Background jobs process (if using Celery)

### Frontend
- [ ] Application loads without console errors
- [ ] Login/Register flows work end-to-end
- [ ] Protected routes redirect to login when unauthenticated
- [ ] Dashboard loads data from API
- [ ] NetSuite connection flow works
- [ ] AI Assistant responds
- [ ] All navigation works (no 404s on refresh)

### Integration
- [ ] CORS headers correct on API responses
- [ ] Cookies/tokens work across subdomains (if applicable)
- [ ] Email delivery works (test registration, password reset)
- [ ] File uploads work (if applicable)

---

## 🔄 Rollback Plan

### Backend Rollback
```bash
# 1. Revert to previous Docker image / code version
# 2. Run migrations in reverse (if needed)
python manage.py migrate app_name previous_migration --settings=config.settings.production

# 3. Restart Gunicorn
systemctl restart gunicorn  # or your process manager
```

### Frontend Rollback
```bash
# 1. Revert to previous build in static hosting
# 2. Invalidate CDN cache
# 3. Verify old version loads
```

### Database Rollback
- [ ] Point-in-time recovery tested
- [ ] Migration reversal scripts prepared for critical migrations

---

## 📞 Emergency Contacts

| Role | Name | Contact | Escalation |
|------|------|---------|------------|
| Primary On-Call | | | 1st |
| Secondary On-Call | | | 2nd |
| Database Admin | | | 3rd |
| NetSuite Admin | | | As needed |

---

## 📝 Deployment Sign-Off

| Checklist Item | Verified By | Date | Notes |
|----------------|-------------|------|-------|
| Environment variables configured | | | |
| Database migrations applied | | | |
| Static files collected | | | |
| SSL certificates valid | | | |
| DNS records correct | | | |
| Health checks passing | | | |
| Monitoring alerts configured | | | |
| Backup verified | | | |
| Rollback tested | | | |
| Team notified | | | |

---

## 📚 Useful Commands Reference

```bash
# Backend
cd backend
python manage.py check --deploy --settings=config.settings.production
python manage.py migrate --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production
python manage.py createsuperuser --settings=config.settings.production
python manage.py shell --settings=config.settings.production
python manage.py dbshell --settings=config.settings.production

# Frontend
cd frontend
npm ci
npm run build
npm run preview  # Test production build locally

# Docker (if using)
docker build -t erp-pulse-backend ./backend
docker build -t erp-pulse-frontend ./frontend
docker-compose -f docker-compose.prod.yml up -d

# Database backup
pg_dump -h host -U user dbname > backup_$(date +%Y%m%d).sql

# Database restore
psql -h host -U user dbname < backup_20240115.sql
```

---

## 📄 Related Documentation

- [Architecture Overview](architecture.md)
- [API Documentation](docs/api.md)
- [NetSuite Integration Guide](docs/netsuite.md)
- [AI Assistant Guide](docs/ai.md)
- [Monitoring Guide](docs/monitoring.md)

---

*Last Updated: $(date)*
*Version: 1.0*