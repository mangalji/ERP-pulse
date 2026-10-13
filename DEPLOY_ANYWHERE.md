+# Deploying AGSuite ERP / ERP-Pulse on any host
+
+The backend adapts to what the host provides. Moving between Catalyst, AWS,
+GCP, Render, a VPS or Docker should only need **environment variables and the
+process command**, never code changes.
+
+Required everywhere (see `env.postgres.example` / `DEPLOY.md`): `DATABASE_URL`,
+`SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `ALLOWED_HOSTS`, CORS settings.
+Everything below is **optional** and has a safe default.
+
+## What is optional, and what happens without it
+
+| Service | Without it |
+|---|---|
+| Redis | Cache, extraction lock and Gemini rate limiter use PostgreSQL. One throttled warning in the log. |
+| Celery worker / broker | OCR and NetSuite batch jobs run in background threads of the web process. |
+| Celery beat | Run `python manage.py run_scheduled_tasks` from any scheduler (daily), or keep `run_ocr_worker` running (it does this itself). |
+| Persistent local disk | Set `OCR_STORAGE_BACKEND=db` (PostgreSQL) or `s3`. `auto` picks `db` if `MEDIA_ROOT` is read-only. |
+
+Job state always lives in PostgreSQL. A job whose process died is resumed
+automatically (the frontend's status polling triggers recovery), and
+documents already posted to NetSuite are not repeated.
+
+## Processes
+
+| Process | Command | When |
+|---|---|---|
+| web | `gunicorn config.wsgi:application -c gunicorn.conf.py` (Catalyst: `main.py`) | always |
+| OCR/NetSuite worker (PostgreSQL queue) | `python manage.py run_ocr_worker` | optional; set `OCR_EXECUTION_MODE=external` on the web process |
+| Celery worker / beat | `celery -A config.celery worker` / `celery -A config.celery beat` | optional (`docker compose --profile full`) |
+
+`OCR_EXECUTION_MODE=auto` (default) uses Celery only when a broker **and** a live
+worker answer a ping; otherwise threads. Check `GET /api/v1/monitoring/health/`
+(`checks.ocr_execution`, `checks.redis`, `checks.storage`).
+
+## Per host
+
+**Docker Compose** (verified only as YAML structure, not run with Docker here)
+- Minimal: `docker compose up -d` (PostgreSQL + backend + frontend).
+- With Redis/Celery: uncomment the Redis lines in `.env.docker`, then
+  `docker compose --profile full up -d`.
+- With the PostgreSQL-queue worker: `OCR_EXECUTION_MODE=external` in `.env.docker`,
+  then `docker compose --profile worker up -d`.
+
+**VPS (Hostinger, EC2, any VM)**: run gunicorn as a service. Optional second
+service for the worker:
+
+```ini
+[Service]
+WorkingDirectory=/srv/erp-pulse/backend
+EnvironmentFile=/srv/erp-pulse/.env
+ExecStart=/srv/erp-pulse/venv/bin/python manage.py run_ocr_worker
+Restart=always
+```
+
+**Render**: web service + (optional) a Background Worker with start command
+`python manage.py run_ocr_worker` and `OCR_EXECUTION_MODE=external` on the web
+service. Free/ephemeral disks: `OCR_STORAGE_BACKEND=db` or `s3`.
+
+**AWS (ECS / App Runner / EC2)**: same as a VPS. Use `OCR_STORAGE_BACKEND=s3`
+(`pip install django-storages boto3`, set `OCR_S3_BUCKET`, `OCR_S3_REGION`; an IAM
+role is used when no keys are given) when running more than one instance.
+
+**GCP Cloud Run**: raise the request timeout if you want inline OCR (default 300s,
+up to 3600s) and **disable CPU throttling** (CPU always allocated) or use
+`OCR_EXECUTION_MODE=external` with a separate always-on worker service, otherwise
+background threads are paused between requests. Use `OCR_STORAGE_BACKEND=db` or `s3`
+(S3-compatible, e.g. GCS interoperability).
+
+**Zoho Catalyst AppSail**: requests are cut off after 30 s. This is detected
+automatically (inline OCR budget becomes 20 s, then the file continues in the
+background and the client polls). Use `OCR_STORAGE_BACKEND=db` (or `s3`) and
+`OCR_EXECUTION_MODE=thread`. A background thread only runs while the instance is
+alive; if it is stopped, the next status poll resumes the job.
+
+## New environment variables
+
+| Variable | Default | Meaning |
+|---|---|---|
+| `REDIS_URL` / `REDIS_ENABLED` | falls back to `CELERY_BROKER_URL` / `true` | Optional Redis; `false` never touches it |
+| `OCR_EXECUTION_MODE` | `auto` | `auto`, `celery`, `thread`, `inline`, `external` |
+| `OCR_BACKGROUND_WORKERS` / `NETSUITE_BACKGROUND_WORKERS` | `2` / `1` | In-process worker threads |
+| `OCR_JOB_LEASE_SECONDS` | `300` | A job that stops renewing is recovered |
+| `OCR_JOB_MAX_RETRIES` / `OCR_JOB_RETRY_BASE_SECONDS` | `5` / `15` | Retry policy |
+| `OCR_SINGLE_TIME_BUDGET_SECONDS` | `180` (`20` on Catalyst) | Inline attempt before handing over |
+| `OCR_SINGLE_ASYNC` | `false` | Never process inline, always poll |
+| `OCR_MULTIPLE_ENABLED` | `true` | Multiple-file mode |
+| `OCR_STORAGE_BACKEND` | `auto` | `auto`, `local`, `db`, `s3` |
+| `OCR_SCRATCH_DIR` | `MEDIA_ROOT/ocr` | Temp work dir (falls back to system temp) |
+| `OCR_S3_BUCKET`, `OCR_S3_REGION`, `OCR_S3_ENDPOINT_URL`, `OCR_S3_ACCESS_KEY_ID`, `OCR_S3_SECRET_ACCESS_KEY` | empty | S3-compatible storage |
+| `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` | `2`, `1`, `300` | Read by `gunicorn.conf.py` |
+
+## Limits to know
+
+- A platform request limit (Catalyst 30 s) cannot be raised from code; long work
+  continues in the background instead.
+- Profile pictures (`accounts`) still use the default Django storage (local disk).
+- `OCR_STORAGE_BACKEND=db` keeps whole files in PostgreSQL: fine for typical
+  documents, use `s3` for very large volumes.
