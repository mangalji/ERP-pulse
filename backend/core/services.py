"""
Base service class for AGSuite ERP.

Provides a thin ``BaseService`` that establishes the service-layer
convention without imposing any business logic. Services across the
project (``AuthenticationService``, ``NetSuiteConnectionService``,
``OCRService``, ``AIService``, ``SyncManager``, ``DashboardService``,
``AnalyticsService``) already follow a consistent pattern: instantiated
once (or per-request), delegate to repositories, and never touch the
HTTP layer.

``BaseService`` formalizes this pattern for new services. Existing
services are intentionally NOT migrated to inherit from it — they
continue to work as-is so no existing imports break.

Usage::

    from core.services import BaseService

    class MyService(BaseService):
        def __init__(self, repository=None):
            self.repository = repository or MyRepository()

        def do_something(self, *, user):
            ...
"""

import logging

logger = logging.getLogger(__name__)


class BaseService:
    """
    Abstract base for service-layer classes.

    This class intentionally has no business logic, no repository
    injection, and no model imports — it exists only to:
    1. Establish the convention that services have a ``logger``.
    2. Provide a consistent ``__init__`` pattern for subclasses.
    3. Serve as a marker class for type hints and documentation.
    """

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__module__)