"""
OCR processing tasks.

Existing IDP pipeline tasks are preserved.
The OCR batch processor uses the approved notebook Gemini extractor,
Redis quota limiting, and per-file persistence.
"""
from __future__ import annotations
import sys
import time
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
import logging
import random
import redis
import uuid
from typing import Any
import mimetypes
from django.utils import timezone
from django.conf import settings

from ocr.error_taxonomy import (
    FailureInfo,
    classify_failure,
    is_daily_quota_error,
)
from ocr.exceptions import (
    DocumentProcessingException,
    GeminiConnectionException,
    GeminiRateLimitException,
    GeminiTimeoutException,
    InvalidExtractionResultException,
    OCRTimeBudgetExceeded,
)
from ocr.models import OCRBatch, OCRDocument, OCRUpload
from ocr.notebook_extraction_service import notebook_gemini_extractor
from ocr.adapters import get_adapter
from common.infra import get_redis_client, report_redis_failure, warn_throttled
from ocr.storage import local_file_path
from ocr.leases import LeaseHeartbeat, claim_upload, lease_seconds, new_owner
from ocr.services.gemini_quota_limiter import GeminiQuotaLimiter

logger = logging.getLogger(__name__)

OCR_EXTRACTION_LOCK_TTL_SECONDS = getattr(
    settings,
    "OCR_EXTRACTION_LOCK_TTL_SECONDS",
    5 * 60,
)
OCR_EXTRACTION_LOCK_HEARTBEAT_SECONDS = getattr(
    settings,
    "OCR_EXTRACTION_LOCK_HEARTBEAT_SECONDS",
    60,
)

OCR_EXTRACTION_CACHE_TTL_SECONDS =  96 * 60 * 60
OCR_EXTRACTION_LOCK_MAX_WAIT_SECONDS = getattr(
    settings,
    "OCR_EXTRACTION_LOCK_MAX_WAIT_SECONDS",
    2 * 60,
)
OCR_EXTRACTION_LOCK_POLL_INTERVAL_SECONDS = getattr(
    settings,
    "OCR_EXTRACTION_LOCK_POLL_INTERVAL_SECONDS",
    1,
)

OCR_EXTRACTION_CACHE_VERSION = "v3"
OCR_EXTRACTION_CONTRACT_VERSION = "v2"


def _live_result_key(upload_id: str) -> str:
    return (
        f"erp-pulse:ocr:live:{upload_id}"
        )

def _is_daily_gemini_quota_error(exc: Exception) -> bool:
    """Backward-compatible alias of ``error_taxonomy.is_daily_quota_error``."""
    return is_daily_quota_error(exc)


def _mark_upload_failed(upload, reason: str, code: str = "") -> None:
    completed_at = timezone.now()

    upload.status = OCRUpload.Status.FAILED
    upload.processing_completed_at = completed_at
    upload.failure_reason = str(reason)[:5000]
    upload.failure_code = code or ""
    upload.lease_owner = ""
    upload.lease_expires_at = None
    upload.next_attempt_at = None

    update_fields = [
        "status",
        "processing_completed_at",
        "failure_reason",
        "failure_code",
        "lease_owner",
        "lease_expires_at",
        "next_attempt_at",
    ]

    if getattr(upload, "processing_started_at", None):
        upload.processing_duration_ms = int(
            (
                completed_at - upload.processing_started_at
            ).total_seconds() * 1000
        )
        update_fields.append("processing_duration_ms")

    upload.save(update_fields=update_fields)
    _refresh_batch_status(upload.batch_id)


def _merge_page_extraction_results(page_results: list[dict]) -> dict:
    """
    Merge page-level dynamic OCR results into one canonical result.

    Header/custom fields: first non-null/non-empty value wins.
    line_items: all page lists are concatenated in page order.
    raw_text: page text is concatenated with a page-break marker.
    Other fields: first non-null/non-empty value wins.
    """
    if not page_results:
        raise ValueError("OCR adapter produced no extractable pages.")

    if len(page_results) == 1:
        return page_results[0]

    merged: dict = {}
    merged_line_items: list = []
    raw_text_parts: list[str] = []

    for page_index, result in enumerate(page_results, start=1):
        if not isinstance(result, dict):
            raise ValueError(
                f"OCR extractor returned invalid page result at page {page_index}."
            )

        for key, value in result.items():
            if key == "line_items":
                if value is None:
                    continue
                if not isinstance(value, list):
                    raise ValueError(
                        f"OCR extractor returned invalid line_items on page {page_index}."
                    )
                merged_line_items.extend(value)
                continue

            if key == "raw_text":
                if value not in (None, ""):
                    raw_text_parts.append(str(value))
                continue

            if merged.get(key) in (None, "") and value not in (None, ""):
                merged[key] = value

    if "line_items" in page_results[0] or merged_line_items:
        merged["line_items"] = merged_line_items

    if raw_text_parts:
        merged["raw_text"] = "\n---PAGE BREAK---\n".join(raw_text_parts)

    return merged


def _validate_extraction_result(result, *, page_index: int | None = None) -> None:
    """Shared shape check for AI extraction output (single page or merged)."""
    where = f" on page {page_index}" if page_index else ""

    if not isinstance(result, dict):
        raise InvalidExtractionResultException(
            f"OCR extractor returned an invalid result{where}."
        )

    line_items = result.get("line_items")
    if line_items is not None and not isinstance(line_items, list):
        raise InvalidExtractionResultException(
            f"OCR extractor returned invalid line_items{where}."
        )


def _normalize_to_page_paths(adapter, upload, original_path) -> list[str]:
    """Run the document adapter and return the image page paths for the AI."""
    normalized = adapter.normalize()

    if not isinstance(normalized, dict):
        raise ValueError("Document adapter returned an invalid normalized result.")

    pages = normalized.get("pages") or []
    if isinstance(pages, (str, bytes)):
        pages = [pages]

    page_paths = [str(path) for path in pages if path]

    if not page_paths:
        fallback_path = normalized.get("path") or original_path
        if fallback_path:
            page_paths = [str(fallback_path)]

    if not page_paths:
        raise DocumentProcessingException(
            f"Document adapter produced no pages for "
            f"'{upload.original_filename}'."
        )

    return page_paths


def _extract_single_page(
    upload,
    page_path: str,
    requested_fields,
    page_index: int,
    deadline_monotonic: float | None,
) -> dict:
    """
    Send one page to the AI extractor.

    Without a deadline (background workers) the extractor's own timeout and
    retry policy apply. With a deadline (inline/single mode) the request is
    bounded by the remaining wall-clock budget, with at most one quick retry.
    """
    mime_type, _ = mimetypes.guess_type(page_path)
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/png"

    if deadline_monotonic is None:
        return notebook_gemini_extractor.extract(
            file_path=page_path,
            mime_type=mime_type,
            requested_fields=requested_fields,
            company=upload.batch.company,
        )

    max_single_ai_retries = 1
    result = None

    for ai_attempt in range(max_single_ai_retries + 1):
        remaining = deadline_monotonic - time.monotonic()

        if remaining <= 0:
            raise OCRTimeBudgetExceeded(
                "Single OCR processing exceeded its time budget."
            )

        # Give the request most of the remaining budget; keep a small reserve
        # for response handling, persistence and cleanup.
        request_timeout = max(1.0, remaining - 2.0)

        try:
            result = notebook_gemini_extractor.extract(
                file_path=page_path,
                mime_type=mime_type,
                requested_fields=requested_fields,
                company=upload.batch.company,
                timeout=request_timeout,
                max_retries=0,
            )
            break
        except (
            GeminiConnectionException,
            GeminiRateLimitException,
            GeminiTimeoutException,
        ) as exc:
            if ai_attempt >= max_single_ai_retries or is_daily_quota_error(exc):
                # Out of attempts, or a terminal daily-quota error that a
                # retry cannot fix.
                raise

            remaining_after_failure = deadline_monotonic - time.monotonic()

            if remaining_after_failure <= 3.0:
                raise OCRTimeBudgetExceeded(
                    "Single OCR processing did not have enough time "
                    "for another AI attempt."
                ) from exc

            retry_delay = min(3.0, remaining_after_failure - 2.0)

            logger.warning(
                "Retrying Single OCR Gemini request — "
                "upload=%s page=%s attempt=%d/%d delay=%.1fs reason=%s",
                upload.id,
                page_index,
                ai_attempt + 1,
                max_single_ai_retries + 1,
                retry_delay,
                exc,
            )
            time.sleep(retry_delay)

    if result is None:
        raise GeminiConnectionException("Gemini OCR did not return a result.")

    return result


def _perform_ocr_extraction(
    upload,
    requested_fields,
    *,
    deadline_monotonic: float | None = None,
):
    """
    Shared OCR extraction engine (used by every execution mode).

    Normalizes every supported document format into AI-consumable page
    images, extracts each page with the same dynamic requested_fields ->
    prompt/schema -> normalization contract, and merges the pages.

    ``deadline_monotonic`` (a ``time.monotonic()`` value) is only set by the
    inline/single mode to bound the wall-clock time; background execution
    leaves it ``None``.
    """
    with local_file_path(upload.file) as original_path:
        adapter = get_adapter(original_path, str(upload.id))

        try:

            page_paths = _normalize_to_page_paths(adapter, upload, original_path)
            page_results = []

            for page_index, page_path in enumerate(page_paths, start=1):
                result = _extract_single_page(
                    upload,
                    page_path,
                    requested_fields,
                    page_index,
                    deadline_monotonic,
                )
                _validate_extraction_result(result, page_index=page_index)
                page_results.append(result)

            return _merge_page_extraction_results(page_results)

        finally:
            try:
                cleanup = getattr(adapter, "cleanup", None)
                if callable(cleanup):
                    cleanup()
            except Exception:
                logger.exception(
                    "OCR adapter cleanup failed — upload=%s",
                    getattr(upload, "id", None),
                )

def _perform_ocr_extraction_sync(
    upload,
    requested_fields,
    *,
    deadline_monotonic: float,
) -> dict:
    """Backward-compatible wrapper: extraction bounded by a wall-clock deadline."""
    return _perform_ocr_extraction(
        upload,
        requested_fields,
        deadline_monotonic=deadline_monotonic,
    )


def _canonical_config(requested_fields: Any) -> dict:
    """
    Build a canonical, deterministic representation of an extraction
    configuration suitable for hashing and comparison.

    The backend is authoritative: callers must pass the persisted
    ``OCRBatch.requested_fields_json`` or a comparable dict. Frontend
    JSON is not trusted without canonicalization.

    Raises ValueError for malformed configurations that cannot be
    safely canonicalized.
    """
    if requested_fields is None:
        return {"standard_fields": [], "custom_fields": []}

    if not isinstance(requested_fields, dict):
        raise ValueError(
            f"Extraction configuration must be a dict, got {type(requested_fields).__name__}"
        )

    selected_standard = requested_fields.get("standard_fields")
    if selected_standard is not None and not isinstance(selected_standard, list):
        raise ValueError(
            f"standard_fields must be a list, got {type(selected_standard).__name__}"
        )

    custom_fields = requested_fields.get("custom_fields")
    if custom_fields is not None and not isinstance(custom_fields, list):
        raise ValueError(
            f"custom_fields must be a list, got {type(custom_fields).__name__}"
        )

    if not isinstance(selected_standard, list):
        selected_standard = sorted(
            {
                "invoice_number",
                "invoice_date",
                "due_date",
                "vendor_name",
                "customer_name",
                "subsidiary",
                "currency",
                "subtotal",
                "tax_amount",
                "tax_rate",
                "total_amount",
                "payment_terms",
                "line_items",
            }
        )

    normalized_custom = []
    for idx, custom in enumerate(custom_fields or []):
        if not isinstance(custom, dict):
            raise ValueError(
                f"custom_fields[{idx}] must be a dict, "
                f"got {type(custom).__name__}"
            )
        label = str(custom.get("label") or custom.get("key") or "").strip()
        if not label:
            raise ValueError(
                f"custom_fields[{idx}] must have a non-empty label or key"
            )
        normalized_custom.append(
            {
                "key": str(custom.get("key") or label).strip(),
                "label": label,
                "description": str(custom.get("description") or "").strip(),
                "scope": str(custom.get("scope") or "header").strip().lower(),
                "data_type": str(custom.get("data_type") or "text").strip().lower(),
            }
        )

    return {
        "standard_fields": sorted(selected_standard),
        "custom_fields": sorted(
            normalized_custom,
            key=lambda c: (c["key"], c["label"], c["description"], c["scope"], c["data_type"]),
        ),
    }


def build_extraction_config_hash(requested_fields: Any) -> str:
    """
    Deterministic hash of the complete extraction configuration.

    Two semantically identical configurations always produce the same
    hash. Different configurations produce different hashes.

    - ``None`` or ``{}`` → ``"default"``
    - Valid explicit configuration → deterministic config hash
    - Malformed/invalid non-empty configuration → raises ``ValueError``

    Never silently converts invalid configuration to the default hash.
    """
    try:
        if requested_fields is None or requested_fields == {}:
            return "default"

        canonical = _canonical_config(requested_fields)

        # If canonical config is empty (no standard fields, no custom fields),
        # treat it as default
        if not canonical["standard_fields"] and not canonical["custom_fields"]:
            return "default"

        normalized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.md5(normalized).hexdigest()[:16]
    except ValueError:
        raise
    except Exception:
        raise ValueError(
            "Failed to canonicalize extraction configuration for hashing."
        )


def build_extraction_contract_version() -> str:
    """
    Return the current extraction contract version.

    Increment this string whenever the extraction prompt, schema,
    normalization, datatype rules, or verification logic changes in a
    way that could invalidate previously cached results.
    """
    return OCR_EXTRACTION_CONTRACT_VERSION

def _scope_hash(scope: str) -> str:
    """Short stable hash of a tenant/provider scope string (safe for cache keys)."""
    return hashlib.sha1(scope.encode("utf-8")).hexdigest()[:12]


def _extraction_scope(upload) -> str:
    """
    Tenant + AI configuration scope for cache and lock keys.

    Cached extraction results must never be shared between companies, and
    must not survive a change of the company's AI provider/model. Returns
    ``"<company_id>:<provider>:<model>"`` (or just the company id if the AI
    configuration cannot be read); ``""`` only when there is no company.
    """
    company_id = getattr(getattr(upload, "batch", None), "company_id", None)
    if not company_id:
        return ""

    try:
        from ocr.models import AIConfiguration

        config = (
            AIConfiguration.objects.filter(company_id=company_id)
            .values_list("provider", "model")
            .first()
        )
    except Exception as exc:  # noqa: BLE001 - scope must never break extraction
        logger.warning(
            "Could not read AI configuration for OCR cache scope — "
            "company=%s reason=%s",
            company_id,
            exc,
        )
        config = None

    provider, model = config if config else ("", "")
    return f"{company_id}:{provider}:{model}"


def build_ocr_cache_identity(
    file_hash: str,
    requested_fields: Any,
    scope: str = "",
) -> dict:
    """
    Build the complete cache identity for an extraction request.

    The identity captures:
    - document identity (file_hash)
    - extraction configuration (config_hash)
    - extraction contract version

    This identity is stored as metadata alongside the cached result
    and validated on every cache read.
    """
    identity = {
        "document_identity": file_hash,
        "config_hash": build_extraction_config_hash(requested_fields),
        "contract_version": build_extraction_contract_version(),
        "status": "COMPLETED",
    }
    if scope:
        identity["scope"] = _scope_hash(scope)
    return identity


def build_ocr_cache_key(file_hash: str, requested_fields: Any, scope: str = "") -> str:
    """
    Build a deterministic Redis cache key that includes all identity
    components.

    Format:
        erp-pulse:ocr:file-result:<cache_version>:<contract_version>:<config_hash>:<file_hash>
    """
    identity = build_ocr_cache_identity(file_hash, requested_fields, scope)
    scope_part = f"{identity['scope']}:" if "scope" in identity else ""
    return (
        f"erp-pulse:ocr:file-result:"
        f"{OCR_EXTRACTION_CACHE_VERSION}:"
        f"{identity['contract_version']}:"
        f"{identity['config_hash']}:"
        f"{scope_part}"
        f"{file_hash}"
    )


def _is_valid_cache_metadata(metadata: Any) -> bool:
    """Validate that cache metadata contains all required fields."""
    if not isinstance(metadata, dict):
        return False
    for field in ("document_identity", "config_hash", "contract_version", "status"):
        if field not in metadata:
            return False
    return metadata.get("status") == "COMPLETED"


def read_valid_cached_result(file_hash: str, requested_fields: Any, scope: str = ""):
    """
    Read a cached OCR result only if the metadata validates completely.

    Returns the result dict on cache hit, or None on cache miss /
    invalid metadata. Never raises on corrupt cache entries.

    The metadata is validated against the expected identity derived from
    the provided file_hash and requested_fields. This ensures a cached
    result is never returned when it was generated using a different
    extraction contract.
    """
    try:
        expected_identity = build_ocr_cache_identity(file_hash, requested_fields, scope)
        cache_key = build_ocr_cache_key(file_hash, requested_fields, scope)
        cached = _kv_get(cache_key)

        if not cached:
            return None

        payload = json.loads(cached)

        if not isinstance(payload, dict):
            logger.warning(
                "Ignoring non-dict OCR cache payload — file_hash=%s",
                file_hash,
            )
            return None

        metadata = payload.get("metadata")
        if not _is_valid_cache_metadata(metadata):
            logger.warning(
                "Ignoring OCR cache entry with invalid/missing metadata — file_hash=%s metadata=%s",
                file_hash,
                metadata,
            )
            return None

        # Validate metadata matches the expected identity
        if metadata.get("document_identity") != expected_identity["document_identity"]:
            logger.warning(
                "Ignoring OCR cache entry with mismatched document identity — file_hash=%s cached=%s expected=%s",
                file_hash,
                metadata.get("document_identity"),
                expected_identity["document_identity"],
            )
            return None

        if metadata.get("config_hash") != expected_identity["config_hash"]:
            logger.warning(
                "Ignoring OCR cache entry with mismatched config hash — file_hash=%s cached=%s expected=%s",
                file_hash,
                metadata.get("config_hash"),
                expected_identity["config_hash"],
            )
            return None

        if metadata.get("scope", "") != expected_identity.get("scope", ""):
            logger.warning(
                "Ignoring OCR cache entry from a different tenant/AI scope — file_hash=%s",
                file_hash,
            )
            return None

        if metadata.get("contract_version") != expected_identity["contract_version"]:
            logger.warning(
                "Ignoring OCR cache entry with mismatched contract version — file_hash=%s cached=%s expected=%s",
                file_hash,
                metadata.get("contract_version"),
                expected_identity["contract_version"],
            )
            return None

        result = payload.get("result")
        if not _is_valid_cached_result(result):
            logger.warning(
                "Ignoring OCR cache entry with invalid result shape — file_hash=%s",
                file_hash,
            )
            return None

        return result

    except redis.RedisError as exc:
        logger.warning(
            "OCR Redis cache read unavailable; continuing without cache — "
            "file_hash=%s error=%s",
            file_hash,
            exc,
        )
        return None


def write_completed_cached_result(
    file_hash: str,
    requested_fields: Any,
    result: dict,
    ttl: int | None = None,
    scope: str = "",
) -> None:
    """
    Write a completed OCR result to cache with full identity metadata.

    Only completed results should be cached. The payload includes
    validation metadata so stale or mismatched entries are rejected
    on read.
    """
    try:
        cache_key = build_ocr_cache_key(file_hash, requested_fields, scope)
        identity = build_ocr_cache_identity(file_hash, requested_fields, scope)
        payload = {
            "metadata": identity,
            "result": result,
        }
        _kv_set(
            cache_key,
            json.dumps(payload, ensure_ascii=False, default=str),
            ttl or OCR_EXTRACTION_CACHE_TTL_SECONDS,
        )
    except redis.RedisError as exc:
        logger.warning(
            "OCR Redis cache write unavailable; continuing without cache — "
            "file_hash=%s error=%s",
            file_hash,
            exc,
        )


def _config_hash(requested_fields: Any) -> str:
    """
    Short, stable hash of the dynamic extraction configuration.

    Kept for backward compatibility with call sites that still pass
    config_hash explicitly. New code should use ``build_extraction_config_hash``.
    """
    return build_extraction_config_hash(requested_fields)


def _file_result_cache_key(file_hash: str, config_hash: str | None = None) -> str:
    """
    Backward-compatible cache key builder.

    New code should use ``build_ocr_cache_key`` which includes the
    contract version. This wrapper preserves the old signature for
    existing callers.
    """
    if config_hash is None:
        config_hash = build_extraction_config_hash(None)
    return (
        f"erp-pulse:ocr:file-result:"
        f"{OCR_EXTRACTION_CACHE_VERSION}:"
        f"{OCR_EXTRACTION_CONTRACT_VERSION}:"
        f"{config_hash}:"
        f"{file_hash}"
    )


def _build_lock_key(file_hash: str, requested_fields: Any, scope: str = "") -> str:
    """
    Build a deterministic Redis lock key for an extraction identity.

    Format:
        erp-pulse:ocr:lock:<cache_version>:<contract_version>:<config_hash>:<file_hash>
    """
    identity = build_ocr_cache_identity(file_hash, requested_fields, scope)
    scope_part = f"{identity['scope']}:" if "scope" in identity else ""
    return (
        f"erp-pulse:ocr:lock:"
        f"{OCR_EXTRACTION_CACHE_VERSION}:"
        f"{identity['contract_version']}:"
        f"{identity['config_hash']}:"
        f"{scope_part}"
        f"{file_hash}"
    )

from enum import Enum


class ExtractionLockStatus(str, Enum):
    ACQUIRED = "acquired"
    HELD = "held"
    UNAVAILABLE = "unavailable"

# Locks taken through the PostgreSQL-backed Django cache (the fallback used
# when Redis is unavailable) carry this prefix so renew/release know which
# backend owns them.
_DB_LOCK_TOKEN_PREFIX = "db:"


def _db_cache():
    from django.core.cache import cache

    return cache


def _kv_get(key: str):
    """Redis GET with a fallback to the shared Django (database) cache."""
    try:
        return _redis_client().get(key)
    except redis.RedisError as exc:
        report_redis_failure(exc)

    try:
        return _db_cache().get(key)
    except Exception as exc:  # noqa: BLE001 - a cache miss must never break OCR
        warn_throttled(
            "ocr-db-cache-read",
            "OCR database cache read unavailable; continuing without cache: %s",
            exc,
        )
        return None


def _kv_set(key: str, value: str, ttl: int) -> None:
    """Redis SETEX with a fallback to the shared Django (database) cache."""
    try:
        _redis_client().setex(key, ttl, value)
        return
    except redis.RedisError as exc:
        report_redis_failure(exc)

    try:
        _db_cache().set(key, value, timeout=ttl)
    except Exception as exc:  # noqa: BLE001
        warn_throttled(
            "ocr-db-cache-write",
            "OCR database cache write unavailable; continuing without cache: %s",
            exc,
        )


def _db_acquire_lock(lock_key: str, file_hash: str):
    token = _DB_LOCK_TOKEN_PREFIX + uuid.uuid4().hex

    try:
        if _db_cache().add(lock_key, token, timeout=OCR_EXTRACTION_LOCK_TTL_SECONDS):
            return ExtractionLockStatus.ACQUIRED, token
        return ExtractionLockStatus.HELD, None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "No extraction lock backend available; continuing without a lock — "
            "file_hash=%s reason=%s",
            file_hash,
            exc,
        )
        return ExtractionLockStatus.UNAVAILABLE, None



def acquire_extraction_lock(
    file_hash: str,
    requested_fields: Any,
    scope: str = "",
) -> tuple[ExtractionLockStatus, str | None]:
    """
    Try to acquire the extraction lock (Redis, falling back to PostgreSQL).

    Returns:
        (ACQUIRED, token)
        (HELD, None)
        (UNAVAILABLE, None)   # no lock backend reachable: proceed without a lock
    """
    lock_key = _build_lock_key(file_hash, requested_fields, scope)
    try:
        token = uuid.uuid4().hex

        acquired = _redis_client().set(
            lock_key,
            token,
            nx=True,
            ex=OCR_EXTRACTION_LOCK_TTL_SECONDS,
        )

        if acquired:
            return ExtractionLockStatus.ACQUIRED, token

        return ExtractionLockStatus.HELD, None

    except redis.RedisError as exc:
        report_redis_failure(exc)
        logger.debug(
            "Redis unavailable for OCR extraction lock; using PostgreSQL  " 
            "fallback file_hash=%s reason=%s",
            file_hash,
            exc,
        )
        return _db_acquire_lock(lock_key, file_hash)

_RENEW_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""


def renew_extraction_lock(
    file_hash: str,
    requested_fields: Any,
    token: str | None,
    scope: str = "",
) -> bool:
    if not token:
        return False

    lock_key = _build_lock_key(file_hash, requested_fields, scope)

    if token.startswith(_DB_LOCK_TOKEN_PREFIX):
        try:
            cache = _db_cache()
            if cache.get(lock_key) != token:
                return False
            return bool(cache.touch(lock_key, OCR_EXTRACTION_LOCK_TTL_SECONDS))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "OCR extraction lock renewal failed — file_hash=%s reason=%s",
                file_hash,
                exc,
            )
            return False

    try:

        result = _redis_client().eval(
            _RENEW_LOCK_SCRIPT,
            1,
            lock_key,
            token,
            OCR_EXTRACTION_LOCK_TTL_SECONDS,
        )

        return bool(result)

    except redis.RedisError as exc: 
        logger.warning(
            "OCR extraction lock renewal failed — file_hash=%s reason=%s",
            file_hash,
            exc,
        )
        return False

import threading

class ExtractionLockHeartbeat:
    def __init__(
        self,
        file_hash: str,
        requested_fields: Any,
        token: str,
        scope: str = "",
    ) -> None:
        self.file_hash = file_hash
        self.requested_fields = requested_fields
        self.token = token
        self.scope = scope
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.lost = False

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self._run,
            name="ocr-extraction-lock-heartbeat",
            daemon=True,
        )
        self.thread.start()

    def _run(self) -> None:
        while not self.stop_event.wait(
            OCR_EXTRACTION_LOCK_HEARTBEAT_SECONDS
        ):
            renewed = renew_extraction_lock(
                self.file_hash,
                self.requested_fields,
                self.token,
                self.scope,
            )

            if not renewed:
                self.lost = True
                logger.warning(
                    "OCR extraction lock ownership lost; another worker may "
                    "duplicate this extraction — file_hash=%s",
                     self.file_hash,
                 )
                return

    def stop(self) -> None:
        self.stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

def release_extraction_lock(
    file_hash: str,
    requested_fields: Any,
    token: str | None,
    scope: str = "",
) -> None:
    """
    Release a lock only if the caller is the owner.

    Redis locks use a Lua script for an atomic check-and-delete; PostgreSQL
    (Django cache) locks compare the stored token before deleting.
    """
    if not token:
        return
    lock_key = _build_lock_key(file_hash, requested_fields, scope)

    if token.startswith(_DB_LOCK_TOKEN_PREFIX):
        try:
            cache = _db_cache()
            if cache.get(lock_key) == token:
                cache.delete(lock_key)
        except Exception as exc:  # noqa: BLE001 - the lock expires on its own TTL
            logger.warning(
                "OCR extraction lock release skipped (lock will expire on "
                "its own) — file_hash=%s reason=%s",
                file_hash,
                exc,
            )
        return
    try:
        # Lua script: only delete if value matches token (owner check)
        lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
        """
        _redis_client().eval(lua, 1, lock_key, token)
    except redis.RedisError as exc:
        # Expected when Redis is down: the lock simply expires on its own TTL.
        logger.warning(
            "OCR extraction lock release skipped (Redis unavailable; lock "
            "will expire on its own) — file_hash=%s reason=%s",
            file_hash,
            exc,
        )
    except Exception:
        logger.exception(
            "OCR extraction lock release failed — file_hash=%s",
            file_hash,
        )

def _lock_state(lock_key: str) -> str:
    """
    Is the extraction lock currently held? Checks Redis and PostgreSQL.

    Returns "held", "free", or "unavailable" (neither backend reachable).
    """
    redis_failed = False

    try:
        if _redis_client().exists(lock_key):
            return "held"
    except redis.RedisError as exc:
        report_redis_failure(exc)
        redis_failed = True

    try:
        if _db_cache().get(lock_key) is not None:
            return "held"
    except Exception as exc:  # noqa: BLE001
        if redis_failed:
            logger.warning(
                "No extraction lock backend available while waiting — reason=%s",
                exc,
            )
            return "unavailable"

    return "free"


def wait_for_extraction_lock(
    file_hash: str,
    requested_fields: Any,
    timeout: int = OCR_EXTRACTION_LOCK_MAX_WAIT_SECONDS,
    poll_interval: int = OCR_EXTRACTION_LOCK_POLL_INTERVAL_SECONDS,
    scope: str = "",
) -> dict:
    lock_key = _build_lock_key(file_hash, requested_fields, scope)
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        # First check whether the completed result is already available.
        result = read_valid_cached_result(
            file_hash,
            requested_fields,
            scope,
        )

        if result is not None:
            return {
                "status": "completed",
                "result": result,
            }

        state = _lock_state(lock_key)

        if state == "unavailable":
            return {                
                "status": "redis_unavailable",
                "result": None,
            }

        # Owner finished/failed and released the lock.
        if state == "free":
            return {
                "status": "lock_released",
                "result": None,
            }

        time.sleep(poll_interval)

    return {
        "status": "timeout",
        "result": None,
    }


def _redis_client():
    """
    Optional Redis client. Raises ``RedisUnavailable`` (a ``redis.RedisError``)
    when Redis is not configured or unreachable, so the existing
    ``except redis.RedisError`` handlers treat it as a normal fallback case.
    """
    return get_redis_client()



def _is_valid_cached_result(result) -> bool:
    """
    Config-agnostic sanity check for a cached extraction result.

    The previous version required the full default field set, which is
    wrong once a dynamic configuration is in play (a config may request
    fewer fields). We now only require a dict whose optional line_items
    (when present) is a list — enough to avoid downstream crashes. The
    config is already isolated by the cache key.
    """
    if not isinstance(result, dict):
        return False

    line_items = result.get("line_items")
    if line_items is not None and not isinstance(line_items, list):
        return False

    return True


def _read_cached_result(file_hash: str, requested_fields: Any, scope: str = ""):
    """
    Backward-compatible wrapper around ``read_valid_cached_result``.

    Accepts the legacy ``config_hash`` signature via ``_config_hash``
    for existing callers, but validates cache metadata before
    returning any result.
    """
    return read_valid_cached_result(file_hash, requested_fields, scope)


def _write_cached_result(
    file_hash: str,
    result: dict,
    requested_fields: Any,
    ttl: int | None = None,
    scope: str = "",
) -> None:
    """
    Backward-compatible wrapper around ``write_completed_cached_result``.

    Accepts the legacy ``config_hash`` signature via ``_config_hash``
    for existing callers.
    """
    write_completed_cached_result(file_hash, requested_fields, result, ttl=ttl, scope=scope)


def _write_live_result(upload_id: str, result: dict) -> None:
    try:
        _redis_client().setex(
            _live_result_key(upload_id),
            OCR_EXTRACTION_CACHE_TTL_SECONDS,
            json.dumps(
                result,
                ensure_ascii=False,
                default=str,
            ),
        )
    except redis.RedisError as exc:
        warn_throttled(
            "ocr-live-result-redis",
            "OCR Redis live-result layer unavailable; results are served "
            "from PostgreSQL instead: %s",
            exc,
        )

# def _begin_processing(upload):
#     """Common 'job started' state transition. Returns the start timestamp."""
def _begin_processing(upload, owner: str = ""):
    """
    Common 'job started' state transition. Returns the start timestamp.

    Also takes/renews the upload's lease so an interrupted job can be
    recognised (lease expired) and recovered.
    """
    started_at = timezone.now()

    upload.status = OCRUpload.Status.PROCESSING
    upload.processing_started_at = started_at
    upload.processing_completed_at = None
    upload.processing_duration_ms = None
    upload.failure_reason = None
    upload.failure_code = ""
    upload.lease_owner = owner or new_owner("inline")
    upload.lease_expires_at = started_at + timedelta(seconds=lease_seconds())
    upload.next_attempt_at = None
    upload.attempt_count = (upload.attempt_count or 0) + 1

    upload.save(
        update_fields=[
            "status",
            "processing_started_at",
            "processing_completed_at",
            "processing_duration_ms",
            "failure_reason",
            "failure_code",
            "lease_owner",
            "lease_expires_at",
            "next_attempt_at",
            "attempt_count",
        ]
    )
    return started_at


def _persist_success(
    upload,
    result: dict,
    requested_fields,
    *,
    started_at,
    write_cache: bool = True,
    scope: str = "",
) -> None:
    """
    Common 'job succeeded' persistence, shared by every execution mode.

    The result is written to the fast Redis layer (optional) AND durably to
    PostgreSQL (``live_result_json``), so a missing/unreachable Redis can
    never lose an extraction result.

    ``write_cache=False`` is for callers that already wrote the extraction
    cache while still holding the extraction lock.
    """
    _validate_extraction_result(result)

    if write_cache:
        _write_cached_result(
            upload.file_hash,
            result,
            requested_fields,
            scope=scope,
        )

    _write_live_result(str(upload.id), result)

    completed_at = timezone.now()

    upload.live_result_json = result
    upload.live_result_expires_at = completed_at + timedelta(
        seconds=OCR_EXTRACTION_CACHE_TTL_SECONDS
    )
    upload.status = OCRUpload.Status.COMPLETED
    upload.processing_completed_at = completed_at
    upload.processing_duration_ms = int(
        (completed_at - (started_at or completed_at)).total_seconds() * 1000
    )
    upload.failure_reason = None
    upload.failure_code = ""
    upload.lease_owner = ""
    upload.lease_expires_at = None
    upload.next_attempt_at = None

    upload.save(
        update_fields=[
            "live_result_json",
            "live_result_expires_at",
            "status",
            "processing_completed_at",
            "processing_duration_ms",
            "failure_reason",
            "failure_code",
            "lease_owner",
            "lease_expires_at",
            "next_attempt_at",
        ]
    )

    if upload.batch_id:
        _refresh_batch_status(upload.batch_id)


def _persist_failure(upload, exc: BaseException) -> FailureInfo:
    """
    Common 'job failed' handling, shared by every execution mode.

    Classifies the error, logs it at the right level (one-line warning for
    expected failures, traceback only for unexpected ones) and stores a
    user-safe reason plus a stable failure code. Never raises: if even the
    failure state cannot be saved, that is logged and swallowed.
    """
    info = classify_failure(exc)
    upload_id = getattr(upload, "id", None)

    if info.expected:
        logger.warning(
            "OCR processing failed — upload=%s code=%s reason=%s",
            upload_id,
            info.code,
            exc,
        )
    else:
        logger.error(
            "OCR processing failed unexpectedly — upload=%s code=%s",
            upload_id,
            info.code,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    if upload is not None:
        try:
            _mark_upload_failed(upload, info.message, info.code)
        except Exception as save_exc:  # noqa: BLE001
            logger.warning(
                "Could not persist OCR failure state — upload=%s reason=%s",
                upload_id,
                save_exc,
            )

    return info


def _refresh_batch_status(batch_id):
    """Reconcile one batch from its child upload states."""
    try:
        batch = OCRBatch.objects.get(pk=batch_id)
    except OCRBatch.DoesNotExist:
        return

    uploads = OCRUpload.objects.filter(batch_id=batch_id)
    total = uploads.count()

    if total == 0:
        batch.status = OCRBatch.Status.FAILED
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "completed_at"])
        return

    completed = uploads.filter(
        status=OCRUpload.Status.COMPLETED
    ).count()
    failed = uploads.filter(
        status=OCRUpload.Status.FAILED
    ).count()
    active = uploads.exclude(
        status__in=[
            OCRUpload.Status.COMPLETED,
            OCRUpload.Status.FAILED,
        ]
    ).exists()

    if completed == total:
        new_status = OCRBatch.Status.COMPLETED
    elif failed == total:
        new_status = OCRBatch.Status.FAILED
    elif failed and not active:
        new_status = OCRBatch.Status.PARTIAL
    else:
        new_status = OCRBatch.Status.PROCESSING

    update_fields = ["status"]
    batch.status = new_status

    if new_status in {
        OCRBatch.Status.COMPLETED,
        OCRBatch.Status.FAILED,
        OCRBatch.Status.PARTIAL,
    }:
        batch.completed_at = timezone.now()
        update_fields.append("completed_at")

    batch.save(update_fields=update_fields)

def _requeue_for_background(upload) -> None:
    """Return an upload to the waiting state so a background executor can take it."""
    upload.status = OCRUpload.Status.UPLOADED
    upload.failure_reason = None
    upload.failure_code = ""
    upload.lease_owner = ""
    upload.lease_expires_at = None
    upload.next_attempt_at = None
    upload.save(
        update_fields=[
            "status",
            "failure_reason",
            "failure_code",
            "lease_owner",
            "lease_expires_at",
            "next_attempt_at",
        ]
    )


def process_single_ocr_upload(
    upload_id: str,
    user_id: str,
    time_budget_seconds: float | None = None,
    handoff_on_budget: bool = False,
) -> dict:
    """
    Process one OCR upload inline (no Celery worker or broker needed).

    Uses the same shared extraction engine and persistence helpers as the
    background path, while enforcing a wall-clock time budget.

    With ``handoff_on_budget=True`` an exhausted time budget is not a failure:
    the upload is returned to the waiting state and ``OCRTimeBudgetExceeded``
    is raised so the caller can hand it to background execution.
    """
    upload = None

    if time_budget_seconds is None:
        time_budget_seconds = getattr(
            settings,
            "OCR_SINGLE_TIME_BUDGET_SECONDS",
            180,
        )

    try:
        upload = OCRUpload.objects.select_related(
            "user",
            "batch",
        ).get(pk=upload_id)

        if str(upload.user_id) != str(user_id):
            logger.error(
                "Single OCR ownership mismatch — upload=%s user=%s owner=%s",
                upload_id,
                user_id,
                upload.user_id,
            )
            raise PermissionError("OCR upload ownership mismatch.")

        requested_fields = (
            upload.batch.requested_fields_json
            if upload.batch
            else None
        )
        scope = _extraction_scope(upload)

        # A completed upload may already have a live result.
        if (
            upload.status == OCRUpload.Status.COMPLETED
            and isinstance(upload.live_result_json, dict)
        ):
            return upload.live_result_json

        started_at = _begin_processing(upload)

        deadline_monotonic = time.monotonic() + float(time_budget_seconds)

        # Reuse a valid extraction cache when available.
        result = _read_cached_result(
            upload.file_hash,
            requested_fields,
            scope=scope,
        )

        if result is None:
            result = _perform_ocr_extraction_sync(
                upload,
                requested_fields,
                deadline_monotonic=deadline_monotonic,
            )

        _validate_extraction_result(result)

        _persist_success(
            upload,
            result,
            requested_fields,
            started_at=started_at,
            write_cache=True,
            scope=scope,
        )

        logger.info(
            "Single OCR extraction completed — upload=%s",
            upload_id,
        )

        return result

    except OCRUpload.DoesNotExist:
        logger.warning(
            "Single OCR upload not found — upload_id=%s",
            upload_id,
        )
        raise

    except PermissionError:
        # Never change the state of an upload the caller does not own.
        raise

    except OCRTimeBudgetExceeded:
        if handoff_on_budget and upload is not None:
            logger.info(
                "Inline OCR time budget exhausted; handing over to background "
                "processing — upload=%s",
                upload_id,
            )
            _requeue_for_background(upload)
            raise
        _persist_failure(upload, sys.exc_info()[1])
        raise

    except Exception as exc:
        _persist_failure(upload, exc)
        raise

# try:
#     from celery import shared_task

@dataclass
class JobOutcome:
    """Result of one execution attempt of an upload job."""
    # @shared_task(
    #     bind=True,
    #     max_retries=5,
    #     default_retry_delay=30,
    #     acks_late=True,
    #     reject_on_worker_lost=True,
    # )
    # def process_ocr_upload_task(
    #     self,
    #     upload_id: str,
    #     user_id: str,
    # ) -> None:
    #     """
    #     Process one uploaded OCR file.
    status: str  # "done" | "failed" | "retry" | "skipped"
    exc: BaseException | None = None
    countdown: float = 0.0

        # Celery provides async execution. Redis provides a global
        # concurrency/RPM limiter shared across all workers.
        # """
        # upload = None
        # limiter = GeminiQuotaLimiter()
        # token = None

        # try:
        #     upload = OCRUpload.objects.select_related(
        #         "user",
        #         "batch",
        #     ).get(pk=upload_id)

        #     if str(upload.user_id) != str(user_id):
        #         logger.error(
        #             "OCR task ownership mismatch — upload=%s user=%s upload_owner=%s",
        #             upload_id,
        #             user_id,
        #             upload.user_id,
        #         )
        #         return

def execute_upload_job(
    upload_id: str,
    user_id: str,
    *,
    owner: str,
    request_id: str,
    retries: int = 0,
    max_retries: int = 5,
    claim: bool = False,
) -> JobOutcome:
    """
    Run one background OCR job: cache -> extraction lock -> global Gemini
    limiter -> extraction -> persistence.

            # if upload.status == OCRUpload.Status.COMPLETED:
            #     _refresh_batch_status(upload.batch_id)
            #     return

     This is the single implementation behind every background executor
    (Celery task, in-process worker threads, ``run_ocr_worker``). It never
    raises for a failed document and never schedules the retry itself: a
    retryable failure is reported as ``JobOutcome("retry", countdown=...)``
    and the executor decides how to re-run it.
    ``claim=True`` makes the start atomic (exactly one executor can run a
    given upload), which the non-Celery executors rely on.
    """

    upload = None
    limiter = GeminiQuotaLimiter()
    token = None
    heartbeat = None
    outcome = JobOutcome("done")

    try:
        upload = OCRUpload.objects.select_related(
            "user",
            "batch",
        ).get(pk=upload_id)

        if str(upload.user_id) != str(user_id):
            logger.error(
                "OCR task ownership mismatch — upload=%s user=%s upload_owner=%s",
                upload_id,
                user_id,
                upload.user_id,
            )
            return JobOutcome("skipped")

        if upload.status == OCRUpload.Status.COMPLETED:
            _refresh_batch_status(upload.batch_id)
            return JobOutcome("skipped")

        if claim and not claim_upload(upload.id, owner):
            logger.info(
                "OCR upload already claimed or not runnable; skipping — upload=%s",
                upload_id,
            )
            return JobOutcome("skipped")

        started_at = _begin_processing(upload, owner)
        heartbeat = LeaseHeartbeat(upload.id, owner)
        heartbeat.start()

        # Optional distributed gate. The Gemini call normally starts only
        # after both concurrency and rolling-RPM checks pass; if the
        # limiter backend (Redis) is unavailable we continue without the
        # global limiter instead of failing the document.
        try:
            token = limiter.acquire(
                request_id=f"{upload.id}:{request_id}"
            )
        except Exception as limiter_exc:  # noqa: BLE001
            token = None
            logger.warning(
                "Gemini rate limiter unavailable; continuing without the "
                "global limiter — upload=%s reason=%s",
                upload.id,
                limiter_exc,
            )

        requested_fields = upload.batch.requested_fields_json if upload.batch else None
        scope = _extraction_scope(upload)
        result = _read_cached_result(
            upload.file_hash,
            requested_fields,
            scope=scope,
        )

        if result is None:
                # IMPORTANT: acquire the distributed extraction lock exactly
            # once. The previous implementation called acquire twice;
            # the first call acquired the lock and the second call then
            # saw the same worker's lock as HELD and waited on itself.
            lock_status, extraction_lock_token = acquire_extraction_lock(
                 upload.file_hash,
                 requested_fields,
                 scope=scope,
             )

            if lock_status == ExtractionLockStatus.HELD:
                logger.info(
                    "OCR extraction lock held by another worker — "
                    "waiting for concurrent extraction — upload=%s file_hash=%s",
                    upload.id,
                    upload.file_hash,
                )

                wait_result = wait_for_extraction_lock(
                    upload.file_hash,
                    requested_fields,
                    scope=scope,
                )
                if wait_result["status"] == "completed":
                    result = wait_result["result"]

                elif wait_result["status"] == "lock_released":
                    retry_status, retry_token = acquire_extraction_lock(
                        upload.file_hash,
                        requested_fields,
                        scope=scope,
                    )
                    if retry_status == ExtractionLockStatus.ACQUIRED:
                        extraction_lock_token = retry_token
                    elif retry_status == ExtractionLockStatus.UNAVAILABLE:
                        extraction_lock_token = None
                    else:
                        second_wait = wait_for_extraction_lock(
                            upload.file_hash,
                            requested_fields,
                            scope=scope,
                            timeout=min(
                                OCR_EXTRACTION_LOCK_MAX_WAIT_SECONDS,
                                30,
                            ),
                        )
                        if second_wait["status"] == "completed":
                            result = second_wait["result"]
                        elif second_wait["status"] == "redis_unavailable":
                            extraction_lock_token = None
                        else:
                            raise TimeoutError(
                                "Another OCR extraction is still in progress."
                            )

                elif wait_result["status"] == "redis_unavailable":
                    extraction_lock_token = None

                elif wait_result["status"] == "timeout":
                    # A slow concurrent extraction must not turn into a
                    # false OCR failure. Re-check cache, then make one
                    # bounded attempt to take over if the lock is free.
                    result = _read_cached_result(
                         upload.file_hash,
                         requested_fields,
                         scope=scope,
                     )

                    if result is None:
                        retry_status, retry_token = acquire_extraction_lock(
                            upload.file_hash,
                            requested_fields,
                            scope=scope,
                        )

                        if retry_status == ExtractionLockStatus.ACQUIRED:
                            extraction_lock_token = retry_token
                        elif retry_status == ExtractionLockStatus.UNAVAILABLE:
                            extraction_lock_token = None
                        else:
                            second_wait = wait_for_extraction_lock(
                                upload.file_hash,
                                requested_fields,
                                scope=scope,
                                timeout=min(
                                    OCR_EXTRACTION_LOCK_MAX_WAIT_SECONDS,
                                    30,
                                ),
                            )
                            if second_wait["status"] == "completed":
                                result = second_wait["result"]
                            elif second_wait["status"] == "redis_unavailable":
                                extraction_lock_token = None
                            else:
                                raise TimeoutError(
                                    "Another OCR extraction is still in progress."
                                )
            elif lock_status == ExtractionLockStatus.UNAVAILABLE:
                logger.warning(
                    "Redis lock unavailable; proceeding without distributed "
                    "OCR extraction lock — upload=%s file_hash=%s",
                    upload.id,
                    upload.file_hash,
                )
                extraction_lock_token = None

            # If no result came from cache/concurrent extraction, execute
            # the real OCR extraction. Always release the lock afterward.
            if result is None:
                heartbeat = None
                try:
                    if extraction_lock_token:
                        heartbeat = ExtractionLockHeartbeat(
                            upload.file_hash,
                            requested_fields,
                            extraction_lock_token,
                            scope=scope,
                        )
                        heartbeat.start()

                    result = _perform_ocr_extraction(
                        upload,
                        requested_fields,
                    )

                    _validate_extraction_result(result)

                    _write_cached_result(
                         upload.file_hash,
                        result,
                        requested_fields,
                        scope=scope,
                    )
                finally:
                    if heartbeat is not None:
                        heartbeat.stop()

                    release_extraction_lock(
                        upload.file_hash,
                        requested_fields,
                        extraction_lock_token,
                        scope=scope,
                    )
        else:
            logger.info(
                "OCR result cache hit — upload=%s file_hash=%s",
                upload.id,
                upload.file_hash,
            )
        # IMPORTANT: AI extraction is a review-stage result. It is kept as
        # the upload's live result (Redis + PostgreSQL) and is only
        # written to the OCR document tables when the user reviews and
        # explicitly clicks Save.
        _persist_success(
            upload,
            result,
            requested_fields,
            started_at=started_at,
            write_cache=False,  # already cached while holding the lock
            scope=scope,
        )

        logger.info(
            "OCR extraction completed — upload=%s; result is awaiting user review/save",
            upload_id,
        )
    except (
        GeminiRateLimitException,
        GeminiTimeoutException,
        GeminiConnectionException,
    ) as exc:
        if upload is None:
            raise

        info = classify_failure(exc)

        # Terminal failures (e.g. daily quota exhaustion) are never
        # retried: retrying only burns worker time.
        if not info.retryable:
            _mark_upload_failed(upload, info.message, info.code)
            logger.warning(
                "OCR terminal failure — upload=%s code=%s",
                upload_id,
                info.code,
            )
            return JobOutcome("failed")

        # Temporary rate limits, network failures and timeouts are
        # retryable. After the final retry the upload becomes a terminal
        # FAILED state so it can never remain stuck as UPLOADED.
        if retries >= max_retries:
            _mark_upload_failed(
                upload,
                f"{info.message} (gave up after {retries + 1} attempts)",
                info.code,
            )
            logger.warning(
                "OCR retry limit exhausted — upload=%s retries=%s code=%s reason=%s",
                upload_id,
                retries,
                info.code,
                exc,
            )
            return JobOutcome("failed")

        base = float(getattr(settings, "OCR_JOB_RETRY_BASE_SECONDS", 15))
        countdown = min(
            base * (2 ** retries) + random.uniform(0, min(5.0, base)),
            900,
        )         

        # Hand the upload back to the queue: no lease, retry not before
        # ``next_attempt_at`` (also lets recovery find it if the retry
        # message/timer is lost).
        upload.status = OCRUpload.Status.UPLOADED
        upload.failure_reason = info.message
        upload.failure_code = info.code
        upload.lease_owner = ""
        upload.lease_expires_at = None
        upload.next_attempt_at = timezone.now() + timedelta(seconds=countdown)
        upload.save(
            update_fields=[
                "status",
                "failure_reason",
                "failure_code",
                "lease_owner",
                "lease_expires_at",
                "next_attempt_at",
            ]
        )
        logger.warning(
            "Retryable OCR failure — upload=%s retry=%d "
            "countdown=%.1fs code=%s reason=%s",
            upload_id,
            retries,
            countdown,
            info.code,
            exc,
        )   
        return JobOutcome("retry", exc=exc, countdown=countdown)
    
    except OCRUpload.DoesNotExist:
        logger.warning(
            "OCR upload not found — upload_id=%s",
            upload_id,
        )
        outcome = JobOutcome("skipped")
    
    except Exception as exc:
        _persist_failure(upload, exc)
        outcome = JobOutcome("failed")
    
    finally:
        if heartbeat is not None:
            heartbeat.stop()
        
        if token is not None:
            limiter.release(token)

    return outcome

try:
    from celery import shared_task

    # ignore_result: the outcome lives in PostgreSQL, so publishing/finishing
    # a task must not depend on the (Redis) result backend being reachable.
    @shared_task(
        bind=True,
        max_retries=5,
        default_retry_delay=30,
        acks_late=True,
        reject_on_worker_lost=True,
        ignore_result=True,
    )
    def process_ocr_upload_task(
        self,
        upload_id: str,
        user_id: str,
    ) -> None:
        """
        Celery entry point for one uploaded OCR file.

        Thin wrapper over ``execute_upload_job``; Celery only provides the
        queueing and retry scheduling.
        """
        request_id = self.request.id or uuid.uuid4().hex

        outcome = execute_upload_job(
            upload_id,
            user_id,
            owner=f"celery:{request_id}",
            request_id=request_id,
            retries=self.request.retries,
            max_retries=self.max_retries,
        )
        if outcome.status == "retry":
            raise self.retry(exc=outcome.exc, countdown=outcome.countdown)

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def retry_stage_task(
        self,
        document_id: str,
        stage: str,
    ) -> None:
        """Re-run a single IDP pipeline stage."""
        try:
            document = OCRDocument.objects.get(pk=document_id)
        except OCRDocument.DoesNotExist:
            logger.error("Document %s not found.", document_id)
            return

        metadata = document.processing_metadata or {}
        retries = metadata.get("retry_count", 0) + 1
        metadata["retry_count"] = retries
        metadata["last_retried_stage"] = stage

        document.processing_metadata = metadata
        document.save(update_fields=["processing_metadata"])

        logger.info(
            "Retrying stage %s for document %s — attempt %d",
            stage,
            document_id,
            retries,
        )

    @shared_task
    def cleanup_task() -> None:
        """
        Recover OCR uploads whose worker died.
        Only uploads whose lease expired are touched (a running job keeps
        renewing its lease); they are re-queued, or failed once interrupted
        too many times.
        """
        from ocr.execution import recover_batch

        changed = recover_batch()

        if changed:
            logger.info("cleanup_task recovered %d interrupted uploads.", changed)

except ImportError:  # pragma: no cover
    def process_ocr_upload_task(upload_id: str, user_id: str) -> None:
        logger.warning(
            "Celery not installed; running OCR synchronously is unavailable."
        )

    def retry_stage_task(document_id: str, stage: str) -> None:
        logger.warning("Celery not installed; retry_stage_task is unavailable.")

    def cleanup_task() -> None:
        logger.warning("Celery not installed; cleanup_task is unavailable.")