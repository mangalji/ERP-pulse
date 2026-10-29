"""Middleware that makes request evidence available to audit events."""

from audit.context import reset_request_context, set_request_context


class AuditRequestContextMiddleware:
    """Attach safe request metadata to all audit writes in this request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_request_context(request)
        try:
            return self.get_response(request)
        finally:
            reset_request_context(token)
