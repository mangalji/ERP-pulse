from rest_framework import status


class EmailIntegrationConfigurationError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class EmailIntegrationStateError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST


class EmailRefreshTokenMissingError(EmailIntegrationStateError):
    """Authorization did not supply the token required for background access."""


class EmailIntegrationOAuthError(Exception):
    status_code = status.HTTP_502_BAD_GATEWAY

    def __init__(self, message, *, authorization_required=False):
        super().__init__(message)
        self.authorization_required = authorization_required


class EmailIntegrationNotFoundError(Exception):
    status_code = status.HTTP_404_NOT_FOUND


class EmailMailboxFetchError(Exception):
    """A provider API request failed while reading a connected mailbox."""

    status_code = status.HTTP_502_BAD_GATEWAY
