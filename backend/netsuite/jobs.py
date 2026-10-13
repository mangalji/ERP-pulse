"""
NetSuite batch jobs without a hard Celery/Redis dependency.

Job state is a ``NetSuiteBatchJob`` row in PostgreSQL. Execution reuses the
OCR executor ladder (``ocr.execution``): Celery when a worker is detected,
otherwise an in-process worker thread, otherwise inline; ``external`` mode
leaves the job for ``manage.py run_ocr_worker``. A job whose worker died is
resumed from the per-document results already stored (posting is idempotent
and finished documents are skipped).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from common.infra import warn_throttled
from netsuite.models import NetSuiteBatchJob
from ocr.execution import (
    Mode,
    _BackgroundPool,
    configured_mode,
    report_celery_failure,
    resolve_mode,
)
from ocr.leases import LeaseHeartbeat, claim_row, lease_seconds, new_owner

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 15
_RUNNABLE = (NetSuiteBatchJob.STATUS_PENDING, NetSuiteBatchJob.STATUS_PROGRESS)

# Separate (small) pool: a long posting batch must not starve OCR threads.
_pool = _BackgroundPool("NETSUITE_BACKGROUND_WORKERS", 1, "ns-bg")


def create_job(*, user, action: str, document_ids, connection_id=None) -> NetSuiteBatchJob:
    return NetSuiteBatchJob.objects.create(
        user=user,
        action=action,
        document_ids=list(document_ids),
        connection_id=str(connection_id) if connection_id else None,
        total=len(document_ids),
    )


class _DBProgress:
    """Stands in for the Celery task object: persists progress to the DB."""

    def __init__(self, job_id) -> None:
        self.job_id = job_id

    def update_state(self, state=None, meta=None, **_):
        meta = meta or {}
        NetSuiteBatchJob.objects.filter(pk=self.job_id).update(
            status=NetSuiteBatchJob.STATUS_PROGRESS,
            completed=meta.get("completed", 0),
            succeeded=meta.get("succeeded", 0),
            failed=meta.get("failed", 0),
            results=meta.get("all_results", meta.get("results", [])),
            lease_expires_at=timezone.now() + timedelta(seconds=lease_seconds()),
        )


def run_batch_job(job_id, *, owner: str, claim: bool = True) -> str:
    """
    Run one job. Returns "done", "failed", "retry" or "skipped".
    Never raises for a failed batch.
    """
    from netsuite.tasks import _run_netsuite_batch

    job = NetSuiteBatchJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.warning("NetSuite batch job not found — job=%s", job_id)
        return "skipped"

    if job.status in (NetSuiteBatchJob.STATUS_SUCCESS, NetSuiteBatchJob.STATUS_FAILURE):
        return "skipped"

    if claim and not claim_row(NetSuiteBatchJob, job.pk, owner, _RUNNABLE):
        return "skipped"

    now = timezone.now()
    NetSuiteBatchJob.objects.filter(pk=job.pk).update(
        status=NetSuiteBatchJob.STATUS_PROGRESS,
        lease_owner=owner,
        lease_expires_at=now + timedelta(seconds=lease_seconds()),
        next_attempt_at=None,
        attempt_count=job.attempt_count + 1,
    )
    job.refresh_from_db()

    heartbeat = LeaseHeartbeat(job.pk, owner, model=NetSuiteBatchJob)
    heartbeat.start()

    try:
        final = _run_netsuite_batch(
            task=_DBProgress(job.pk),
            action=job.action,
            document_ids=[str(value) for value in job.document_ids],
            user_id=str(job.user_id),
            connection_id=job.connection_id,
            resume_results=job.results or None,
        )
        NetSuiteBatchJob.objects.filter(pk=job.pk).update(
            status=NetSuiteBatchJob.STATUS_SUCCESS,
            total=final["total"],
            completed=final["completed"],
            succeeded=final["succeeded"],
            failed=final["failed"],
            results=final["results"],
            error="",
            lease_owner="",
            lease_expires_at=None,
        )
        return "done"

    except ValueError as exc:
        # Deterministic problem (bad action / too many documents): no retry.
        logger.warning("NetSuite batch job rejected — job=%s reason=%s", job.pk, exc)
        NetSuiteBatchJob.objects.filter(pk=job.pk).update(
            status=NetSuiteBatchJob.STATUS_FAILURE,
            error=str(exc)[:500],
            lease_owner="",
            lease_expires_at=None,
        )
        return "failed"

    except Exception:  # noqa: BLE001
        logger.error(
            "NetSuite batch job failed unexpectedly — job=%s attempt=%s",
            job.pk,
            job.attempt_count,
            exc_info=True,
        )
        if job.attempt_count < MAX_ATTEMPTS:
            NetSuiteBatchJob.objects.filter(pk=job.pk).update(
                status=NetSuiteBatchJob.STATUS_PENDING,
                lease_owner="",
                lease_expires_at=None,
                next_attempt_at=timezone.now() + timedelta(seconds=RETRY_DELAY_SECONDS),
            )
            return "retry"

        NetSuiteBatchJob.objects.filter(pk=job.pk).update(
            status=NetSuiteBatchJob.STATUS_FAILURE,
            error="The batch job failed unexpectedly. Please try again.",
            lease_owner="",
            lease_expires_at=None,
        )
        return "failed"

    finally:
        heartbeat.stop()


def _run_in_thread(job_id: str, kind: str = "thread") -> None:
    outcome = run_batch_job(job_id, owner=new_owner(kind), claim=True)
    if outcome == "retry" and kind == "thread":
        _pool.submit(_run_in_thread, job_id, kind, delay=RETRY_DELAY_SECONDS)


def _mark_queued(job_id, via: str) -> None:
    NetSuiteBatchJob.objects.filter(pk=job_id).update(
        queued_at=timezone.now(),
        queued_via=via,
    )


def dispatch_job(job_id) -> str:
    """Hand a job to the best available executor; never raises."""
    job_id = str(job_id)
    mode = resolve_mode()

    if mode == Mode.CELERY:
        try:
            from netsuite.tasks import run_netsuite_batch_job_task

            run_netsuite_batch_job_task.delay(job_id)
            _mark_queued(job_id, Mode.CELERY)
            return Mode.CELERY
        except Exception as exc:  # noqa: BLE001
            report_celery_failure(exc)
            warn_throttled(
                "ns-celery-publish-failed",
                "Could not enqueue NetSuite batch job on Celery (%s); using "
                "background threads",
                type(exc).__name__,
            )
            mode = Mode.THREAD

    if mode == Mode.EXTERNAL:
        _mark_queued(job_id, Mode.EXTERNAL)
        return Mode.EXTERNAL

    if mode == Mode.THREAD:
        try:
            _mark_queued(job_id, Mode.THREAD)
            _pool.submit(_run_in_thread, job_id, Mode.THREAD)
            return Mode.THREAD
        except Exception as exc:  # noqa: BLE001
            warn_throttled(
                "ns-thread-submit-failed",
                "Could not start a NetSuite background thread (%s); running inline",
                type(exc).__name__,
            )

    _mark_queued(job_id, Mode.INLINE)
    run_batch_job(job_id, owner=new_owner("inline"), claim=True)
    return Mode.INLINE


def _waiting_jobs(user_id=None):
    now = timezone.now()
    qs = NetSuiteBatchJob.objects.filter(status=NetSuiteBatchJob.STATUS_PENDING)
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    return qs.filter(
        Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lt=now)
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))


def reset_stale_jobs(user_id=None) -> int:
    """Interrupted jobs (PROGRESS, lease expired) go back to PENDING."""
    now = timezone.now()
    qs = NetSuiteBatchJob.objects.filter(
        status=NetSuiteBatchJob.STATUS_PROGRESS,
    ).filter(Q(lease_expires_at__lt=now) | Q(lease_expires_at__isnull=True))
    if user_id is not None:
        qs = qs.filter(user_id=user_id)

    changed = 0
    for job in list(qs[:100]):
        if job.attempt_count >= MAX_ATTEMPTS + 2:
            NetSuiteBatchJob.objects.filter(pk=job.pk).update(
                status=NetSuiteBatchJob.STATUS_FAILURE,
                error="The batch job was interrupted repeatedly and was stopped.",
                lease_owner="",
                lease_expires_at=None,
            )
            changed += 1
            continue
        changed += NetSuiteBatchJob.objects.filter(
            pk=job.pk,
            status=NetSuiteBatchJob.STATUS_PROGRESS,
        ).update(
            status=NetSuiteBatchJob.STATUS_PENDING,
            lease_owner="",
            lease_expires_at=None,
            queued_at=None,
        )
        logger.warning("Recovered interrupted NetSuite batch job — job=%s", job.pk)
    return changed


def recover_jobs(user_id=None) -> int:
    """Self-healing for the status endpoint (and the worker loop)."""
    changed = reset_stale_jobs(user_id)

    if configured_mode() == Mode.EXTERNAL:
        return changed

    now = timezone.now()
    thread_after = timedelta(
        seconds=int(getattr(settings, "OCR_THREAD_REDISPATCH_AFTER_SECONDS", 60))
    )
    celery_after = timedelta(
        seconds=int(getattr(settings, "OCR_CELERY_REDISPATCH_AFTER_SECONDS", 900))
    )
    candidates = _waiting_jobs(user_id).filter(
        Q(queued_at__isnull=True)
        | (Q(queued_via=Mode.CELERY) & Q(queued_at__lt=now - celery_after))
        | (~Q(queued_via=Mode.CELERY) & Q(queued_at__lt=now - thread_after))
    )

    for job in list(candidates[:50]):
        reserved = NetSuiteBatchJob.objects.filter(
            pk=job.pk,
            status=NetSuiteBatchJob.STATUS_PENDING,
            queued_at=job.queued_at,
        ).update(queued_at=now)
        if not reserved:
            continue
        logger.info("Re-dispatching waiting NetSuite batch job — job=%s", job.pk)
        dispatch_job(job.pk)
        changed += 1

    return changed


def claim_and_run_next(kind: str = "worker") -> bool:
    """For the dedicated worker process."""
    for job in _waiting_jobs().order_by("created_at")[:5]:
        if run_batch_job(job.pk, owner=new_owner(kind), claim=True) != "skipped":
            return True
    return False