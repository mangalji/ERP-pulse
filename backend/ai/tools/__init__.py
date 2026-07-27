"""
Tool abstraction: lightweight wrappers around existing services.

Tools contain zero business logic — they only delegate to the appropriate
existing service and return its output as-is. Organised by business domain
(analytics, dashboard, reports, netsuite) so the registry stays clean.
"""

