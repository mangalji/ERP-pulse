"""Provider-neutral OAuth URL and signed-state helpers for mailboxes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing

from mail_integration.exceptions import (
    EmailIntegrationConfigurationError,
    EmailIntegrationStateError,
)
from mail_integration.models import EmailIntegration


STATE_MAX_AGE_SECONDS = 600
_state_signer = signing.TimestampSigner(salt="mail-integration-oauth-state")


@dataclass(frozen=True)
class ProviderOAuthConfig:
    authorize_url: str
    token_url: str
    client_id: str
    client_secret: str
    scopes: tuple[str, ...]


_ZOHO_DATA_CENTERS = {
    "COM": "https://accounts.zoho.com",
    "IN": "https://accounts.zoho.in",
    "EU": "https://accounts.zoho.eu",
    "COM_AU": "https://accounts.zoho.com.au",
    "JP": "https://accounts.zoho.jp",
    "CA": "https://accounts.zohocloud.ca",
    "COM_CN": "https://accounts.zoho.com.cn",
    "AE": "https://accounts.zoho.ae",
    "SA": "https://accounts.zoho.sa",
}


def oauth_config_for(integration: EmailIntegration) -> ProviderOAuthConfig:
    """Return the OAuth endpoints and server credentials for a provider."""
    provider = integration.provider

    if provider == EmailIntegration.Provider.GOOGLE:
        return ProviderOAuthConfig(
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            client_id=integration.oauth_client_id or settings.GOOGLE_MAIL_CLIENT_ID,
            client_secret=integration.oauth_client_secret or settings.GOOGLE_MAIL_CLIENT_SECRET,
            scopes=(
                "openid",
                "email",
                "https://www.googleapis.com/auth/gmail.readonly",
            ),
        )

    if provider == EmailIntegration.Provider.ZOHO:
        data_center = str(
            (integration.provider_metadata or {}).get("zoho_data_center", "IN")
        ).upper()
        accounts_base = _ZOHO_DATA_CENTERS.get(data_center)
        if not accounts_base:
            raise EmailIntegrationConfigurationError(
                "Unsupported Zoho data center."
            )
        return ProviderOAuthConfig(
            authorize_url=f"{accounts_base}/oauth/v2/auth",
            token_url=f"{accounts_base}/oauth/v2/token",
            client_id=integration.oauth_client_id or settings.ZOHO_MAIL_CLIENT_ID,
            client_secret=integration.oauth_client_secret or settings.ZOHO_MAIL_CLIENT_SECRET,
            scopes=(
                "ZohoMail.accounts.READ",
                "ZohoMail.folders.READ",
                "ZohoMail.messages.READ",
            ),
        )

    raise EmailIntegrationConfigurationError("Unsupported email provider.")


def _validate_config(config: ProviderOAuthConfig) -> None:
    if not settings.EMAIL_OAUTH_REDIRECT_URI:
        raise EmailIntegrationConfigurationError(
            "EMAIL_OAUTH_REDIRECT_URI is not configured."
        )
    if not config.client_id or not config.client_secret:
        raise EmailIntegrationConfigurationError(
            "Email OAuth client credentials are not configured for this provider."
        )


def validate_oauth_configuration(*, integration: EmailIntegration) -> None:
    """Fail before creating or reconnecting a mailbox with incomplete OAuth settings."""
    _validate_config(oauth_config_for(integration))


def build_authorization_url(*, integration: EmailIntegration, user_id: str) -> str:
    config = oauth_config_for(integration)
    _validate_config(config)

    payload = json.dumps(
        {
            "user_id": str(user_id),
            "integration_id": str(integration.id),
            "provider": integration.provider,
        },
        separators=(",", ":"),
    )
    state = _state_signer.sign(payload)
    query = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": settings.EMAIL_OAUTH_REDIRECT_URI,
        "scope": " ".join(config.scopes)
        if integration.provider == EmailIntegration.Provider.GOOGLE
        else ",".join(config.scopes),
        "state": state,
        "access_type": "offline",
    }
    if integration.provider == EmailIntegration.Provider.GOOGLE or (
        integration.provider == EmailIntegration.Provider.ZOHO
        and (not integration.refresh_token or integration.status == EmailIntegration.Status.ERROR)
    ):
        # Zoho issues another refresh token on explicit consent; avoid asking
        # again when an existing Zoho connection already has a usable token.
        query["prompt"] = "consent"

    return f"{config.authorize_url}?{urlencode(query)}"


def resolve_state(state: str) -> dict[str, str]:
    if not state:
        raise EmailIntegrationStateError("Missing OAuth state parameter.")
    try:
        payload = _state_signer.unsign(state, max_age=STATE_MAX_AGE_SECONDS)
        decoded = json.loads(payload)
    except signing.SignatureExpired as exc:
        raise EmailIntegrationStateError(
            "Email authorization has expired. Please reconnect the mailbox."
        ) from exc
    except (signing.BadSignature, json.JSONDecodeError) as exc:
        raise EmailIntegrationStateError("Invalid OAuth state parameter.") from exc

    if not isinstance(decoded, dict) or not all(
        isinstance(decoded.get(key), str) and decoded[key]
        for key in ("user_id", "integration_id", "provider")
    ):
        raise EmailIntegrationStateError("Invalid OAuth state parameter.")
    return decoded
