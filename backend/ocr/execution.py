"""
Background execution for OCR uploads, independent of the hosting platform.

Executors (``OCR_EXECUTION_MODE``)
----------------------------------
auto      Celery if a broker AND a live worker are detected, else threads.
celery    Prefer Celery; still degrades to threads if it is unreachable.
thread    In-process background worker threads (the default fallback).
inline    Run in the calling process (no background execution at all).
external  Only mark the upload as queued; a separate ``manage.py
          run_ocr_worker`` process (any host) picks it up from PostgreSQL.

Every executor runs the very same ``execute_upload_job`` engine, and every
job's state lives in PostgreSQL (status + lease), so it does not matter which
executor was used, or whether the process that started a job is still alive:
``recover_batch`` re-queues interrupted jobs (it is also triggered by the
status polling of the frontend, so it needs no scheduler).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.db import connections
from django.db.models import Q
from django.utils import timezone

from common.infra import warn_throttled
from ocr.leases import lease_seconds, new_owner

logger = logging.getLogger(__name__)


class Mode:
    AUTO = "auto"
    CELERY = "celery"
    THREAD = "thread"
    INLINE = "inline"
    EXTERNAL = "external"


_VALID_MODES = {Mode.AUTO, Mode.CELERY, Mode.THREAD, Mode.INLINE, Mode.EXTERNAL}


# ---------------------------------------------------------------------------
# Celery capability probe (cached)
# ---------------------------------------------------------------------------

_probe_lock = threading.Lock()
_probe_state = {"at": 0.0, "ok": False, "reason": "not probed yet"}


def _probe_celery() -> tuple[bool, str]:
    """Is a Celery broker reachable AND is at least one worker answering?"""
    try:
        from config.celery import app
    except Exception as exc:  # noqa: BLE001
        return False, f"Celery is not importable ({type(exc).__name__})"

    try:
        with app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=1, timeout=2)
    except Exception as exc:  # noqa: BLE001
        return False, f"broker unreachable ({type(exc).__name__})"

    try:
        replies = app.control.ping(timeout=1.0)
    except Exception as exc:  # noqa: BLE001
        return False, f"worker ping failed ({type(exc).__name__})"

    if not replies:
        return False, "no Celery worker answered"

    return True, ""


def celery_available(force: bool = False) -> bool:
    ttl = max(1, int(getattr(settings, "OCR_CELERY_PROBE_SECONDS", 30)))
    now = time.monotonic()

    with _probe_lock:
        fresh = _probe_state["at"] and (now - _probe_state["at"]) < ttl
        if fresh and not force:
            return _probe_state["ok"]

        ok, reason = _probe_celery()
        _probe_state.update(at=time.monotonic(), ok=ok, reason=reason)

    if not ok:
        warn_throttled(
            "celery-unavailable",
            "Celery is not available (%s); OCR jobs run in background "
            "threads instead",
            reason,
        )
    return ok


def report_celery_failure(exc: BaseException) -> None:
    """Mark Celery as down right away (e.g. publishing a task failed)."""
    with _probe_lock:
        _probe_state.update(
            at=time.monotonic(),
            ok=False,
            reason=f"publishing failed ({type(exc).__name__})",
        )


def configured_mode() -> str:
    mode = (getattr(settings, "OCR_EXECUTION_MODE", Mode.AUTO) or Mode.AUTO)
    mode = str(mode).strip().lower()

    if mode not in _VALID_MODES:
        warn_throttled(
            "ocr-bad-execution-mode",
            "Unknown OCR_EXECUTION_MODE=%r; using 'auto'",
            mode,
        )
        return Mode.AUTO

    return mode


def resolve_mode() -> str:
    """The executor that will actually be used right now."""
    mode = configured_mode()

    if mode in (Mode.THREAD, Mode.INLINE, Mode.EXTERNAL):
        return mode

    return Mode.CELERY if celery_available() else Mode.THREAD


def execution_status(probe: bool = True) -> dict:
    """
    Snapshot for health/diagnostics endpoints.

    ``probe=False`` never contacts the broker (health checks must stay fast):
    it reports the last known Celery state instead.
    """
    configured = configured_mode()

    if probe:
        resolved = resolve_mode()
    elif configured in (Mode.THREAD, Mode.INLINE, Mode.EXTERNAL):
        resolved = configured
    elif _probe_state["at"]:
        resolved = Mode.CELERY if _probe_state["ok"] else Mode.THREAD
    else:
        resolved = "unknown (not probed yet)"

    return {
        "configured_mode": configured,
        "resolved_mode": reso,
        "celery_available": _probe_state["ok"],
        "celery_probe_reason": _probe_state["reason"] or None,
        "background_workers": int(getattr(settings, "OCR_BACKGROUND_WORKERS", 2)),
    }


# ---------------------------------------------------------------------------
# In-process background worker pool
# ---------------------------------------------------------------------------


class _BackgroundPool:
    """Small pool of daemon worker threads fed from an in-memory queue."""

    def __init__(self,
        workers_setting: str = "OCR_BACKGROUND_WORKERS",
        default_workers: int = 2,
        prefix: str = "ocr-bg",) -> None:
        self._workers_setting = workers_setting
        self._default_workers = default_workers
        self._prefix = prefix

    def _ensure_started(self) -> None:
        with self._lock:
            workers = max(
                1,
                int(getattr(settings, self._workers_setting, self._default_workers)),
            )
            self._threads = [t for t in self._threads if t.is_alive()]

            while len(self._threads) < workers:
                thread = threading.Thread(
                    target=self._worker,
                    name=f"{self._prefix}-{len(self._threads) + 1}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)

    def submit(self, fn, *args, delay: float = 0.0) -> None:
        self._ensure_started()

        if delay and delay > 0:
            timer = threading.Timer(delay, self._queue.put, args=((fn, args),))
            timer.daemon = True
            timer.start()
        else:
            self._queue.put((fn, args))

    def _worker(self) -> None:
        while True:
            fn, args = self._queue.get()
            try:
                fn(*args)
            except Exception:  # noqa: BLE001
                logger.error("OCR background job crashed", exc_info=True)
            finally:
                # Never keep a database connection open between jobs.
                try:
                    connections.close_all()
                except Exception:  # noqa: BLE001
                    pass


_pool = _BackgroundPool()


def get_pool() -> _BackgroundPool:
    return _pool


# ---------------------------------------------------------------------------
# Running a job
# ---------------------------------------------------------------------------


def run_background_job(upload_id: str, user_id: str, kind: str = "thread"):
    """
    Execute one upload (claim -> engine). A retryable failure is re-scheduled
    on the in-process pool after its back-off delay; if the process dies
    before that, the persisted ``next_attempt_at`` lets recovery re-queue it.
    """
    from ocr.models import OCRUpload
    from ocr.tasks import execute_upload_job

    owner = new_owner(kind)
    attempts_so_far = (
        OCRUpload.objects.filter(pk=upload_id)
        .values_list("attempt_count", flat=True)
        .first()
        or 0
    )

    outcome = execute_upload_job(
        upload_id,
        user_id,
        owner=owner,
        request_id=owner,
        retries=attempts_so_far,
        max_retries=int(getattr(settings, "OCR_JOB_MAX_RETRIES", 5)),
        claim=True,
    )

    if outcome.status == "retry" and kind == "thread":
        get_pool().submit(
            run_background_job,
            upload_id,
            user_id,
            kind,
            delay=outcome.countdown,
        )

    return outcome


def _mark_queued(upload_id: str, via: str) -> None:
    from ocr.models import OCRUpload

    try:
        OCRUpload.objects.filter(pk=upload_id).update(
            queued_at=timezone.now(),
            queued_via=via,
        )
    except Exception as exc:  # noqa: BLE001 - bookkeeping only
        logger.warning(
            "Could not record OCR queue time — upload=%s reason=%s",
            upload_id,
            exc,
        )


def dispatch_upload(upload_id: str, user_id: str) -> str:
    """
    Hand an upload to the best available executor. Never raises: if the
    preferred executor fails, the next one down the ladder is used
    (Celery -> thread -> inline). Returns the executor that took the job.
    """
    mode = resolve_mode()

    if mode == Mode.CELERY:
        try:
            from ocr.tasks import process_ocr_upload_task

            process_ocr_upload_task.delay(str(upload_id), str(user_id))
            _mark_queued(upload_id, Mode.CELERY)
            return Mode.CELERY
        except Exception as exc:  # noqa: BLE001
            report_celery_failure(exc)
            warn_throttled(
                "celery-publish-failed",
                "Could not enqueue OCR job on Celery (%s: %s); falling back "
                "to background threads",
                type(exc).__name__,
                exc,
            )
            mode = Mode.THREAD

    if mode == Mode.EXTERNAL:
        _mark_queued(upload_id, Mode.EXTERNAL)
        return Mode.EXTERNAL

    if mode == Mode.THREAD:
        try:
            _mark_queued(upload_id, Mode.THREAD)
            get_pool().submit(
                run_background_job, str(upload_id), str(user_id), Mode.THREAD
            )
            return Mode.THREAD
        except Exception as exc:  # noqa: BLE001
            warn_throttled(
                "thread-submit-failed",
                "Could not start a background OCR thread (%s: %s); processing "
                "inline instead",
                type(exc).__name__,
                exc,
            )

    # Inline: last resort, runs in the caller's process.
    _mark_queued(upload_id, Mode.INLINE)
    run_background_job(str(upload_id), str(user_id), Mode.INLINE)
    return Mode.INLINE


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


def reset_stale_processing(batch_id=None, *, limit: int = 200) -> int:
    """
    Interrupted jobs (PROCESSING whose lease expired) go back to the waiting
    state, or to FAILED once they were interrupted too many times.
    """
    from ocr.models import OCRUpload
    from ocr.tasks import _mark_upload_failed, _refresh_batch_status

    now = timezone.now()
    max_attempts = int(getattr(settings, "OCR_JOB_MAX_RETRIES", 5)) + 1

    qs = OCRUpload.objects.filter(status=OCRUpload.Status.PROCESSING)
    if batch_id is not None:
        qs = qs.filter(batch_id=batch_id)

    stale = qs.filter(
        Q(lease_expires_at__lt=now)
        | Q(
            lease_expires_at__isnull=True,
            processing_started_at__lt=now - timedelta(seconds=lease_seconds()),
        )
    )

    changed = 0
    for upload in list(stale[:limit]):
        if (upload.attempt_count or 0) >= max_attempts:
            _mark_upload_failed(
                upload,
                "Processing was interrupted repeatedly and was stopped.",
                "INTERNAL",
            )
            if upload.batch_id:
                _refresh_batch_status(upload.batch_id)
            changed += 1
            continue

        # Conditional update: another poller may have recovered it already.
        updated = (
            OCRUpload.objects.filter(pk=upload.pk, status=OCRUpload.Status.PROCESSING)
            .filter(Q(lease_expires_at__lt=now) | Q(lease_expires_at__isnull=True))
            .update(
                status=OCRUpload.Status.UPLOADED,
                lease_owner="",
                lease_expires_at=None,
                queued_at=None,
            )
        )
        if updated:
            logger.warning(
                "Recovered interrupted OCR job — upload=%s attempts=%s",
                upload.pk,
                upload.attempt_count,
            )
            changed += updated

    return changed


def _waiting_uploads(batch_id=None):
    """Uploads that are runnable right now (no live lease, retry delay over)."""
    from ocr.models import OCRUpload

    now = timezone.now()

    qs = OCRUpload.objects.filter(status=OCRUpload.Status.UPLOADED)
    if batch_id is not None:
        qs = qs.filter(batch_id=batch_id)

    return qs.filter(
        Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lt=now)
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))


def recover_batch(batch_id=None, *, limit: int = 200) -> int:
    """
    Self-healing: reset interrupted jobs and re-dispatch jobs that were queued
    but never picked up. Safe to call often (e.g. on every status poll): each
    upload is re-dispatched at most once per redispatch interval, and the
    executors claim uploads atomically, so duplicates are harmless.
    """
    from ocr.models import OCRUpload

    changed = reset_stale_processing(batch_id, limit=limit)

    if configured_mode() == Mode.EXTERNAL:
        return changed  # a dedicated worker process owns dispatching

    now = timezone.now()
    thread_after = timedelta(
        seconds=int(getattr(settings, "OCR_THREAD_REDISPATCH_AFTER_SECONDS", 60))
    )
    celery_after = timedelta(
        seconds=int(getattr(settings, "OCR_CELERY_REDISPATCH_AFTER_SECONDS", 900))
    )

    candidates = _waiting_uploads(batch_id).filter(
        Q(queued_at__isnull=True)
        | (Q(queued_via=Mode.CELERY) & Q(queued_at__lt=now - celery_after))
        | (~Q(queued_via=Mode.CELERY) & Q(queued_at__lt=now - thread_after))
    )

    for upload in list(candidates.select_related("user")[:limit]):
        # Reserve the re-dispatch so concurrent pollers do not all do it.
        reserved = OCRUpload.objects.filter(
            pk=upload.pk,
            status=OCRUpload.Status.UPLOADED,
            queued_at=upload.queued_at,
        ).update(queued_at=now)

        if not reserved:
            continue

        logger.info(
            "Re-dispatching waiting OCR job — upload=%s attempts=%s",
            upload.pk,
            upload.attempt_count,
        )
        dispatch_upload(str(upload.pk), str(upload.user_id))
        changed += 1

    return changed


def claim_and_run_next(kind: str = "worker") -> bool:
    """
    For the dedicated worker process: take the oldest runnable upload and run
    it to completion. Returns False when nothing was runnable.
    """
    for upload in _waiting_uploads().order_by("created_at")[:5]:
        outcome = run_background_job(str(upload.pk), str(upload.user_id), kind)
        if outcome.status != "skipped":
            return True
    return False