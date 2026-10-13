from __future__ import annotations

import logging
from celery import shared_task
from django.conf import settings

from netsuite.services import NetSuiteReferenceSyncService
from netsuite.models import NetSuiteConnection
from tenancy.services import company_lifecycle_service
from netsuite.exceptions import NetSuiteTokenExchangeException

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

BATCH_MAX_DOCUMENTS = int(
    getattr(
        settings,
        "NETSUITE_OCR_BATCH_MAX_DOCUMENTS",
        200,
    )
)
BATCH_JOB_TTL_SECONDS = 60 * 60 * 24
BATCH_ACTIONS = {"validate", "post"}

def _is_batch_success(status: str) -> bool:
    return status in {
        "VALIDATED",
        "POSTED",
        "ALREADY_POSTED",
    }


def _is_batch_failure(
    status: str,
    error: str | None = None,
) -> bool:
    return (
        bool(error)
        or status in {
            "FAILED",
            "VALIDATION_FAILED",
        }
    )

def _is_success_status(status: str) -> bool:
    return status in {
        "VALIDATED",
        "POSTED",
        "ALREADY_POSTED",
    }


def _is_failed_status(
    status: str,
    error=None,
) -> bool:
    return (
        bool(error)
        or status in {
            "FAILED",
            "VALIDATION_FAILED",
        }
    )

def _expected_item_errors() -> tuple:
    """Exception types that mean "this document was rejected", not "bug"."""
    import netsuite.exceptions as ns_exceptions
    from django.core.exceptions import ValidationError as DjangoValidationError
    from ocr.exceptions import OCRException
    from rest_framework.exceptions import APIException

    domain = tuple(
        value
        for value in vars(ns_exceptions).values()
        if isinstance(value, type)
        and issubclass(value, Exception)
        and value.__module__ == ns_exceptions.__name__
    )
    return domain + (APIException, DjangoValidationError, OCRException)



def _run_netsuite_batch(
    *,
    task,
    action: str,
    document_ids: list[str],
    user_id: str,
    connection_id: str | None = None,
    resume_results: list | None = None,
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

    # A resumed job keeps the documents already processed and skips them
    # (posting is idempotent, but there is no reason to repeat NetSuite calls).
    results = list(resume_results or [])
    done_ids = {str(item.get("document_id")) for item in results}
    completed = len(results)

    for document_id in document_ids:
        if str(document_id) in done_ids:
            continue


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
                    connection_id=connection_id,
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

        except NetSuiteTokenExchangeException:
            logger.warning(
                "NetSuite batch item needs reconnect — action=%s document=%s user=%s",
                action,
                document_id,
                user_id,
            )
            result["error"] = (
                "NetSuite connection needs reconnecting. "
                "Ask a Company Admin to reconnect it, then retry."
            )
            result["code"] = "NETSUITE_REAUTH_REQUIRED"

        except Exception as exc:
            if isinstance(exc, _expected_item_errors()):
                # A document NetSuite/validation rejected: an expected outcome
                # reported to the user, not a bug -> one-line warning.
                logger.warning(
                    "NetSuite batch item rejected — action=%s document=%s "
                    "user=%s reason=%s",
                    action,
                    document_id,
                    user_id,
                    exc,
                )
            else:
                logger.exception(
                    "NetSuite batch item failed unexpectedly — action=%s "
                    "document=%s user=%s",
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
                    # if item["status"] in {
                    #     "VALIDATED",
                    #     "POSTED",
                    #     "ALREADY_POSTED",
                    # }
                    if _is_success_status(
                        item["status"]
                    )
                ),
                "failed": sum(
                    1 for item in results if _is_batch_failure(
                        item["status"],
                        item.get("error")
                    )
                ),
                "results": results[-25:],
                # full list so a crashed job can be resumed from the DB
                "all_results": results,
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
            if _is_success_status(
                item.get("status")
            )
        ),
        "failed": sum(
            1 for item in results if _is_batch_failure(
                item.get("status",""),
                item.get("error"),
            )
        ),
        "results": results,
    }
@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def run_netsuite_batch_job_task(self, job_id):
    """
    Celery entry point for one NetSuite batch job (validate or post).

    All state lives in ``NetSuiteBatchJob`` (PostgreSQL); Celery only provides
    the queueing, so the job also runs without Celery/Redis (see
    ``netsuite.jobs``).
    """
    from netsuite.jobs import run_batch_job

    outcome = run_batch_job(
        str(job_id),
        owner=f"celery:{self.request.id}",
        claim=False,
    )

    if outcome == "retry":
            raise self.retry(countdown=15)