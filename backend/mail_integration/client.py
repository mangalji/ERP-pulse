"""HTTP client for Gmail and Zoho OAuth token endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from mail_integration.exceptions import EmailIntegrationOAuthError
from mail_integration.models import EmailIntegration
from mail_integration.oauth import oauth_config_for, validate_oauth_configuration


@dataclass(frozen=True)
class EmailTokenSet:
    access_token: str
    refresh_token: str | None
    access_token_expires_at: object
    provider_metadata: dict


class EmailOAuthClient:
    """Token exchange and refresh only; mailbox fetch is a later phase."""

    def __init__(self, *, integration: EmailIntegration):
        self.integration = integration
        validate_oauth_configuration(integration=integration)
        self.config = oauth_config_for(integration)

    def exchange_code(self, *, code: str) -> EmailTokenSet:
        return self._request_tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.EMAIL_OAUTH_REDIRECT_URI,
            }
        )

    def refresh_access_token(self) -> EmailTokenSet:
        if not self.integration.refresh_token:
            raise EmailIntegrationOAuthError(
                "The mailbox does not have a refresh token. Reconnect it.",
                authorization_required=True,
            )
        return self._request_tokens(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.integration.refresh_token,
            }
        )

    def authorized_mailbox_identity(self, *, access_token: str) -> tuple[str, dict]:
        """Verify that the OAuth grant belongs to the mailbox being connected."""
        if self.integration.provider == EmailIntegration.Provider.GOOGLE:
            data = self._get_json(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            email = str(data.get("email") or "").strip().lower()
            if not email or data.get("email_verified") is False:
                raise EmailIntegrationOAuthError(
                    "Google did not return a verified mailbox email address."
                )
            return email, {}

        if self.integration.provider == EmailIntegration.Provider.ZOHO:
            data_center = str(
                (self.integration.provider_metadata or {}).get("zoho_data_center", "IN")
            ).upper()
            domains = {
                "COM": "https://mail.zoho.com", "IN": "https://mail.zoho.in",
                "EU": "https://mail.zoho.eu", "COM_AU": "https://mail.zoho.com.au",
                "JP": "https://mail.zoho.jp", "CA": "https://mail.zohocloud.ca",
                "COM_CN": "https://mail.zoho.com.cn", "AE": "https://mail.zoho.ae",
                "SA": "https://mail.zoho.sa",
            }
            api_base = domains.get(data_center)
            if not api_base:
                raise EmailIntegrationOAuthError("Unsupported Zoho data center.")
            accounts = self._get_json(
                f"{api_base}/api/accounts",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            ).get("data") or []
            expected = self.integration.mailbox_email.casefold()
            selected = next(
                (
                    account for account in accounts
                    if str(
                        account.get("primaryEmailAddress")
                        or account.get("emailAddress")
                        or account.get("accountName")
                        or ""
                    ).casefold() == expected
                ),
                None,
            )
            account_id = str((selected or {}).get("accountId") or "")
            if not account_id:
                raise EmailIntegrationOAuthError(
                    "The authorized Zoho account does not match the mailbox email entered."
                )
            return expected, {"zoho_account_id": account_id}

        raise EmailIntegrationOAuthError("Unsupported email provider.")

    @staticmethod
    def _get_json(url: str, *, headers: dict[str, str]) -> dict:
        try:
            response = requests.get(url, headers=headers, timeout=20)
        except requests.RequestException as exc:
            raise EmailIntegrationOAuthError(
                "Could not verify the authorized mailbox identity."
            ) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise EmailIntegrationOAuthError(
                "The email provider returned an invalid mailbox identity response."
            ) from exc
        if response.status_code >= 400 or not isinstance(data, dict):
            raise EmailIntegrationOAuthError(
                "Could not verify the authorized mailbox identity."
            )
        return data

    def _request_tokens(self, payload: dict) -> EmailTokenSet:
        try:
            response = requests.post(
                self.config.token_url,
                data={
                    **payload,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            raise EmailIntegrationOAuthError(
                "Could not reach the email provider. Please try again."
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise EmailIntegrationOAuthError(
                "The email provider returned an invalid token response."
            ) from exc

        if response.status_code >= 400 or not data.get("access_token"):
            provider_error = str(
                data.get("error_description") or data.get("error") or "OAuth failed."
            )
            invalid_grant = (
                payload.get("grant_type") == "refresh_token"
                and (
                    str(data.get("error", "")).lower() == "invalid_grant"
                    or (
                        self.integration.provider == EmailIntegration.Provider.ZOHO
                        and str(data.get("error", "")).lower() == "invalid_code"
                    )
                )
            )
            raise EmailIntegrationOAuthError(
                "Mailbox authorization expired or was revoked. Reconnect it."
                if invalid_grant else provider_error[:500],
                authorization_required=invalid_grant,
            )

        expires_in = int(data.get("expires_in") or 3600)
        metadata = dict(self.integration.provider_metadata or {})
        if data.get("api_domain"):
            metadata["api_domain"] = data["api_domain"]

        return EmailTokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token") or None,
            access_token_expires_at=timezone.now() + timedelta(seconds=expires_in),
            provider_metadata=metadata,
        )
