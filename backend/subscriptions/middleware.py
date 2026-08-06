"""
License enforcement middleware.

Checks every request for:
- Company active status
- Subscription active
- Module access
- Usage limits
"""

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework import status

from subscriptions.utils import LicenseError


class LicenseMiddleware(MiddlewareMixin):
    """
    Middleware to enforce subscription and license checks.
    
    Skips auth endpoints, admin, and static/media files.
    """

    EXEMPT_PATHS = (
        '/admin/',
        '/static/',
        '/media/',
        '/api/v1/auth/',
        '/api/v1/demo/submit/',
        '/api/v1/invitations/',
        '/api/v1/subscriptions/plans/',
        '/api/v1/subscriptions/my/',
        '/api/v1/subscriptions/my-usage/',
        '/api/v1/subscriptions/my-modules/',
    )

    def process_request(self, request):
        # Skip exempt paths
        for path in self.EXEMPT_PATHS:
            if request.path.startswith(path):
                return None

        # Skip if no user
        if not request.user or not request.user.is_authenticated:
            return None

        # Skip super admins
        if request.user.is_superuser or request.user.is_staff:
            return None

        company = getattr(request.user, 'company', None)
        if not company:
            return None

        # Check company status
        if company.status == Company.Status.SUSPENDED:
            return JsonResponse(
                {'detail': 'Company account is suspended. Please contact support.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if company.status == Company.Status.EXPIRED:
            return JsonResponse(
                {'detail': 'Company subscription has expired. Please renew your plan.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check active subscription
        subscription = subscription_service.get_active_subscription(company_id=company.id)
        if not subscription:
            return JsonResponse(
                {'detail': 'No active subscription. Please contact support.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check module access based on path
        module_code = self._get_module_from_path(request.path)
        if module_code:
            try:
                license_service.check_limit(company, module_code)
            except LicenseError as exc:
                return JsonResponse(
                    {'detail': str(exc)},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return None

    @staticmethod
    def _get_module_from_path(path):
        """Map URL path to module code."""
        module_map = {
            '/api/v1/ocr/': 'ocr',
            '/api/v1/ai/': 'ai',
            '/api/v1/reports/': 'reports',
            '/api/v1/bi/': 'bi',
            '/api/v1/netsuite/': 'netsuite',
            '/api/v1/invoice/': 'invoice',
            '/api/v1/client/employees': 'employees',
            '/api/v1/dashboard/': 'dashboard',
        }
        for prefix, code in module_map.items():
            if path.startswith(prefix):
                return code
        return None


# Import here to avoid circular imports
from tenancy.models import Company
from subscriptions.services import subscription_service, license_service
