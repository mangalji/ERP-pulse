from __future__ import annotations

import logging
import redis

from celery import shared_task
from django.conf import settings

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

BATCH_MAX_DOCUMENTS = 100
BATCH_JOB_TTL_SECONDS = 60 * 60 * 24
BATCH_ACTIONS = {"validate", "post"}

def _batch_job_redis():
    return redis.Redis.from_url(
        settings.CELERY_RESULT_BACKEND,
        decode_responses=True,
    )


def _batch_job_access_key(task_id: str) -> str:
    return f"erp-pulse:netsuite:batch-job:{task_id}"


def _store_batch_job_owner(task_id: str, user_id: str, action: str) -> None:
    _batch_job_redis().setex(
        _batch_job_access_key(task_id),
        BATCH_JOB_TTL_SECONDS,
        f"{user_id}:{action}",
    )


def get_batch_job_owner(task_id: str):
    raw = _batch_job_redis().get(_batch_job_access_key(task_id))
    if not raw:
        return None

    try:
        user_id, action = raw.split(":", 1)
    except ValueError:
        return None

    if action not in BATCH_ACTIONS:
        return None

    return {"user_id": user_id, "action": action}


def _run_netsuite_batch(
    *,
    task,
    action: str,
    document_ids: list[str],
    user_id: str,
    connection_id: str | None = None,
) -> dict:
    from accounts.models import User
    from netsuite.services import (
        NetSuiteValidationService,
        NetSuiteVendorBillPostingService,
    )

    if action not in BATCH_ACTIONS:
        raise ValueError("Unsupported NetSuite batch action.")

    if len(document_ids) > BATCH_MAX_DOCUMENTS:
        raise ValueError(
            f"A maximum of {BATCH_MAX_DOCUMENTS} documents can be processed per batch."
        )

    user = User.objects.get(pk=user_id)

    results = []
    completed = 0

    for document_id in document_ids:
        result = {
            "document_id": str(document_id),
            "status": "FAILED",
            "error": None,
        }

        try:
            if action == "validate":
                service_result = NetSuiteValidationService().validate_document(
                    document_id=document_id,
                    user=user,
                )
                result.update(
                    {
                        "status": service_result.get("status", "VALIDATION_FAILED"),
                        "validation_id": service_result.get("validation_id"),
                        "errors": service_result.get("errors", []),
                    }
                )
            else:
                service_result = NetSuiteVendorBillPostingService().post_vendor_bill(
                    document_id=document_id,
                    user=user,
                    connection_id=connection_id,
                )
                result.update(
                    {
                        "status": (
                            "ALREADY_POSTED"
                            if service_result.get("already_posted")
                            else "POSTED"
                        ),
                        "posting_id": service_result.get("posting_id"),
                        "netsuite_record_id": service_result.get(
                            "netsuite_record_id"
                        ),
                        "already_posted": bool(
                            service_result.get("already_posted")
                        ),
                    }
                )

        except Exception as exc:
            logger.exception(
                "NetSuite batch %s item failed — action=%s document=%s user=%s",
                action,
                document_id,
                user_id,
            )
            result["error"] = str(exc)[:2000]

        results.append(result)
        completed += 1

        task.update_state(
            state="PROGRESS",
            meta={
                "action": action,
                "user_id": str(user_id),
                "total": len(document_ids),
                "completed": completed,
                "succeeded": sum(
                    1
                    for item in results
                    if item["status"] in {
                        "VALIDATED",
                        "POSTED",
                        "ALREADY_POSTED",
                    }
                ),
                "failed": sum(1 for item in results if item["error"]),
                "results": results[-25:],
            },
        )

    return {
        "action": action,
        "user_id": str(user_id),
        "total": len(document_ids),
        "completed": completed,
        "succeeded": sum(
            1
            for item in results
            if item["status"] in {
                "VALIDATED",
                "POSTED",
                "ALREADY_POSTED",
            }
        ),
        "failed": sum(1 for item in results if item["error"]),
        "results": results,
    }


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def batch_validate_documents_task(self, document_ids, user_id):
    """Validate up to 100 OCR documents without depending on the browser."""
    try:
        normalized_ids = [str(value) for value in document_ids]
        return _run_netsuite_batch(
            task=self,
            action="validate",
            document_ids=normalized_ids,
            user_id=str(user_id),
        )
    except Exception as exc:
        logger.exception(
            "NetSuite batch validation job failed — task=%s user=%s",
            self.request.id,
            user_id,
        )
        raise self.retry(exc=exc, countdown=15)


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def batch_post_documents_task(
    self,
    document_ids,
    user_id,
    connection_id=None,
):
    """Post up to 100 validated OCR documents from a Celery worker."""
    try:
        normalized_ids = [str(value) for value in document_ids]
        return _run_netsuite_batch(
            task=self,
            action="post",
            document_ids=normalized_ids,
            user_id=str(user_id),
            connection_id=str(connection_id) if connection_id else None,
        )
    except Exception as exc:
        logger.exception(
            "NetSuite batch posting job failed — task=%s user=%s",
            self.request.id,
            user_id,
        )
        raise self.retry(exc=exc, countdown=15)