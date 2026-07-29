"""
AI provider abstraction (AI_CONTEXT.md "Always use Provider Abstraction" /
ARCHITECTURE_DECISIONS.md ADR-010).

AIService depends only on the AIProvider interface — adding Claude,
Gemini, or Azure later means adding a new subclass here and changing
which one AIService is constructed with; AIService itself never changes.
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
from django.conf import settings

from ai.exceptions import AIProviderNotConfiguredException, AIProviderRequestException

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 30
RETRYABLE_STATUS_CODES = (
    429,
    500,
    502,
    503,
    504,
)

def build_session() -> requests.session:
    """
    Shared HTTP session with retry strategy.

    Retries only transient failures.
    """
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=RETRYABLE_STATUS_CODES,
        allowed_methods=frozenset(["POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=20,
    )
    session = requests.session()
    session.mount("https://",adapter)
    session.mount("http://",adapter)
    return session

class AIProvider(ABC):
    """Interface every AI provider must implement."""

    @abstractmethod
    def generate_response(self, *, system_prompt: str, user_prompt: str, history: list[dict] | None = None) -> str:
        """Return the assistant's reply as plain text.`history`, if given, is prior conversation turns as
        {'role': 'user'|'assistant', 'content': str} dicts, oldest first
        — the caller (AIService) is responsible for bounding how many are
        passed in; providers must not apply their own truncation.
        """
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    """
    Calls OpenAI's Chat Completions API directly via `requests` — the
    project already depends on `requests` for the NetSuite client
    (netsuite/client.py), so this avoids adding the full `openai` SDK as a
    new dependency for a single HTTP endpoint.
    """

    API_URL = 'https://api.openai.com/v1/chat/completions'
    _session = build_session()

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL

    def generate_response(self, *, system_prompt: str, user_prompt: str, history: list[dict] | None = None) -> str:
        if not self.api_key:
            raise AIProviderNotConfiguredException(
                'OPENAI_API_KEY is not configured. Set it in the environment to enable '
                'AI responses.'
            )
        messages = [{'role': 'system', 'content': system_prompt}]
        if history:
            messages.extend(history)
        messages.append({'role': 'user', 'content': user_prompt})

        payload = {
            "model":self.model,
            "messages":messages,
        }
        try:
            response = self._session.post(
                self.API_URL,
                headers = {
                    "Authorization" : f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json = payload,
                timeout = (
                    CONNECT_TIMEOUT_SECONDS,
                    READ_TIMEOUT_SECONDS,
                ),
            )

        except requests.Timeout as exc:
            logger.exception('OpenAI request failed (network error).')
            raise AIProviderRequestException(
                'Could not reach the AI provider. the AI porvider timed out.'
            ) from exc

        except requests.ConnectionError as exc:
            logger.exception("Unable to connect to OpenAI.")
            raise AIProviderRequestException(
                "Unable"
            )

        if not response.ok:
            # Never log the request body (contains the user's question) or
            # raw response body, consistent with netsuite/client.py's
            # logging discipline.
            logger.error('OpenAI API returned %s.', response.status_code)
            raise AIProviderRequestException(
                'The AI provider rejected the request. Please try again later.'
            )

        payload = response.json()
        try:
            return payload['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError) as exc:
            logger.exception('Unexpected OpenAI response shape.')
            raise AIProviderRequestException(
                'Received an unexpected response from the AI provider.'
            ) from exc

class GeminiProvider(AIProvider):
    """
    Google Gemini implementation using the Gemini REST API.

    Uses Gemini's native conversation format instead of flattening
    everything into one prompt.
    """

    API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent?key={api_key}"
    )
    _session = build_session()

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL

    def generate_response(
    self,
    *,
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
) -> str:

        if not self.api_key:
            raise AIProviderNotConfiguredException(
                "GEMINI_API_KEY is not configured."
            )

        contents: list[dict] = []

        # Gemini REST conversation format
        contents.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "System Instructions:\n"
                            f"{system_prompt}\n\n"
                            "Follow these instructions throughout the conversation."
                        )
                    }
                ],
            }
        )

        contents.append(
            {
                "role": "model",
                "parts": [
                    {
                        "text": "Understood."
                    }
                ],
            }
        )

        if history:
            for message in history:

                role = (
                    "model"
                    if message["role"] == "assistant"
                    else "user"
                )

                contents.append(
                    {
                        "role": role,
                        "parts": [
                            {
                                "text": message["content"]
                            }
                        ],
                    }
                )

        contents.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": user_prompt
                    }
                ],
            }
        )

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.9,
                "topK": 40,
                "maxOutputTokens": 2048,
            },
        }

        try:

            response = self._session.post(
                self.API_URL.format(
                    model=self.model,
                    api_key=self.api_key,
                ),
                headers={
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=(
                    CONNECT_TIMEOUT_SECONDS,
                    READ_TIMEOUT_SECONDS,
                ),
            )

        except requests.Timeout as exc:

            logger.exception("Gemini request timed out.")

            raise AIProviderRequestException(
                "The AI provider timed out."
            ) from exc

        except requests.ConnectionError as exc:

            logger.exception("Unable to connect to Gemini.")

            raise AIProviderRequestException(
                "Unable to reach the AI provider."
            ) from exc

        except requests.RequestException as exc:

            logger.exception("Unexpected Gemini request failure.")

            raise AIProviderRequestException(
                "AI provider request failed."
            ) from exc

        if response.status_code == 401:

            logger.error("Invalid Gemini API key.")

            raise AIProviderRequestException(
                "Gemini authentication failed."
            )

        if response.status_code == 429:

            logger.warning("Gemini rate limit exceeded.")

            raise AIProviderRequestException(
                "The AI provider is currently busy. Please try again shortly."
            )

        if response.status_code >= 500:

            logger.error(
                "Gemini server error (%s).",
                response.status_code,
            )

            raise AIProviderRequestException(
                "The AI provider is temporarily unavailable."
            )

        if not response.ok:

            logger.error(
                "Gemini returned HTTP %s.",
                response.status_code,
            )

            raise AIProviderRequestException(
                "The AI provider rejected the request."
            )

        try:

            data = response.json()

        except ValueError as exc:

            logger.exception("Invalid JSON received from Gemini.")

            raise AIProviderRequestException(
                "Invalid response received from the AI provider."
            ) from exc

        candidates = data.get("candidates")

        if not candidates:

            logger.error("Gemini response missing 'candidates'.")

            raise AIProviderRequestException(
                "Unexpected AI provider response."
            )

        content = candidates[0].get("content")

        if not content:

            logger.error("Gemini response missing 'content'.")

            raise AIProviderRequestException(
                "Unexpected AI provider response."
            )

        parts = content.get("parts")

        if not parts:

            logger.error("Gemini response missing 'parts'.")

            raise AIProviderRequestException(
                "Unexpected AI provider response."
            )

        text = parts[0].get("text")

        if not isinstance(text, str):

            logger.error("Gemini response missing text.")

            raise AIProviderRequestException(
                "Unexpected AI provider response."
            )

        return text.strip()

class AIProviderFactory:

    @staticmethod
    def create() -> AIProvider:

        provider = settings.AI_PROVIDER.lower()

        providers = {
            "openai": OpenAIProvider,
            "gemini": GeminiProvider,
        }

        provider_class = providers.get(provider)

        if provider_class is None:
            raise AIProviderNotConfiguredException(
                f"Unsupported AI provider '{provider}'."
            )

        return provider_class()