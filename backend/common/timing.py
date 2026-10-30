"""Structured, monotonic timings for synchronous workflow stages.

Nested calls share a trace ID in the current execution context. This is local
correlation, not distributed tracing across Celery or thread boundaries.
"""

from contextvars import ContextVar
from functools import wraps
from inspect import signature
import json
import logging
from time import perf_counter
from uuid import uuid4


logger = logging.getLogger("performance")
_current_span = ContextVar("performance_span", default=None)
_id_fields = ("upload_id", "document_id", "message_id", "integration_id", "connection_id")


def timed_stage(stage):
    """Log elapsed time and safe identifiers without logging business payloads.

    'returned' means normal Python return, not business success: a validation
    error or deferred job may legitimately be returned rather than raised.
    """
    def decorate(function):
        call_signature = signature(function)

        @wraps(function)
        def measured(*args, **kwargs):
            if not logger.isEnabledFor(logging.INFO):
                return function(*args, **kwargs)
            parent = _current_span.get()
            identifiers = dict(parent[2]) if parent else {}
            bound = call_signature.bind_partial(*args, **kwargs).arguments
            for key in _id_fields:
                value = bound.get(key)
                if value is not None:
                    identifiers[key] = str(value)
            trace_id = parent[0] if parent else uuid4().hex
            span_id = uuid4().hex
            token = _current_span.set((trace_id, span_id, identifiers))
            started = perf_counter()
            outcome = "returned"
            error_type = None
            try:
                return function(*args, **kwargs)
            except BaseException as exc:
                outcome = "raised"
                error_type = type(exc).__name__
                raise
            finally:
                elapsed = (perf_counter() - started) * 1000
                _current_span.reset(token)
                event = {
                    "event": "stage_timing", "stage": stage,
                    "trace_id": trace_id, "span_id": span_id,
                    "parent_span_id": parent[1] if parent else None,
                    "duration_ms": round(elapsed, 2), "outcome": outcome,
                    **identifiers,
                }
                if error_type:
                    event["error_type"] = error_type
                # Observability must never change the business operation's result.
                try:
                    logger.info("TIMING %s", json.dumps(event, sort_keys=True))
                except Exception:
                    pass

        return measured
    return decorate
