"""
Builds the business context passed to the AI provider.

Per AI_CONTEXT.md ("Facts come from analytics. Explanations come from
AI.") and the explicit rule for this task, this module never fabricates
business data. `netsuite_connected` reflects a real, current check against
the user's actual NetSuiteConnection (reusing netsuite's own repository
rather than querying the model directly here, per DRY) — it is not
hardcoded, since hardcoding it would become an outright lie the moment a
real connection exists. `business_context` stays None until a future task
adds real NetSuite data fetching (an analytics layer, per AI_CONTEXT.md's
"AI receives structured metrics only" rule) — that data-fetching step is
explicitly out of scope today.
"""

from accounts.models import User
from netsuite.repositories import NetSuiteConnectionRepository

_connection_repository = NetSuiteConnectionRepository()


def build_context(user: User) -> dict:
    connection = _connection_repository.get_by_user(user)
    netsuite_connected = bool(connection and connection.is_active)

    return {
        'netsuite_connected': netsuite_connected,
        'business_context': None,
    }
