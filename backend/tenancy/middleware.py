"""
Tenant middleware — attaches the current Company to each request.

Sets ``request.company`` from the authenticated user's ``company`` FK.
If the user is unauthenticated or has no company, ``request.company``
is ``None``.

This middleware does NOT change authentication or authorization flow.
It only enriches the request object with tenant context for downstream
use (view scoping, audit logging, module access checks, etc.).
"""


class TenantMiddleware:
    """Attach ``request.company`` for authenticated users with a company."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        company = None
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            company = getattr(user, 'company', None)
        request.company = company
        return self.get_response(request)