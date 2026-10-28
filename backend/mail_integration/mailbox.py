"""Read-only Gmail and Zoho clients normalized for email staging."""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone
from email.utils import getaddresses, parsedate_to_datetime
from collections.abc import Callable
from typing import Iterator

import requests
from django.utils import timezone

from mail_integration.exceptions import EmailMailboxFetchError
from mail_integration.models import EmailIntegration


REQUEST_TIMEOUT_SECONDS = 30
ZOHO_MAIL_BASE_URLS = {
    "COM": "https://mail.zoho.com", "IN": "https://mail.zoho.in",
    "EU": "https://mail.zoho.eu", "COM_AU": "https://mail.zoho.com.au",
    "JP": "https://mail.zoho.jp", "CA": "https://mail.zohocloud.ca",
    "COM_CN": "https://mail.zoho.com.cn", "AE": "https://mail.zoho.ae",
    "SA": "https://mail.zoho.sa",
}


@dataclass(frozen=True)
class IncomingMailboxMessage:
    provider_message_id: str
    provider_thread_id: str
    internet_message_id: str
    sender_email: str
    recipient_emails: list[str]
    subject: str
    sent_at: datetime | None
    received_at: datetime | None
    raw_body: str
    normalized_body: str


def normalize_email_body(value: str) -> str:
    """Preserve readable text and remove HTML/script noise before AI use."""
    value = value or ""
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html.unescape(value).replace("\r\n", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def readable_email_body(raw_body: str, normalized_body: str) -> str:
    """Keep plain-text mail intact; render HTML mail as safe readable text."""
    if re.search(r"(?i)<\s*/?\s*(?:html|body|div|p|br|table|span|script|style)\b", raw_body or ""):
        return normalized_body or normalize_email_body(raw_body)
    return raw_body or normalized_body or ""


def _millis_to_datetime(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=datetime_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _header_datetime(value: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(value)
        return (
            timezone.make_aware(parsed, datetime_timezone.utc)
            if timezone.is_naive(parsed)
            else parsed.astimezone(datetime_timezone.utc)
        )
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _addresses(value: str) -> list[str]:
    return [address.lower() for _, address in getaddresses([value or ""]) if address]


class BaseMailboxClient:
    def __init__(self, *, integration: EmailIntegration):
        if not integration.access_token:
            raise EmailMailboxFetchError("The mailbox is not authorized. Reconnect it.")
        self.integration = integration

    @property
    def headers(self) -> dict[str, str]:
        raise NotImplementedError

    def iter_messages_since(
        self,
        since: datetime,
        *,
        until: datetime | None = None,
        cursor: str = "",
        on_page_completed: Callable[[str], bool | None] | None = None,
    ) -> Iterator[IncomingMailboxMessage]:
        raise NotImplementedError

    @staticmethod
    def get(url: str, *, headers: dict[str, str], params: dict | None = None) -> dict:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise EmailMailboxFetchError("Could not reach the email provider.") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise EmailMailboxFetchError("The email provider returned an invalid response.") from exc
        if response.status_code >= 400:
            if response.status_code in {401, 403}:
                raise EmailMailboxFetchError(
                    "MAILBOX_AUTHORIZATION_REQUIRED: The mailbox authorization was rejected. Reconnect it."
                )
            detail = data.get("error") if isinstance(data, dict) else ""
            if isinstance(detail, dict):
                detail = detail.get("message") or detail.get("status")
            raise EmailMailboxFetchError(str(detail or "Mailbox request failed.")[:500])
        return data


class GmailMailboxClient(BaseMailboxClient):
    api_base_url = "https://gmail.googleapis.com/gmail/v1/users/me"

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.integration.access_token}"}

    def iter_messages_since(
        self,
        since: datetime,
        *,
        until: datetime | None = None,
        cursor: str = "",
        on_page_completed: Callable[[str], bool | None] | None = None,
    ) -> Iterator[IncomingMailboxMessage]:
        page_token = cursor
        while True:
            query = f"after:{int(since.timestamp())}"
            # Keep a large initial sync a stable, resumable window. Messages
            # delivered while it runs are picked up by the next regular sync.
            if until:
                query += f" before:{int(until.timestamp()) + 1}"
            params = {"q": query, "maxResults": 500}
            if page_token:
                params["pageToken"] = page_token
            listing = self.get(f"{self.api_base_url}/messages", headers=self.headers, params=params)
            for item in listing.get("messages") or []:
                message_id = str(item.get("id") or "")
                if not message_id:
                    continue
                message = self.get(
                    f"{self.api_base_url}/messages/{message_id}",
                    headers=self.headers,
                    params={"format": "full"},
                )
                yield self.parse_message(message)
            next_page_token = str(listing.get("nextPageToken") or "")
            if on_page_completed and next_page_token:
                # The sync service may stop after a bounded number of fully
                # checkpointed pages. The next scheduled run resumes here.
                if on_page_completed(next_page_token) is False:
                    return
            page_token = next_page_token
            if not page_token:
                return

    def parse_message(self, message: dict) -> IncomingMailboxMessage:
        payload = message.get("payload") or {}
        headers = {
            str(item.get("name") or "").casefold(): str(item.get("value") or "")
            for item in payload.get("headers") or []
            if isinstance(item, dict)
        }
        raw_body = self._part_body(payload)
        sender = _addresses(headers.get("from", ""))
        recipients = []
        for name in ("to", "cc", "bcc"):
            recipients.extend(_addresses(headers.get(name, "")))
        sent_at = _header_datetime(headers.get("date", ""))
        return IncomingMailboxMessage(
            provider_message_id=str(message.get("id") or ""),
            provider_thread_id=str(message.get("threadId") or ""),
            internet_message_id=headers.get("message-id", "").strip(),
            sender_email=sender[0] if sender else "",
            recipient_emails=list(dict.fromkeys(recipients)),
            subject=headers.get("subject", "").strip(),
            sent_at=sent_at,
            received_at=_millis_to_datetime(message.get("internalDate")) or sent_at,
            raw_body=raw_body,
            normalized_body=normalize_email_body(raw_body),
        )

    def _part_body(self, part: dict) -> str:
        children = part.get("parts") or []
        if children:
            parsed = [
                (str(child.get("mimeType") or "").casefold(), self._part_body(child))
                for child in children if isinstance(child, dict)
            ]
            parsed = [(mime, body) for mime, body in parsed if body]
            plain = [body for mime, body in parsed if mime == "text/plain"]
            return "\n".join(plain or [body for _, body in parsed])
        encoded = str((part.get("body") or {}).get("data") or "")
        if not encoded:
            return ""
        try:
            return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8", "replace")
        except (ValueError, UnicodeDecodeError):
            return ""


class ZohoMailboxClient(BaseMailboxClient):
    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Zoho-oauthtoken {self.integration.access_token}"}

    @property
    def api_base_url(self) -> str:
        data_center = str((self.integration.provider_metadata or {}).get("zoho_data_center", "IN")).upper()
        try:
            return ZOHO_MAIL_BASE_URLS[data_center]
        except KeyError as exc:
            raise EmailMailboxFetchError("Unsupported Zoho data center.") from exc

    def iter_messages_since(
        self,
        since: datetime,
        *,
        until: datetime | None = None,
        cursor: str = "",
        on_page_completed: Callable[[str], bool | None] | None = None,
    ) -> Iterator[IncomingMailboxMessage]:
        account_id = self._account_id()
        try:
            start = max(1, int(cursor or "1"))
        except ValueError as exc:
            raise EmailMailboxFetchError("Zoho mailbox sync cursor is invalid.") from exc

        # The search API filters the large history window at Zoho instead of
        # making the application page through every message in the Inbox.
        # Zoho date searches are calendar-day based, so retain exact timestamp
        # checks below for the start/end boundaries.
        search_start = timezone.localtime(since - timedelta(days=1)).strftime("%d-%b-%Y")
        search_end = timezone.localtime((until or timezone.now()) + timedelta(days=1)).strftime("%d-%b-%Y")
        search_key = f"in:Inbox::fromDate:{search_start}::toDate:{search_end}"
        while True:
            listing = self.get(
                f"{self.api_base_url}/api/accounts/{account_id}/messages/search",
                headers=self.headers,
                params={"searchKey": search_key, "start": start, "limit": 200, "includeto": "true"},
            )
            messages = listing.get("data") or []
            if not isinstance(messages, list):
                raise EmailMailboxFetchError("Zoho returned an invalid message list.")
            if not messages:
                return
            for item in messages:
                received_at = _millis_to_datetime(item.get("receivedTime", item.get("receivedtime"))) or _millis_to_datetime(item.get("sentDateInGMT"))
                if received_at and (received_at < since or (until and received_at > until)):
                    continue
                message_id = str(item.get("messageId") or "")
                folder_id = str(item.get("folderId") or "")
                if not message_id or not folder_id:
                    continue
                raw_body = self._content(account_id, folder_id, message_id)
                yield IncomingMailboxMessage(
                    provider_message_id=message_id,
                    provider_thread_id=str(item.get("threadId") or ""),
                    internet_message_id=str(item.get("mailId") or ""),
                    sender_email=(_addresses(str(item.get("fromAddress") or "")) or [""])[0],
                    recipient_emails=_addresses(str(item.get("toAddress") or "")),
                    subject=str(item.get("subject") or "").strip(),
                    sent_at=_millis_to_datetime(item.get("sentDateInGMT")),
                    received_at=received_at,
                    raw_body=raw_body,
                    normalized_body=normalize_email_body(raw_body),
                )
            next_start = start + len(messages)
            if on_page_completed and len(messages) == 200:
                # Persist the next offset only after this complete page was
                # staged. A later run can safely continue at that offset.
                if on_page_completed(str(next_start)) is False:
                    return
            if len(messages) < 200:
                return
            start = next_start

    def _account_id(self) -> str:
        metadata = dict(self.integration.provider_metadata or {})
        if metadata.get("zoho_account_id"):
            return str(metadata["zoho_account_id"])
        accounts = self.get(f"{self.api_base_url}/api/accounts", headers=self.headers).get("data") or []
        if not isinstance(accounts, list):
            raise EmailMailboxFetchError("Zoho returned an invalid account list.")
        mailbox = self.integration.mailbox_email.casefold()
        selected = next(
            (
                account for account in accounts
                if str(
                    account.get("primaryEmailAddress")
                    or account.get("emailAddress")
                    or account.get("accountName")
                    or ""
                ).casefold() == mailbox
            ),
            None,
        )
        account_id = str((selected or {}).get("accountId") or "")
        if not account_id:
            raise EmailMailboxFetchError("No Zoho mailbox account is available.")
        metadata["zoho_account_id"] = account_id
        self.integration.provider_metadata = metadata
        self.integration.save(update_fields=["provider_metadata", "updated_at"])
        return account_id

    def _inbox_folders(self, account_id: str) -> list[str]:
        folders = self.get(f"{self.api_base_url}/api/accounts/{account_id}/folders", headers=self.headers).get("data") or []
        inboxes = [str(folder.get("folderId")) for folder in folders if str(folder.get("folderName") or folder.get("displayName") or "").casefold() == "inbox" and folder.get("folderId")]
        if not inboxes:
            raise EmailMailboxFetchError("The connected Zoho mailbox has no Inbox folder.")
        return inboxes

    def _content(self, account_id: str, folder_id: str, message_id: str) -> str:
        response = self.get(
            f"{self.api_base_url}/api/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/content",
            headers=self.headers,
            params={"includeBlockContent": "true"},
        )
        data = response.get("data") or {}
        return data if isinstance(data, str) else str(data.get("content") or data.get("messageContent") or "")


def mailbox_client_for(integration: EmailIntegration) -> BaseMailboxClient:
    if integration.provider == EmailIntegration.Provider.GOOGLE:
        return GmailMailboxClient(integration=integration)
    if integration.provider == EmailIntegration.Provider.ZOHO:
        return ZohoMailboxClient(integration=integration)
    raise EmailMailboxFetchError("Unsupported email provider.")
