from __future__ import annotations

import logging

from celery import shared_task

from netsuite.services import NetSuiteReferenceSyncService
from netsuite.models import NetSuiteConnection
from tenancy.services import company_lifecycle_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_netsuite_reference_data(self, connection_id: str) -> None:
    """Sync NetSuite master/reference IDs for one connected account."""

    try:
        connection = (
            NetSuiteConnection.objects
            .select_related('user__company')
            .get(pk=connection_id)
        )
    except NetSuiteConnection.DoesNotExist:
        logger.error(
            "NetSuite reference sync skipped — connection=%s not found.",
            connection_id,
        )
        return

    company = getattr(connection.user, 'company', None)

    if company is not None:
        try:
            company_lifecycle_service.ensure_operational(
                company=company
            )
        except ValueError as exc:
            logger.info(
                "NetSuite reference sync skipped — company=%s is not operational: %s",
                company.id,
                exc,
            )
            return

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