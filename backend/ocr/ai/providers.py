"""Provider adapters used by OCR.

No provider SDK is required for OpenAI or Anthropic; their HTTPS APIs are
called through requests, which is already a project dependency. Gemini keeps
using google-genai because the existing OCR pipeline already depends on it.
"""

from __future__ import annotations

import base64
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 45.0

RETRYABLE_STATUS_CODES = frozenset({
    408,
    409,
    429,
    500,
    502,
    503,
    504,
})


class AIProviderError(Exception):
    """Safe domain error raised by an AI provider adapter."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        rate_limited: bool = False,
        quota_exhausted: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.rate_limited = rate_limited
        self.quota_exhausted = quota_exhausted


def _is_quota_exhausted(message: str) -> bool:
    text = message.lower()

    return any(
        token in text
        for token in (
            "resource_exhausted",
            "insufficient_quota",
            "quota exceeded",
            "quota has been exceeded",
            "exceeded your current quota",
            "daily quota",
            "quota limit",
        )
    )


def _parse_json_text(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise AIProviderError("AI provider returned an empty response.")

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise AIProviderError("AI provider returned invalid JSON.")

        try:
            payload = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AIProviderError("AI provider returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise AIProviderError("AI provider returned a non-object JSON response.")

    return payload


class AIProvider(ABC):
    """Common contract and shared provider infrastructure."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @staticmethod
    def _raise_status_error(
        *,
        message: str,
        status_code: int | None,
        error_text: str = "",
    ) -> None:
        quota_exhausted = (
            status_code == 429
            and _is_quota_exhausted(error_text)
        )

        raise AIProviderError(
            message,
            status_code=status_code,
            retryable=(
                status_code in RETRYABLE_STATUS_CODES
                and not quota_exhausted
            ),
            rate_limited=(
                status_code == 429
                and not quota_exhausted
            ),
            quota_exhausted=quota_exhausted,
        )

    @staticmethod
    def _raise_request_error(
        exc: requests.RequestException,
        *,
        provider_name: str,
    ) -> None:
        if isinstance(exc, requests.Timeout):
            raise AIProviderError(
                f"{provider_name} request timed out.",
                retryable=True,
            ) from exc

        if isinstance(exc, requests.ConnectionError):
            raise AIProviderError(
                f"Could not reach {provider_name}.",
                retryable=True,
            ) from exc

        raise AIProviderError(
            f"{provider_name} request failed."
        ) from exc

    @classmethod
    def _request(
        cls,
        request_func: Callable[..., requests.Response],
        *,
        url: str,
        provider_name: str,
        error_message: str,
        timeout: float,
        **kwargs: Any,
    ) -> requests.Response:
        try:
            response = request_func(
                url,
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            cls._raise_request_error(
                exc,
                provider_name=provider_name,
            )

        if not response.ok:
            logger.warning(
                "%s request failed with status=%s",
                provider_name,
                response.status_code,
            )
            cls._raise_status_error(
                message=error_message,
                status_code=response.status_code,
                error_text=response.text or "",
            )

        return response

    @staticmethod
    def _response_json(
        response: requests.Response,
        *,
        error_message: str,
    ) -> dict:
        try:
            body = response.json()
        except (ValueError, TypeError) as exc:
            raise AIProviderError(error_message) from exc

        if not isinstance(body, dict):
            raise AIProviderError(error_message)

        return body

    @staticmethod
    def _read_file_bytes(file_path: str | Path) -> bytes:
        try:
            return Path(file_path).read_bytes()
        except OSError as exc:
            raise AIProviderError(
                "Could not read the document for AI processing."
            ) from exc

    @classmethod
    def _encode_file_base64(
        cls,
        file_path: str | Path,
    ) -> str:
        return base64.b64encode(
            cls._read_file_bytes(file_path)
        ).decode("ascii")

    @abstractmethod
    def list_models(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def test_connection(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate_json(
        self,
        *,
        file_path: str | Path,
        mime_type: str,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
        seed: int | None = None,
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
    ) -> dict:
        """Generate structured JSON without requiring a document file."""
        raise NotImplementedError


class GoogleProvider(AIProvider):
    """Google Gemini provider adapter."""

    @staticmethod
    def _load_sdk():
        try:
            from google import genai
            from google.genai import errors
        except ImportError as exc:
            raise AIProviderError(
                "Google Gemini support is not installed."
            ) from exc

        return genai, errors

    def _client(self, genai, *, timeout: float):
        return genai.Client(
            api_key=self.api_key,
            http_options={"timeout": int(timeout * 1000)},
        )

    def list_models(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> list[dict[str, Any]]:
        genai, errors = self._load_sdk()

        try:
            client = self._client(genai, timeout=timeout)
            models = []

            for model in client.models.list():
                model_dump = {}

                if hasattr(model, "model_dump"):
                    model_dump = model.model_dump(
                        mode="json",
                        exclude_none=True,
                    )

                model_name = (
                    getattr(model, "base_model_id", None)
                    or getattr(model, "name", "")
                )
                model_name = model_name.removeprefix("models/")

                display_name = (
                    getattr(model, "display_name", None)
                    or model_name
                )

                if model_name:
                    models.append(
                        {
                            "model_id": model_name,
                            "model_name": display_name,
                            "metadata": model_dump,
                        }
                    )

            return models

        except errors.APIError as exc:
            self._raise_status_error(
                message="Google Gemini model listing failed.",
                status_code=getattr(exc, "code", None),
                error_text=str(exc),
            )

        except AIProviderError:
            raise

        except Exception:
            logger.exception(
                "Google Gemini model catalogue request failed."
            )
            raise AIProviderError(
                "Google Gemini model listing failed."
            )

    def test_connection(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        genai, errors = self._load_sdk()

        try:
            client = self._client(genai, timeout=timeout)
            client.models.get(model=self.model)

        except errors.APIError as exc:
            self._raise_status_error(
                message="Google rejected the API key or model.",
                status_code=getattr(exc, "code", None),
                error_text=str(exc),
            )

        except AIProviderError:
            raise

        except Exception:
            logger.exception(
                "Google Gemini connection test failed — model=%s",
                self.model,
            )
            raise AIProviderError(
                "Google rejected the API key or model."
            )

    def generate_json(
        self,
        *,
        file_path: str | Path,
        mime_type: str,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
        seed: int | None = None,
    ) -> dict:
        genai, errors = self._load_sdk()

        try:
            client = self._client(genai, timeout=timeout)
            data = self._read_file_bytes(file_path)
            part = genai.types.Part.from_bytes(
                data=data,
                mime_type=mime_type,
            )

            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0,
            }

            if seed is not None:
                config_kwargs["seed"] = seed

            response = client.models.generate_content(
                model=self.model,
                contents=[part, prompt],
                config=genai.types.GenerateContentConfig(
                    **config_kwargs
                ),
            )

            return _parse_json_text(
                getattr(response, "text", "") or ""
            )

        except AIProviderError:
            raise

        except errors.APIError as exc:
            self._raise_status_error(
                message="Google Gemini request failed.",
                status_code=getattr(exc, "code", None),
                error_text=str(exc),
            )

        except Exception:
            logger.exception(
                "Google Gemini OCR request failed — model=%s",
                self.model,
            )
            raise AIProviderError(
                "Google Gemini request failed."
            )

    def generate_structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
    ) -> dict:
        genai, errors = self._load_sdk()

        try:
            client = self._client(genai, timeout=timeout)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0,
                ),
            )

            return _parse_json_text(
                getattr(response, "text", "") or ""
            )

        except AIProviderError:
            raise

        except errors.APIError as exc:
            logger.error(
                "Google Gemini structured response failed — "
                "model=%s status=%s error=%s",
                self.model,
                getattr(exc, "code", None),
                str(exc),
            )
            self._raise_status_error(
                message="Google Gemini structured response failed.",
                status_code=getattr(exc, "code", None),
                error_text=str(exc),
            )

        except Exception:
            logger.exception(
                "Google Gemini structured response failed — model=%s",
                self.model,
            )
            raise AIProviderError(
                "Google Gemini structured response failed."
            )


class OpenAIProvider(AIProvider):
    """OpenAI provider adapter."""

    API_URL = "https://api.openai.com/v1/responses"
    MODELS_URL = "https://api.openai.com/v1/models"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def list_models(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> list[dict[str, Any]]:
        response = self._request(
            requests.get,
            url=self.MODELS_URL,
            headers=self._headers(),
            timeout=timeout,
            provider_name="OpenAI",
            error_message="OpenAI model listing failed.",
        )

        body = self._response_json(
            response,
            error_message="OpenAI returned an unexpected model list response.",
        )

        models = []

        for item in body.get("data", []):
            if not isinstance(item, dict):
                continue

            model_id = item.get("id")

            if not model_id:
                continue

            models.append(
                {
                    "model_id": model_id,
                    "model_name": model_id,
                    "metadata": item,
                }
            )

        return models

    def test_connection(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._request(
            requests.get,
            url=f"{self.MODELS_URL}/{self.model}",
            headers=self._headers(),
            timeout=timeout,
            provider_name="OpenAI",
            error_message="OpenAI rejected the API key or model.",
        )

    def generate_json(
        self,
        *,
        file_path: str | Path,
        mime_type: str,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
        seed: int | None = None,
    ) -> dict:
        encoded = self._encode_file_base64(file_path)

        if mime_type.startswith("image/"):
            input_content = {
                "type": "input_image",
                "image_url": f"data:{mime_type};base64,{encoded}",
            }
        else:
            input_content = {
                "type": "input_file",
                "filename": Path(file_path).name,
                "file_data": f"data:{mime_type};base64,{encoded}",
            }

        input_item = {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                input_content,
            ],
        }

        payload = {
            "model": self.model,
            "input": [input_item],
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ocr_extraction",
                    "strict": False,
                    "schema": schema,
                }
            },
        }

        if seed is not None:
            payload["metadata"] = {"seed": str(seed)}

        response = self._request(
            requests.post,
            url=self.API_URL,
            headers=self._headers(),
            json=payload,
            timeout=timeout,
            provider_name="OpenAI",
            error_message="OpenAI rejected the OCR request.",
        )

        body = self._response_json(
            response,
            error_message="OpenAI returned an unexpected response.",
        )

        return _parse_json_text(
            body.get("output_text", "")
        )

    def generate_structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
    ) -> dict:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                }
            ],
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "netsuite_error_diagnostics",
                    "strict": True,
                    "schema": schema,
                }
            },
        }

        response = self._request(
            requests.post,
            url=self.API_URL,
            headers=self._headers(),
            json=payload,
            timeout=timeout,
            provider_name="OpenAI",
            error_message="OpenAI structured response failed.",
        )

        body = self._response_json(
            response,
            error_message="OpenAI returned an unexpected response.",
        )

        return _parse_json_text(
            body.get("output_text", "")
        )


class AnthropicProvider(AIProvider):
    """Anthropic provider adapter."""

    API_URL = "https://api.anthropic.com/v1/messages"
    MODELS_URL = "https://api.anthropic.com/v1/models"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def list_models(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> list[dict[str, Any]]:
        models = []
        after_id = None

        while True:
            params = {
                "limit": 1000,
            }

            if after_id:
                params["after_id"] = after_id

            response = self._request(
                requests.get,
                url=self.MODELS_URL,
                params=params,
                headers=self._headers(),
                timeout=timeout,
                provider_name="Anthropic",
                error_message="Anthropic model listing failed.",
            )

            body = self._response_json(
                response,
                error_message=(
                    "Anthropic returned an unexpected model list response."
                ),
            )

            for item in body.get("data", []):
                if not isinstance(item, dict):
                    continue

                model_id = item.get("id")

                if not model_id:
                    continue

                models.append(
                    {
                        "model_id": model_id,
                        "model_name": item.get(
                            "display_name",
                            model_id,
                        ),
                        "metadata": item,
                    }
                )

            if not body.get("has_more"):
                break

            next_after_id = body.get("last_id")

            if not next_after_id or next_after_id == after_id:
                break

            after_id = next_after_id

        return models

    def test_connection(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        payload = {
            "model": self.model,
            "max_tokens": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply with OK.",
                }
            ],
        }

        self._request(
            requests.post,
            url=self.API_URL,
            headers=self._headers(),
            json=payload,
            timeout=timeout,
            provider_name="Anthropic",
            error_message="Anthropic rejected the API key or model.",
        )

    def generate_json(
        self,
        *,
        file_path: str | Path,
        mime_type: str,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
        seed: int | None = None,
    ) -> dict:
        encoded = self._encode_file_base64(file_path)

        if mime_type == "application/pdf":
            document_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": encoded,
                },
            }
        elif mime_type.startswith("image/"):
            document_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": encoded,
                },
            }
        else:
            raise AIProviderError(
                f"Anthropic OCR does not support MIME type {mime_type} in this adapter."
            )

        schema_hint = json.dumps(
            schema,
            ensure_ascii=False,
        )

        strict_prompt = (
            f"{prompt}\n\n"
            "Return ONLY a JSON object. It must conform to this JSON Schema:\n"
            f"{schema_hint}"
        )

        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "system": (
                "You are a production document extraction engine. "
                "Follow the requested JSON contract exactly."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        document_block,
                        {
                            "type": "text",
                            "text": strict_prompt,
                        },
                    ],
                }
            ],
        }

        response = self._request(
            requests.post,
            url=self.API_URL,
            headers=self._headers(),
            json=payload,
            timeout=timeout,
            provider_name="Anthropic",
            error_message="Anthropic rejected the OCR request.",
        )

        body = self._response_json(
            response,
            error_message="Anthropic returned an unexpected response.",
        )

        text_parts = [
            item.get("text", "")
            for item in body.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ]

        return _parse_json_text("".join(text_parts))

    def generate_structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        timeout: float,
    ) -> dict:
        schema_hint = json.dumps(
            schema,
            ensure_ascii=False,
        )

        structured_prompt = (
            f"{prompt}\n\n"
            "Return ONLY one JSON object. It must conform to this JSON Schema:\n"
            f"{schema_hint}"
        )

        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "system": (
                "You are a production NetSuite diagnostics assistant. "
                "Follow the requested JSON contract exactly."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": structured_prompt,
                }
            ],
        }

        response = self._request(
            requests.post,
            url=self.API_URL,
            headers=self._headers(),
            json=payload,
            timeout=timeout,
            provider_name="Anthropic",
            error_message="Anthropic structured response failed.",
        )

        body = self._response_json(
            response,
            error_message="Anthropic returned an unexpected response.",
        )

        text_parts = [
            item.get("text", "")
            for item in body.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ]

        return _parse_json_text("".join(text_parts))


PROVIDER_CLASSES = {
    "google": GoogleProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def build_provider(
    *,
    provider: str,
    api_key: str,
    model: str,
) -> AIProvider:
    provider_class = PROVIDER_CLASSES.get(provider)

    if provider_class is None:
        raise AIProviderError("Unsupported AI provider.")

    return provider_class(
        api_key=api_key,
        model=model,
    )
