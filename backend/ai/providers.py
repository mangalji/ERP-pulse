"""
AI provider abstraction (AI_CONTEXT.md "Always use Provider Abstraction" /
ARCHITECTURE_DECISIONS.md ADR-010).

AIService depends only on the AIProvider interface — adding Claude,
Gemini, or Azure later means adding a new subclass here and changing
which one AIService is constructed with; AIService itself never changes.
"""

import logging
from abc import ABC, abstractmethod
import json

import requests
from django.conf import settings

from ai.exceptions import AIProviderNotConfiguredException, AIProviderRequestException

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


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

        try:
            response = requests.post(
                self.API_URL,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': self.model,
                    'messages': messages,
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

# class GeminiProvider(AIProvider):
#     """
#     Calls Google's Gemini REST API directly using requests.

#     Uses the same provider abstraction as OpenAIProvider so AIService
#     remains provider-agnostic.
#     """
#     API_URL = (
#         "https://generativelanguage.googleapis.com/v1beta/models/"
#         "{model}:generateContent?key={api_key}"
#     )
#     def __init__(self):
#         self.api_key = settings.GEMINI_API_KEY
#         self.model = settings.GEMINI_MODEL

#     def generate_response(self,*,system_prompt:str,user_prompt:str,history: list[dict] | None=None,)-> str:

#         if not self.api_key:
#             raise AIProviderNotConfiguredException(
#                 "GEMINI_API_KEY is not configured. Set it in the environment to enable AI responses."
#             )

#         prompt_parts = [
#             f"System Instructions:\n{system_prompt}\n"
#         ]

#         if history:
#             prompt_parts.append("Conversation History: ")

#             for message in history:
#                 role = message['role'].capitalize()
#                 prompt_parts.append(f"{role}: {message['content']}")
            
#         prompt_parts.append(f"User: {user_prompt}")

#         final_prompt = "\n\n".join(prompt_parts)

#         try:
#             response = requests.post(
#                 self.API_URL.format(
#                     model=self.model,
#                     api_key=self.api_key,
#                 ),
#                 headers = {
#                     "Content-Type":"application/json",
#                 },
#                 json={
#                     "contents":[
#                         {
#                             "parts":[
#                                 {
#                                     "text":final_prompt,
#                                 }
#                             ]
#                         }
#                     ]
#                 },
#                 timeout=REQUEST_TIMEOUT_SECONDS,
#             )
#         except requests.RequestException as exc:
#             logger.exception("Gemini request failed (network error).")
#             raise AIProviderRequestException(
#                 "Could not reach the AI provider. Please try again."
#             ) from exc

#         if not response.ok:
#             logger.error("Gemini API returned %s.", response.status_code)

#             raise AIProviderRequestException(
#                 "The AI provider rejected the request. Please try again later."
#             )
        
#         payload = response.json()

#         try:
#             return (
#                 payload["candidates"][0]["content"]["parts"][0]["text"].strip()
#             )

#         except (KeyError, IndexError) as exc:
#             logger.exception("Unexpected Gemini response shape.")

#             raise AIProviderRequestException(
#                 "Received an unexpected response from the AI provider."
#             ) from exc

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

        contents = []

        # System prompt (Gemini REST currently doesn't have a dedicated
        # system role in this endpoint, so we send it as the first user turn.)
        contents.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "System Instructions:\n"
                            f"{system_prompt}\n\n"
                            "Always follow these instructions throughout the conversation."
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
                        "text": "Understood. I will follow those instructions."
                    }
                ],
            }
        )

        # Previous conversation
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

        # Current user message
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

        try:

            response = requests.post(
                self.API_URL.format(
                    model=self.model,
                    api_key=self.api_key,
                ),
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.3,
                        "topP": 0.9,
                        "topK": 40,
                        "maxOutputTokens": 2048,
                    },
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

        except requests.RequestException as exc:

            logger.exception(
                "Gemini request failed (network error)."
            )

            raise AIProviderRequestException(
                "Could not reach the AI provider. Please try again."
            ) from exc

        if not response.ok:

            logger.error(
                "Gemini API returned %s.",
                response.status_code,
            )

            raise AIProviderRequestException(
                "The AI provider rejected the request."
            )

        payload = response.json()

        try:

            return (
                payload["candidates"][0]["content"]["parts"][0]["text"]
                .strip()
            )

        except (KeyError, IndexError) as exc:

            logger.exception(
                "Unexpected Gemini response shape."
            )

            raise AIProviderRequestException(
                "Received an unexpected response from the AI provider."
            ) from exc

# def get_ai_provider() -> AIProvider:
#     """
#     Returns the configured AI provider.

#     AI_PROVIDER values:
#     - gemini
#     """

#     provider = settings.AI_PROVIDER.lower()

#     if provider == "gemini":
#         return GeminiProvider()

#     if provider == "openai":
#         return OpenAIProvider()

#     raise AIProviderNotConfiguredException(
#         f"Unsupported AI provider '{provider}'."
#     )

# def get_ai_provider() -> AIProvider:

#     provider = settings.AI_PROVIDER.lower()

#     if provider == "gemini":
#         return GeminiProvider()

#     if provider == "openai":
#         return OpenAIProvider()

#     raise AIProviderNotConfiguredException(
#         f"Unsupported AI provider '{provider}'."
#     )

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