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
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 45.0


class AIProviderError(Exception):
    """Safe domain error raised by an AI provider adapter."""


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
    """Common OCR contract implemented by every provider."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def test_connection(self, *, timeout: float = REQUEST_TIMEOUT) -> None:
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


class GoogleProvider(AIProvider):
    def test_connection(self, *, timeout: float = REQUEST_TIMEOUT) -> None:
        try:
            from google import genai
        except ImportError as exc:
            raise AIProviderError(
                "Google Gemini support is not installed."
            ) from exc

        try:
            client = genai.Client(
                api_key=self.api_key,
                http_options={"timeout": int(timeout * 1000)},
            )
            client.models.get(model=self.model)
        except Exception as exc:
            raise AIProviderError(
                "Google rejected the API key or model."
            ) from exc

    def generate_json(
        self,
        *,
        file_path,
        mime_type,
        prompt,
        schema,
        timeout,
        seed=None,
    ) -> dict:
        try:
            from google import genai
        except ImportError as exc:
            raise AIProviderError(
                "Google Gemini support is not installed."
            ) from exc

        try:
            client = genai.Client(
                api_key=self.api_key,
                http_options={"timeout": int(timeout * 1000)},
            )
            data = Path(file_path).read_bytes()
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
                config=genai.types.GenerateContentConfig(**config_kwargs),
            )
            return _parse_json_text(getattr(response, "text", "") or "")
        except AIProviderError:
            raise
        except Exception as exc:
            logger.exception(
                "Google Gemini OCR request failed — model=%s error=%s",
                self.model,
                exc,
            )
            raise AIProviderError(
                f"Google Gemini request failed: {exc}."
            ) from exc


class OpenAIProvider(AIProvider):
    API_URL = "https://api.openai.com/v1/responses"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def test_connection(self, *, timeout: float = REQUEST_TIMEOUT) -> None:
        try:
            response = requests.get(
                f"https://api.openai.com/v1/models/{self.model}",
                headers=self._headers(),
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                "Could not reach OpenAI."
            ) from exc

        if not response.ok:
            raise AIProviderError(
                "OpenAI rejected the API key or model."
            )

    def generate_json(
        self,
        *,
        file_path,
        mime_type,
        prompt,
        schema,
        timeout,
        seed=None,
    ) -> dict:
        try:
            encoded = base64.b64encode(Path(file_path).read_bytes()).decode("ascii")
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

            response = requests.post(
                self.API_URL,
                headers=self._headers(),
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                "Could not reach OpenAI."
            ) from exc

        if not response.ok:
            logger.warning(
                "OpenAI OCR request failed with status=%s",
                response.status_code,
            )
            raise AIProviderError(
                "OpenAI rejected the OCR request."
            )

        try:
            body = response.json()
            return _parse_json_text(body.get("output_text", ""))
        except (ValueError, TypeError, KeyError) as exc:
            raise AIProviderError(
                "OpenAI returned an unexpected response."
            ) from exc


class AnthropicProvider(AIProvider):
    API_URL = "https://api.anthropic.com/v1/messages"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def test_connection(self, *, timeout: float = REQUEST_TIMEOUT) -> None:
        payload = {
            "model": self.model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Reply with OK."}],
        }
        try:
            response = requests.post(
                self.API_URL,
                headers=self._headers(),
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                "Could not reach Anthropic."
            ) from exc

        if not response.ok:
            raise AIProviderError(
                "Anthropic rejected the API key or model."
            )

    def generate_json(
        self,
        *,
        file_path,
        mime_type,
        prompt,
        schema,
        timeout,
        seed=None,
    ) -> dict:
        encoded = base64.b64encode(Path(file_path).read_bytes()).decode("ascii")

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

        schema_hint = json.dumps(schema, ensure_ascii=False)
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
            "messages": [{
                "role": "user",
                "content": [document_block, {"type": "text", "text": strict_prompt}],
            }],
        }

        try:
            response = requests.post(
                self.API_URL,
                headers=self._headers(),
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                "Could not reach Anthropic."
            ) from exc

        if not response.ok:
            logger.warning(
                "Anthropic OCR request failed with status=%s",
                response.status_code,
            )
            raise AIProviderError(
                "Anthropic rejected the OCR request."
            )

        try:
            body = response.json()
            text_parts = [
                item.get("text", "")
                for item in body.get("content", [])
                if item.get("type") == "text"
            ]
            return _parse_json_text("".join(text_parts))
        except (ValueError, TypeError, KeyError) as exc:
            raise AIProviderError(
                "Anthropic returned an unexpected response."
            ) from exc


PROVIDER_CLASSES = {
    "google": GoogleProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def build_provider(*, provider: str, api_key: str, model: str) -> AIProvider:
    provider_class = PROVIDER_CLASSES.get(provider)
    if provider_class is None:
        raise AIProviderError("Unsupported AI provider.")
    return provider_class(api_key=api_key, model=model)
