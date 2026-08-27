"""
OCR processing tasks.

Existing IDP pipeline tasks are preserved.
The test OCR batch processor uses the approved notebook Gemini extractor,
Redis quota limiting, and per-file persistence.
"""

from __future__ import annotations
import time
import hashlib
import json
import mimetypes
import logging
import random
import redis
import uuid
from typing import Any
import mimetypes
from django.utils import timezone
from django.conf import settings

from ocr.exceptions import (
    GeminiConnectionException,
    GeminiRateLimitException,
    GeminiTimeoutException,
)
from ocr.models import OCRBatch, OCRDocument, OCRUpload
from ocr.notebook_extraction_service import notebook_gemini_extractor
from ocr.adapters import get_adapter
from ocr.services.gemini_quota_limiter import GeminiQuotaLimiter
from ocr.services.pipeline_service import idp_pipeline_service

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
    """Return True for a project/model daily-quota exhaustion response.

    Daily free-tier quota exhaustion is not a transient rate limit. Retrying
    repeatedly only burns worker time and leaves the OCR upload in a queued
    state indefinitely. It should become a terminal FAILED result.
    """
    message = str(exc).lower()

    return any(
        marker in message
        for marker in (
            'generate_content_free_tier_requests',
            'generaterequestsperdaypermodel-freetier',
            'generaterequestsperdayperprojectpermodel-freetier',
            'daily quota',
            'quota exceeded for metric',
        )
    )


def _mark_upload_failed(upload, reason: str) -> None:
    completed_at = timezone.now()

    upload.status = OCRUpload.Status.FAILED
    upload.processing_completed_at = completed_at
    upload.failure_reason = str(reason)[:5000]

    update_fields = [
        "status",
        "processing_completed_at",
        "failure_reason",
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


def _perform_ocr_extraction(upload, requested_fields):
    """
    Normalize every supported document format before sending it to Gemini.

    The Gemini vision extractor must never receive raw DOCX/XLSX/CSV/TXT
    binaries. The central adapter layer converts supported documents into
    AI-consumable page images; each page then uses the same dynamic OCR
    requested_fields -> prompt/schema -> normalization contract.
    """
    original_path = upload.file.path
    adapter = get_adapter(original_path, str(upload.id))

    try:
        normalized = adapter.normalize()

        if not isinstance(normalized, dict):
            raise ValueError(
                "Document adapter returned an invalid normalized result."
            )

        pages = normalized.get("pages") or []
        if isinstance(pages, (str, bytes)):
            pages = [pages]

        page_paths = [str(path) for path in pages if path]

        if not page_paths:
            fallback_path = normalized.get("path") or original_path
            if fallback_path:
                page_paths = [str(fallback_path)]

        if not page_paths:
            raise ValueError(
                f"Document adapter produced no pages for '{upload.original_filename}'."
            )

        page_results = []

        for page_index, page_path in enumerate(page_paths, start=1):
            mime_type, _ = mimetypes.guess_type(page_path)
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/png"

            result = notebook_gemini_extractor.extract(
                file_path=page_path,
                mime_type=mime_type,
                requested_fields=requested_fields,
            )

            if not isinstance(result, dict):
                raise ValueError(
                    f"OCR extractor returned an invalid result on page {page_index}."
                )

            line_items = result.get("line_items")
            if line_items is not None and not isinstance(line_items, list):
                raise ValueError(
                    f"OCR extractor returned invalid line_items on page {page_index}."
                )

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


def build_ocr_cache_identity(file_hash: str, requested_fields: Any) -> dict:
    """
    Build the complete cache identity for an extraction request.

    The identity captures:
    - document identity (file_hash)
    - extraction configuration (config_hash)
    - extraction contract version

    This identity is stored as metadata alongside the cached result
    and validated on every cache read.
    """
    return {
        "document_identity": file_hash,
        "config_hash": build_extraction_config_hash(requested_fields),
        "contract_version": build_extraction_contract_version(),
        "status": "COMPLETED",
    }


def build_ocr_cache_key(file_hash: str, requested_fields: Any) -> str:
    """
    Build a deterministic Redis cache key that includes all identity
    components.

    Format:
        erp-pulse:ocr:file-result:<cache_version>:<contract_version>:<config_hash>:<file_hash>
    """
    identity = build_ocr_cache_identity(file_hash, requested_fields)
    return (
        f"erp-pulse:ocr:file-result:"
        f"{OCR_EXTRACTION_CACHE_VERSION}:"
        f"{identity['contract_version']}:"
        f"{identity['config_hash']}:"
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


def read_valid_cached_result(file_hash: str, requested_fields: Any):
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
        expected_identity = build_ocr_cache_identity(file_hash, requested_fields)
        cache_key = build_ocr_cache_key(file_hash, requested_fields)
        cached = _redis_client().get(cache_key)

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

    except Exception:
        logger.exception(
            "OCR result cache read failed — file_hash=%s",
            file_hash,
        )
        return None


def write_completed_cached_result(
    file_hash: str,
    requested_fields: Any,
    result: dict,
    ttl: int | None = None,
) -> None:
    """
    Write a completed OCR result to cache with full identity metadata.

    Only completed results should be cached. The payload includes
    validation metadata so stale or mismatched entries are rejected
    on read.
    """
    try:
        cache_key = build_ocr_cache_key(file_hash, requested_fields)
        identity = build_ocr_cache_identity(file_hash, requested_fields)
        payload = {
            "metadata": identity,
            "result": result,
        }
        _redis_client().setex(
            cache_key,
            ttl or OCR_EXTRACTION_CACHE_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False, default=str),
        )
    except Exception:
        logger.exception(
            "OCR result cache write failed — file_hash=%s",
            file_hash,
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


def _build_lock_key(file_hash: str, requested_fields: Any) -> str:
    """
    Build a deterministic Redis lock key for an extraction identity.

    Format:
        erp-pulse:ocr:lock:<cache_version>:<contract_version>:<config_hash>:<file_hash>
    """
    identity = build_ocr_cache_identity(file_hash, requested_fields)
    return (
        f"erp-pulse:ocr:lock:"
        f"{OCR_EXTRACTION_CACHE_VERSION}:"
        f"{identity['contract_version']}:"
        f"{identity['config_hash']}:"
        f"{file_hash}"
    )

from enum import Enum


class ExtractionLockStatus(str, Enum):
    ACQUIRED = "acquired"
    HELD = "held"
    UNAVAILABLE = "unavailable"


# def acquire_extraction_lock(file_hash: str, requested_fields: Any) -> tuple[ExtractionLockStatus, str | None]:
#     """
#     Acquire a Redis lock for the given extraction identity.

#     Uses Redis SET NX EX (atomic) to ensure only one worker can hold
#     the lock for a given extraction identity at a time.

#     Returns:
#         Ownership token on success, None if lock is already held.

#     The lock has a finite TTL so crashed workers cannot block forever.
#     """
#     try:
#         lock_key = _build_lock_key(file_hash, requested_fields)
#         token = f"{timezone.now().timestamp()}:{uuid.uuid4().hex[:8]}"
#         # SET NX EX — atomic, only succeeds if key does not exist
#         acquired = _redis_client().set(
#             lock_key,
#             token,
#             nx=True,
#             ex=OCR_EXTRACTION_LOCK_TTL_SECONDS,
#         )
#         return token if acquired else None
#     except Exception:
#         logger.exception(
#             "OCR extraction lock acquisition failed — file_hash=%s",
#             file_hash,
#         )
#         return None

def acquire_extraction_lock(
    file_hash: str,
    requested_fields: Any,
) -> tuple[ExtractionLockStatus, str | None]:
    """
    Try to acquire the extraction lock.

    Returns:
        (ACQUIRED, token)
        (HELD, None)
        (UNAVAILABLE, None)
    """
    try:
        lock_key = _build_lock_key(file_hash, requested_fields)
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

    except redis.RedisError:
        logger.exception(
            "Redis unavailable while acquiring OCR extraction lock — file_hash=%s",
            file_hash,
        )
        return ExtractionLockStatus.UNAVAILABLE, None

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
) -> bool:
    if not token:
        return False

    try:
        lock_key = _build_lock_key(file_hash, requested_fields)

        result = _redis_client().eval(
            _RENEW_LOCK_SCRIPT,
            1,
            lock_key,
            token,
            OCR_EXTRACTION_LOCK_TTL_SECONDS,
        )

        return bool(result)

    except redis.RedisError:
        logger.exception(
            "OCR extraction lock renewal failed — file_hash=%s",
            file_hash,
        )
        return False

import threading

class ExtractionLockHeartbeat:
    def __init__(
        self,
        file_hash: str,
        requested_fields: Any,
        token: str,
    ) -> None:
        self.file_hash = file_hash
        self.requested_fields = requested_fields
        self.token = token
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
            )

            if not renewed:
                self.lost = True
                logger.error(
                    "OCR extraction lock ownership lost — file_hash=%s",
                    self.file_hash,
                )
                return

    def stop(self) -> None:
        self.stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

def release_extraction_lock(file_hash: str, requested_fields: Any, token: str | None) -> None:
    """
    Release a Redis lock only if the caller is the owner.

    Uses a Lua script for atomic check-and-delete to prevent releasing
    another worker's lock.
    """
    if not token:
        return
    try:
        lock_key = _build_lock_key(file_hash, requested_fields)
        # Lua script: only delete if value matches token (owner check)
        lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
        """
        _redis_client().eval(lua, 1, lock_key, token)
    except Exception:
        logger.exception(
            "OCR extraction lock release failed — file_hash=%s",
            file_hash,
        )


# def wait_for_extraction_lock(
#     file_hash: str,
#     requested_fields: Any,
#     timeout: int = OCR_EXTRACTION_LOCK_MAX_WAIT_SECONDS,
#     poll_interval: int = OCR_EXTRACTION_LOCK_POLL_INTERVAL_SECONDS,
# ) -> dict | None:
#     """
#     Wait for another worker to complete an extraction and write its
#     cache result.

#     Polls the cache at the given interval until:
#     - A valid completed result appears (return it)
#     - The lock disappears (another worker may have failed, return None)
#     - Timeout expires (return None)

#     Never blocks indefinitely.
#     """
#     deadline = timezone.now().timestamp() + timeout
#     while timezone.now().timestamp() < deadline:
#         result = read_valid_cached_result(file_hash, requested_fields)
#         if result is not None:
#             return result
#         time.sleep(poll_interval)
#     return None

def wait_for_extraction_lock(
    file_hash: str,
    requested_fields: Any,
    timeout: int = OCR_EXTRACTION_LOCK_MAX_WAIT_SECONDS,
    poll_interval: int = OCR_EXTRACTION_LOCK_POLL_INTERVAL_SECONDS,
) -> dict:
    lock_key = _build_lock_key(file_hash, requested_fields)
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        # First check whether the completed result is already available.
        result = read_valid_cached_result(
            file_hash,
            requested_fields,
        )

        if result is not None:
            return {
                "status": "completed",
                "result": result,
            }

        try:
            lock_exists = bool(
                _redis_client().exists(lock_key)
            )
        except redis.RedisError:
            logger.exception(
                "Redis unavailable while waiting for OCR extraction lock — file_hash=%s",
                file_hash,
            )
            return {
                "status": "redis_unavailable",
                "result": None,
            }

        # Owner finished/failed and released the lock.
        if not lock_exists:
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
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )



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


def _read_cached_result(file_hash: str, requested_fields: Any):
    """
    Backward-compatible wrapper around ``read_valid_cached_result``.

    Accepts the legacy ``config_hash`` signature via ``_config_hash``
    for existing callers, but validates cache metadata before
    returning any result.
    """
    return read_valid_cached_result(file_hash, requested_fields)


def _write_cached_result(
    file_hash: str,
    result: dict,
    requested_fields: Any,
    ttl: int | None = None,
) -> None:
    """
    Backward-compatible wrapper around ``write_completed_cached_result``.

    Accepts the legacy ``config_hash`` signature via ``_config_hash``
    for existing callers.
    """
    write_completed_cached_result(file_hash, requested_fields, result, ttl=ttl)


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
    except Exception:
        logger.exception(
            "OCR live-result cache write failed — upload_id=%s",
            upload_id,
        )


def _sync_raw_result_snapshot(version, result: dict) -> None:
    version.raw_ocr = result
    version.normalized_json = result

    version.save(
        update_fields=[
            "raw_ocr",
            "normalized_json",
        ]
    )

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


try:
    from celery import shared_task

    @shared_task(
        bind=True,
        max_retries=5,
        default_retry_delay=30,
        acks_late=True,
        reject_on_worker_lost=True,
    )
    def process_test_ocr_upload_task(
        self,
        upload_id: str,
        user_id: str,
    ) -> None:
        """
        Process one uploaded OCR file.

        Celery provides async execution. Redis provides a global
        concurrency/RPM limiter shared across all workers.
        """
        upload = None
        limiter = GeminiQuotaLimiter()
        token = None

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
                return

            if upload.status == OCRUpload.Status.COMPLETED:
                _refresh_batch_status(upload.batch_id)
                return

            upload.status = OCRUpload.Status.PROCESSING
            upload.processing_started_at = timezone.now()
            upload.processing_completed_at = None
            upload.failure_reason = None
            upload.save(
                update_fields=[
                    "status",
                    "processing_started_at",
                    "processing_completed_at",
                    "failure_reason",
                ]
            )

            # This is the distributed global gate. The actual Gemini call
            # starts only after both concurrency and rolling-RPM checks pass.
            token = limiter.acquire(
                request_id=f"{upload.id}:{self.request.id}"
            )

            requested_fields = upload.batch.requested_fields_json if upload.batch else None
            result = _read_cached_result(
                upload.file_hash,
                requested_fields,
            )

            if result is None:
                # IMPORTANT: acquire the distributed extraction lock exactly
                # once. The previous implementation called acquire twice;
                # the first call acquired the lock and the second call then
                # saw the same worker's lock as HELD and waited on itself.
                lock_status, extraction_lock_token = acquire_extraction_lock(
                    upload.file_hash,
                    requested_fields,
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
                    )

                    if wait_result["status"] == "completed":
                        result = wait_result["result"]

                    elif wait_result["status"] == "lock_released":
                        retry_status, retry_token = acquire_extraction_lock(
                            upload.file_hash,
                            requested_fields,
                        )

                        if retry_status == ExtractionLockStatus.ACQUIRED:
                            extraction_lock_token = retry_token
                        elif retry_status == ExtractionLockStatus.UNAVAILABLE:
                            extraction_lock_token = None
                        else:
                            second_wait = wait_for_extraction_lock(
                                upload.file_hash,
                                requested_fields,
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
                        )

                        if result is None:
                            retry_status, retry_token = acquire_extraction_lock(
                                upload.file_hash,
                                requested_fields,
                            )

                            if retry_status == ExtractionLockStatus.ACQUIRED:
                                extraction_lock_token = retry_token
                            elif retry_status == ExtractionLockStatus.UNAVAILABLE:
                                extraction_lock_token = None
                            else:
                                second_wait = wait_for_extraction_lock(
                                    upload.file_hash,
                                    requested_fields,
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
                            )
                            heartbeat.start()

                        result = _perform_ocr_extraction(
                            upload,
                            requested_fields,
                        )

                        if not isinstance(result, dict):
                            raise ValueError(
                                "OCR extractor returned an invalid result shape."
                            )

                        line_items = result.get("line_items")
                        if line_items is not None and not isinstance(line_items, list):
                            raise ValueError(
                                "OCR extractor returned invalid line_items."
                            )

                        _write_cached_result(
                            upload.file_hash,
                            result,
                            requested_fields,
                        )
                    finally:
                        if heartbeat is not None:
                            heartbeat.stop()

                        release_extraction_lock(
                            upload.file_hash,
                            requested_fields,
                            extraction_lock_token,
                        )

            else:
                logger.info(
                    "OCR result cache hit — upload=%s file_hash=%s",
                    upload.id,
                    upload.file_hash,
                )
            _write_live_result(
                str(upload.id),
                result,
            )
            # IMPORTANT: AI extraction is now a review-stage result.
            # Do not persist it to the OCR document tables here. The user must
            # review/edit the result and explicitly click Save before a
            # database version is created.

            completed_at = timezone.now()
            upload.status = OCRUpload.Status.COMPLETED
            upload.processing_completed_at = completed_at
            upload.processing_duration_ms = int(
                (
                    completed_at
                    - upload.processing_started_at
                ).total_seconds()
                * 1000
            )
            upload.failure_reason = None
            upload.save(
                update_fields=[
                    "status",
                    "processing_completed_at",
                    "processing_duration_ms",
                    "failure_reason",
                ]
            )

            logger.info(
                "Test OCR extraction completed — upload=%s; result is awaiting user review/save",
                upload_id,
            )

            _refresh_batch_status(upload.batch_id)

        except (
            GeminiRateLimitException,
            GeminiTimeoutException,
            GeminiConnectionException,
        ) as exc:
            if upload is None:
                raise

            # A daily project/model quota exhaustion is terminal for this
            # request. Do NOT retry it indefinitely.
            if isinstance(exc, GeminiRateLimitException) and _is_daily_gemini_quota_error(exc):
                _mark_upload_failed(
                    upload,
                    "Gemini daily API quota has been exhausted. "
                    "Please try again after the quota resets or use an "
                    "available Gemini API plan/model.",
                )

                logger.error(
                    "Terminal Gemini daily quota failure — upload=%s",
                    upload_id,
                )
                return

            # Temporary rate limits, network failures, and timeouts are
            # retryable. After the final allowed retry, convert the upload to
            # a terminal FAILED state so it can never remain stuck as UPLOADED.
            retries = self.request.retries

            if retries >= self.max_retries:
                _mark_upload_failed(
                    upload,
                    f"Gemini extraction failed after {retries + 1} attempts: {exc}",
                )

                logger.error(
                    "OCR retry limit exhausted — upload=%s retries=%s",
                    upload_id,
                    retries,
                )
                return

            upload.status = OCRUpload.Status.UPLOADED
            upload.failure_reason = str(exc)[:5000]
            upload.save(
                update_fields=["status", "failure_reason"]
            )

            countdown = min(
                15 * (2 ** retries) + random.uniform(0, 5),
                900,
            )

            logger.warning(
                "Retryable OCR failure — upload=%s retry=%d "
                "countdown=%.1fs error=%s",
                upload_id,
                retries,
                countdown,
                exc,
            )

            raise self.retry(exc=exc, countdown=countdown)

        except OCRUpload.DoesNotExist:
            logger.error(
                "Test OCR upload not found — upload_id=%s",
                upload_id,
            )

        except Exception as exc:
            logger.exception(
                "Test OCR processing failed — upload=%s error=%s",
                upload_id,
                exc,
            )

            if upload is not None:
                completed_at = timezone.now()
                upload.status = OCRUpload.Status.FAILED
                upload.processing_completed_at = completed_at
                upload.failure_reason = str(exc)[:5000]

                update_fields = [
                    "status",
                    "processing_completed_at",
                    "failure_reason",
                ]

                if upload.processing_started_at:
                    upload.processing_duration_ms = int(
                        (
                            completed_at
                            - upload.processing_started_at
                        ).total_seconds()
                        * 1000
                    )
                    update_fields.append("processing_duration_ms")

                upload.save(update_fields=update_fields)
                _refresh_batch_status(upload.batch_id)

        finally:
            if token is not None:
                limiter.release(token)

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def process_document_task(self, upload_id: str, user_id: int) -> None:
        """Run the full existing IDP pipeline asynchronously."""
        retries = self.request.retries
        logger.info(
            "OCR pipeline started — upload_id=%s user_id=%s retry=%d",
            upload_id,
            user_id,
            retries,
        )

        try:
            upload = OCRUpload.objects.select_related(
                "user"
            ).get(pk=upload_id)

            user = upload.user if upload.user_id == user_id else None

            if user is None:
                logger.error(
                    "User %s does not own upload %s.",
                    user_id,
                    upload_id,
                )
                return

            upload.status = OCRUpload.Status.PROCESSING
            upload.save(update_fields=["status"])

            result = idp_pipeline_service.process_upload(
                upload_id=upload_id,
                user=user,
            )

            logger.info(
                "OCR pipeline completed — upload_id=%s document=%s status=%s",
                upload_id,
                result.get("document_id"),
                result.get("status"),
            )

        except OCRUpload.DoesNotExist:
            logger.error(
                "OCR pipeline failed — upload not found — upload_id=%s",
                upload_id,
            )
            return

        except Exception as exc:
            logger.exception(
                "OCR pipeline failed — upload_id=%s retry=%d error=%s",
                upload_id,
                retries,
                exc,
            )
            raise self.retry(
                exc=exc,
                countdown=2 ** retries * 60,
            )

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
        """Clean up stale OCR uploads stuck in PROCESSING."""
        stale = OCRUpload.objects.filter(
            status=OCRUpload.Status.PROCESSING
        )
        updated = stale.update(status=OCRUpload.Status.FAILED)

        if updated:
            logger.info(
                "cleanup_task marked %d stale uploads as FAILED.",
                updated,
            )

except ImportError:  # pragma: no cover
    def process_test_ocr_upload_task(upload_id: str, user_id: str) -> None:
        logger.warning(
            "Celery not installed; running test OCR synchronously is unavailable."
        )

    def process_document_task(upload_id: str, user_id: int) -> None:
        logger.warning("Celery not installed; process_document_task is unavailable.")

    def retry_stage_task(document_id: str, stage: str) -> None:
        logger.warning("Celery not installed; retry_stage_task is unavailable.")

    def cleanup_task() -> None:
        logger.warning("Celery not installed; cleanup_task is unavailable.")