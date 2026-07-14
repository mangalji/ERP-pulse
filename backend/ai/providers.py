"""
AI provider abstraction (AI_CONTEXT.md "Always use Provider Abstraction" /
ARCHITECTURE_DECISIONS.md ADR-010).

AIService depends only on the AIProvider interface — adding Claude,
Gemini, or Azure later means adding a new subclass here and changing
which one AIService is constructed with; AIService itself never changes.
"""

import logging
from abc import ABC, abstractmethod

import requests
from django.conf import settings

from ai.exceptions import AIProviderNotConfiguredException, AIProviderRequestException

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


class AIProvider(ABC):
    """Interface every AI provider must implement."""

    @abstractmethod
    def generate_response(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return the assistant's reply as plain text."""
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    """
    Calls OpenAI's Chat Completions API directly via `requests` — the
    project already depends on `requests` for the NetSuite client
    (netsuite/client.py), so this avoids adding the full `openai` SDK as a
    new dependency for a single HTTP endpoint.
    """

    API_URL = 'https://api.openai.com/v1/chat/completions'

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL

    def generate_response(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise AIProviderNotConfiguredException(
                'OPENAI_API_KEY is not configured. Set it in the environment to enable '
                'AI responses.'
            )

        try:
            response = requests.post(
                self.API_URL,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt},
                    ],
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.exception('OpenAI request failed (network error).')
            raise AIProviderRequestException(
                'Could not reach the AI provider. Please try again.'
            ) from exc

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
