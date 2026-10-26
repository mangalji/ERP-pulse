import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from django.db import transaction
from audit.models import Notification

logger = logging.getLogger(__name__)
_activity = ContextVar('notification_activity', default=(None, None))


@contextmanager
def activity_context(activity_type, actor_id=None):
    token = _activity.set((activity_type, actor_id))
    try:
        yield
    finally:
        _activity.reset(token)


def automated_activity(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        with activity_context('automated'):
            return func(*args, **kwargs)
    return wrapped


def notify(user_id, company_id, message, link='', *, activity_type=None, actor_id=None):
    if not user_id or not company_id:
        return
    context_type, context_actor = _activity.get()
    activity_type = activity_type or context_type
    actor_id = (actor_id or context_actor) if activity_type == 'manual' else None
    def create():
        try:
            Notification.objects.create(recipient_id=user_id, company_id=company_id, message=message[:500], link=link[:500], activity_type=activity_type, actor_id=actor_id)
        except Exception:
            logger.exception('Unable to create notification')
    transaction.on_commit(create)


def document_label(document):
    batch = document.batch or (document.upload.batch if document.upload_id else None)
    if batch and batch.source_type == 'EMAIL':
        sender = (batch.source_metadata_json or {}).get('sender') or 'unknown sender'
        return f'email from {sender}'
    if document.upload_id:
        return document.upload.original_filename or 'uploaded file'
    return 'document'
