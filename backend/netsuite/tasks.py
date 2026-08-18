from __future__ import annotations

import logging

from celery import shared_task

from netsuite.services import NetSuiteReferenceSyncService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_netsuite_reference_data(self, connection_id: str) -> None:
    """Sync NetSuite master/reference IDs for one connected account."""
    try:
        result = NetSuiteReferenceSyncService().sync_connection(
            connection_id=connection_id,
        )
        logger.info(
            "NetSuite reference sync completed — connection=%s counts=%s errors=%s",
            connection_id,
            result.get("counts", {}),
            result.get("errors", []),
        )
    except Exception as exc:
        retries = self.request.retries
        logger.exception(
            "NetSuite reference sync failed — connection=%s retry=%d error=%s",
            connection_id,
            retries,
            exc,
        )
        raise self.retry(
            exc=exc,
            countdown=min(60 * (2 ** retries), 900),
        )