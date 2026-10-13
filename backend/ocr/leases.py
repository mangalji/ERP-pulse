"""
Job leases for background OCR execution.

A lease says "executor X is processing this upload until time T". A running
job keeps renewing it (``LeaseHeartbeat``); if the process dies the lease
simply expires and the recovery logic (``ocr.execution.recover_batch``) can
safely re-queue the upload. Everything lives in PostgreSQL, so it works the
same behind PgBouncer, on any host and without Redis.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def new_owner(kind: str) -> str:
    """Unique lease owner id, e.g. ``thread:4242:ab12cd34``."""
    return f"{kind}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def lease_seconds() -> int:
    return max(30, int(getattr(settings, "OCR_JOB_LEASE_SECONDS", 300)))

def claim_row(model, pk, owner: str, runnable_statuses) -> bool:
    """
    Atomically take a job row (any model with ``status``, ``lease_owner``,
    ``lease_expires_at`` and ``next_attempt_at``) for execution.

    Succeeds only if the row is in a runnable status, nobody holds a live
    lease on it and any retry delay has elapsed.
    """
    now = timezone.now()

    updated = (
        model.objects.filter(pk=pk, status__in=list(runnable_statuses))
        .filter(Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lt=now))
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .update(
            lease_owner=owner,
            lease_expires_at=now + timedelta(seconds=lease_seconds()),
        )
    )
    return updated == 1



def claim_upload(upload_id, owner: str) -> bool:
    """
    Atomically take an upload for execution.

    Succeeds only if the upload is waiting (UPLOADED / interrupted PROCESSING),
    nobody holds a live lease on it and any retry delay has elapsed. Exactly
    one of several concurrent callers wins.
    """
    from ocr.models import OCRUpload

    now = timezone.now()

    updated = (
        OCRUpload.objects.filter(pk=upload_id)
        .filter(
            Q(status=OCRUpload.Status.UPLOADED)
            | Q(status=OCRUpload.Status.PROCESSING)
        )
        .filter(Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lt=now))
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .update(
            lease_owner=owner,
            lease_expires_at=now + timedelta(seconds=lease_seconds()),
        )
    )
    return updated == 1


class LeaseHeartbeat:
    """Keeps an upload's lease alive while its job runs (daemon thread)."""

    def __init__(
        self,
        upload_id,
        owner: str,
        interval: float | None = None,
        model=None,
    ):
        self.model = model  # default: OCRUpload:
        self.upload_id = upload_id
        self.owner = owner
        self.interval = interval or max(10.0, lease_seconds() / 3)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="ocr-lease-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        from ocr.models import OCRUpload
        model = self.model or OCRUpload

        try:
            while not self._stop.wait(self.interval):
                try:
                    renewed = model.objects.filter(
                        pk=self.upload_id,
                        lease_owner=self.owner,
                    ).update(
                        lease_expires_at=timezone.now()
                        + timedelta(seconds=lease_seconds())
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "OCR lease renewal failed — upload=%s reason=%s",
                        self.upload_id,
                        exc,
                    )
                    continue

                if not renewed:
                    return  # lease no longer ours (finished or taken over)
        finally:
            connection.close()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)