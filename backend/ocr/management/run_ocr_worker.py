"""
Dedicated OCR worker that needs only PostgreSQL (no Celery, no Redis).

Run it as a second process on any host (VM, ECS/Cloud Run job, Render
background worker, docker compose service ...) and set
``OCR_EXECUTION_MODE=external`` on the web process so uploads are only
queued by the web app and executed here.

    python manage.py run_ocr_worker              # run forever
    python manage.py run_ocr_worker --once       # drain the queue, then exit
    python manage.py run_ocr_worker --interval 5

Several worker processes can run side by side: each upload is claimed
atomically, and an upload whose worker died is recovered automatically.
"""

import logging
import signal
import threading

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from ocr.execution import claim_and_run_next, reset_stale_processing

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run queued OCR uploads from PostgreSQL (no Celery/Redis needed)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process everything that is runnable now, then exit.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=3.0,
            help="Seconds to sleep when the queue is empty (default 3).",
        )

    def handle(self, *args, **options):
        stop = threading.Event()

        def _request_stop(signum, frame):  # noqa: ARG001
            logger.info("OCR worker received signal %s; stopping after current job", signum)
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _request_stop)
            except ValueError:  # not in the main thread (tests)
                pass

        once = options["once"]
        interval = max(0.5, options["interval"])

        self.stdout.write("OCR worker started (PostgreSQL queue; Ctrl+C to stop).")

        while not stop.is_set():
            ran = False
            try:
                close_old_connections()
                reset_stale_processing()
                ran = claim_and_run_next("worker")
            except Exception:  # noqa: BLE001 - keep the worker alive
                logger.error("OCR worker iteration failed", exc_info=True)

            if ran:
                continue  # more work may be waiting

            if once:
                break

            stop.wait(interval)

        self.stdout.write("OCR worker stopped.")