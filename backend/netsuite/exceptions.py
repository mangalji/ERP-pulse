"""
NetSuite integration exceptions.

Each exception carries a `status_code` attribute — the same convention
accounts/exceptions.py already uses — so common/exception_handler.py can
map them to the standard error envelope without importing this module
(common stays app-agnostic; see common/exception_handler.py docstring).
"""

from rest_framework import status


class NetSuiteConfigurationException(Exception):
    """Raised when required NetSuite OAuth environment variables are missing."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class NetSuiteStateMismatchException(Exception):
    """
    Raised when the OAuth `state` parameter on callback is missing,
    expired, or fails signature verification — a potential CSRF attempt
    or a stale/replayed redirect.
    """

    status_code = status.HTTP_400_BAD_REQUEST


class NetSuiteAuthorizationDeniedException(Exception):
    """Raised when the user declines consent on NetSuite's authorization screen."""

    status_code = status.HTTP_400_BAD_REQUEST


class NetSuiteTokenExchangeException(Exception):
    """
    Raised when NetSuite's token endpoint rejects the authorization code
    or refresh token exchange, or when it can't be reached at all.
    """

    status_code = status.HTTP_502_BAD_GATEWAY


class NetSuiteConnectionNotFoundException(Exception):
    """Raised when an operation requires an existing NetSuite connection that doesn't exist."""

    status_code = status.HTTP_404_NOT_FOUND

class NetSuiteConnectionAlreadyExistsException(Exception):
    """
    Raised when a user tries to create a connection for a NetSuite
    account id they already have a connection for.
 
    Checked explicitly in NetSuiteConnectionService.create_connection()
    before the repository write, so this is what the client sees instead
    of the raw IntegrityError from the model's
    (user, netsuite_account_id) unique constraint.
    """
 
    status_code = status.HTTP_409_CONFLICT

class NetSuiteRecordFetchException(Exception):
    """Raised when a NetSuite REST Record API call fails (network error or non-2xx response)."""

    status_code = status.HTTP_502_BAD_GATEWAY

class NetSuiteRecordNotFoundException(Exception):
    """Raised when NetSuite returns 404 for a specific record id (e.g. detail lookups)."""

    status_code = status.HTTP_404_NOT_FOUND