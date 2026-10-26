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


def ensure_email_processing_available():
    try:
        broker = _broker_redis()
        broker.ping()
    except Exception as exc:
        raise EmailIntegrationStateError("Cannot reach the Celery Redis broker. Start Redis and try again.") from exc

    try:
        from config.celery import app
        workers = app.control.inspect(timeout=2).ping()
    except Exception as exc:
        raise EmailIntegrationStateError("Cannot verify a Celery worker. Start the worker and try again.") from exc
    if not workers:
        raise EmailIntegrationStateError("No Celery worker responded. Start the worker and try again.")
    try:
        heartbeat = broker.exists(HEARTBEAT_KEY)
    except Exception as exc:
        raise EmailIntegrationStateError("Cannot verify the email scheduler through Redis. Try again.") from exc
    if not heartbeat:
        raise EmailIntegrationStateError("Email scheduler is not responding. Start Celery Beat and wait up to 30 seconds before trying again.")
