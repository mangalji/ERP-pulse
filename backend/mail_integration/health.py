"""Check that the email scheduler can actually dispatch work to a worker."""

import redis
from django.conf import settings

from mail_integration.exceptions import EmailIntegrationStateError

HEARTBEAT_KEY = "agsuite:mail-integration:beat-worker-heartbeat"
HEARTBEAT_TTL_SECONDS = 90


def _broker_redis():
    return redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2)


def record_scheduler_heartbeat():
    _broker_redis().set(HEARTBEAT_KEY, "1", ex=HEARTBEAT_TTL_SECONDS)


def email_processing_status():
    """Return worker and beat state for the integration UI without raising."""
    result = {
        "worker_running": False,
        "scheduler_running": False,
        "message": "",
    }
    try:
        broker = _broker_redis()
        broker.ping()
    except Exception as exc:
        result["message"] = "Cannot reach the Celery Redis broker."
        return result

    try:
        from config.celery import app
        workers = app.control.inspect(timeout=2).ping()
        result["worker_running"] = bool(workers)
    except Exception:
        result["message"] = "Cannot verify a Celery worker."
        return result
    if not workers:
        result["message"] = "No Celery worker responded."
        return result
    try:
        result["scheduler_running"] = bool(broker.exists(HEARTBEAT_KEY))
    except Exception:
        result["message"] = "Cannot verify the email scheduler through Redis."
        return result
    if not result["scheduler_running"]:
        result["message"] = "Email scheduler is not responding. Start Celery Beat and wait up to 30 seconds."
    return result


def ensure_email_processing_available():
    status = email_processing_status()
    if status["worker_running"] and status["scheduler_running"]:
        return
    if status["message"] == "Cannot reach the Celery Redis broker.":
        raise EmailIntegrationStateError("Cannot reach the Celery Redis broker. Start Redis and try again.")
    if not status["worker_running"]:
        raise EmailIntegrationStateError("No Celery worker responded. Start the worker and try again.")
    raise EmailIntegrationStateError("Email scheduler is not responding. Start Celery Beat and wait up to 30 seconds before trying again.")
