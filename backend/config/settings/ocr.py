"""
OCR module configuration for AGSuite ERP.

All OCR-related configurable values live here so no magic numbers
appear inside the OCR codebase. Values can be overridden via
environment variables for environment-specific tuning.
"""
import os
from decouple import config

# ------------------------------------------------------------------
# PDF Processing
# ------------------------------------------------------------------

#: Maximum number of pages a PDF may have to be processed.
OCR_MAX_PAGES: int = config('OCR_MAX_PAGES', default=100, cast=int)

#: DPI (dots per inch) for PDF-to-image conversion.
OCR_PDF_DPI: int = config('OCR_PDF_DPI', default=300, cast=int)

# ------------------------------------------------------------------
# Chunked PDF mode
# ------------------------------------------------------------------
# Normal pipeline: every PDF page is rendered to a PNG at OCR_PDF_DPI and
# sent as a SEPARATE AI request (N pages = N full API calls, each
# repeating the whole prompt/schema). This mode instead splits the PDF
# into page-range PDF chunks of OCR_PDF_CHUNK_PAGES pages each (e.g. a
# 23-page PDF with the default chunk size becomes 3 chunks: pages 1-10,
# 11-20, 21-23) and sends each chunk as ONE request — no local PyMuPDF
# rasterization, no DPI setting, just a page-range copy. A PDF with
# OCR_PDF_CHUNK_PAGES pages or fewer becomes a single chunk, i.e. a
# single request for the whole document.
#
# Safety: if the split itself fails for any reason, the caller falls back
# to the existing, unchanged per-page pipeline. A PDF whose page count
# exceeds OCR_MAX_PAGES is still rejected either way.
# Chunked mode is enabled by default; set OCR_PDF_WHOLE_DOCUMENT=False to
# temporarily fall back to the legacy per-page image pipeline.
OCR_PDF_WHOLE_DOCUMENT: bool = config(
    'OCR_PDF_WHOLE_DOCUMENT', default=True, cast=bool
)

#: Max pages per chunk PDF sent to the AI provider in one request.
OCR_PDF_CHUNK_PAGES: int = config(
    'OCR_PDF_CHUNK_PAGES', default=5, cast=int
)

# ------------------------------------------------------------------
# AI provider API
# ------------------------------------------------------------------

#: Request timeout in seconds for AI provider calls.
OCR_TIMEOUT: int = config('OCR_TIMEOUT', default=300, cast=int)

#: Maximum number of retry attempts on failure.
OCR_MAX_RETRIES: int = config('OCR_MAX_RETRIES', default=3, cast=int)

#: Base delay in seconds for exponential backoff.
OCR_RETRY_DELAY: float = config('OCR_RETRY_DELAY', default=1.0, cast=float)

#: Maximum image size in MB allowed for AI processing.
# OCR_MAX_IMAGE_SIZE_MB: int = config('OCR_MAX_IMAGE_SIZE_MB', default=20, cast=int)

# #: Confidence threshold below which extraction is considered unreliable.
# OCR_CONFIDENCE_THRESHOLD: float = config('OCR_CONFIDENCE_THRESHOLD', default=0.5, cast=float)

OCR_MAX_UPLOAD_SIZE_MB: int = config('OCR_MAX_UPLOAD_SIZE_MB',default=10,cast=int)

OCR_MAX_ZIP_FILES: int = config('OCR_MAX_ZIP_FILES',default=20,cast=int)

OCR_MAX_ZIP_SIZE_MB: int = config('OCR_MAX_ZIP_SIZE_MB',default=50,cast=int)

OCR_MAX_ZIP_UNCOMPRESSED_MB: int = config('OCR_MAX_ZIP_UNCOMPRESSED_MB',default=100,cast=int)

# Maximum number of AI calls active for one company/provider/model scope.
OCR_AI_MAX_CONCURRENCY: int = config('OCR_AI_MAX_CONCURRENCY', default=5, cast=int)

# Application-side rolling requests-per-minute ceiling.
# Keep this BELOW the configured provider account quota for one scope.
OCR_AI_TARGET_RPM: int = config(
    'OCR_AI_TARGET_RPM',
    default=20,
    cast=int,
)

# Lease for the distributed concurrency slot.
OCR_AI_CONCURRENCY_LEASE_SECONDS: int = config(
    'OCR_AI_CONCURRENCY_LEASE_SECONDS',
    default=600,
    cast=int,
)
OCR_SINGLE_MAX_PAGES: int = config('OCR_SINGLE_MAX_PAGES', default=5, cast=int)
# Catalyst AppSail ends every request after 30s, so on that platform the inline
# attempt must hand over to background processing well before that.
ON_CATALYST: bool = bool(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT"))

OCR_SINGLE_TIME_BUDGET_SECONDS: int = config(
    'OCR_SINGLE_TIME_BUDGET_SECONDS',
    default=20 if ON_CATALYST else 300,
    cast=int,
)
# true = never process inline: accept the file and let the client poll.
OCR_SINGLE_ASYNC: bool = config('OCR_SINGLE_ASYNC', default=False, cast=bool)
# OCR_SINGLE_TIME_BUDGET_SECONDS: int = config('OCR_SINGLE_TIME_BUDGET_SECONDS', default=180, cast=int)
OCR_MULTI_MAX_FILES: int = config('OCR_MULTI_MAX_FILES', default=200, cast=int)
# OCR_MULTIPLE_ENABLED: bool = config('OCR_MULTIPLE_ENABLED', default=False, cast=bool)
# Multiple-file mode works with or without Celery/Redis (see OCR_EXECUTION_MODE).
OCR_MULTIPLE_ENABLED: bool = config('OCR_MULTIPLE_ENABLED', default=True, cast=bool)
# ---------------------------------------------------------------------------
# Background execution (all optional; the defaults work on any host)
# ---------------------------------------------------------------------------
# auto   : Celery when a broker AND a live worker are detected, otherwise
#          in-process background threads.
# celery : prefer Celery (still degrades to threads if it is unreachable).
# thread : always use in-process background threads.
# inline : run in the requesting process (no background execution).
OCR_EXECUTION_MODE: str = config('OCR_EXECUTION_MODE', default='auto').strip().lower()
OCR_BACKGROUND_WORKERS: int = config('OCR_BACKGROUND_WORKERS', default=2, cast=int)
# A running job renews its lease; a job whose lease expired is considered
# interrupted and is re-queued by the recovery logic.
# Threads for in-process NetSuite batch jobs (kept separate from OCR so a long
# posting batch never starves OCR).
NETSUITE_BACKGROUND_WORKERS: int = config('NETSUITE_BACKGROUND_WORKERS', default=1, cast=int)
OCR_JOB_LEASE_SECONDS: int = config('OCR_JOB_LEASE_SECONDS', default=600, cast=int)
OCR_JOB_MAX_RETRIES: int = config('OCR_JOB_MAX_RETRIES', default=5, cast=int)

# Limits for explicit actions initiated from the OCR review screen. These are
# separate from automatic Celery/provider retries and are cumulative per upload.
OCR_MANUAL_RETRY_LIMIT: int = config('OCR_MANUAL_RETRY_LIMIT', default=4, cast=int)
# Retry back-off: base * 2**attempt seconds (+ jitter), capped at 15 minutes.
OCR_JOB_RETRY_BASE_SECONDS: float = config('OCR_JOB_RETRY_BASE_SECONDS', default=15, cast=float)
# How long a queued job may sit unclaimed before recovery re-dispatches it.
OCR_THREAD_REDISPATCH_AFTER_SECONDS: int = config(
    'OCR_THREAD_REDISPATCH_AFTER_SECONDS', default=60, cast=int
)
OCR_CELERY_REDISPATCH_AFTER_SECONDS: int = config(
    'OCR_CELERY_REDISPATCH_AFTER_SECONDS', default=900, cast=int
)
OCR_CELERY_PROBE_SECONDS: int = config('OCR_CELERY_PROBE_SECONDS', default=30, cast=int)

# ---------------------------------------------------------------------------
# File storage (see ocr/storage.py): auto | local | db | s3
# ---------------------------------------------------------------------------
OCR_STORAGE_BACKEND: str = config('OCR_STORAGE_BACKEND', default='auto').strip().lower()
# Temporary page images etc. (defaults to MEDIA_ROOT/ocr/..., falls back to the
# system temp dir when that is read-only).
OCR_SCRATCH_DIR: str = config('OCR_SCRATCH_DIR', default='')
# S3-compatible bucket (only when OCR_STORAGE_BACKEND=s3; needs django-storages + boto3).
OCR_S3_BUCKET: str = config('OCR_S3_BUCKET', default='')
OCR_S3_REGION: str = config('OCR_S3_REGION', default='')
OCR_S3_ENDPOINT_URL: str = config('OCR_S3_ENDPOINT_URL', default='')
OCR_S3_ACCESS_KEY_ID: str = config('OCR_S3_ACCESS_KEY_ID', default='')
OCR_S3_SECRET_ACCESS_KEY: str = config('OCR_S3_SECRET_ACCESS_KEY', default='')

# Zoho Catalyst Cloud Scale Stratus
# OCR_STRATUS_BUCKET: str = config(
#     'OCR_STRATUS_BUCKET',
#     default='',
# )

# OCR_STRATUS_PREFIX: str = config(
#     'OCR_STRATUS_PREFIX',
#     default='ocr',
# )
