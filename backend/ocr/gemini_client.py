"""
Gemini API client for OCR extraction.

``GeminiClient`` handles the low-level communication with the Google
Gemini API. It is deliberately stateless and contains no business
logic — its only responsibilities are:

- Upload images to the API
- Send prompts and receive responses
- Retry on failure with exponential backoff
- Enforce timeouts
- Log all API calls
- Validate response structure

Business logic (orchestration, schema validation, confidence
calculation) belongs in ``OCRExtractionService``.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings

from ocr.exceptions import (
    GeminiConnectionException,
    GeminiRateLimitException,
    GeminiTimeoutException,
    GeminiValidationException,
)
from ocr.prompts import EXTRACTION_PROMPT, SYSTEM_PROMPT
from ocr.notebook_extraction_service import _json_object_schema
from ocr.utils import logger

#: Google Generative AI client — imported lazily to avoid a hard
#: dependency at module load time. This allows the project to run
#: without the google-genai package installed (e.g. in CI tests
#: that mock the client).
_genai = None


def _get_genai():
    """Lazy-import the google-genai library."""
    global _genai
    if _genai is None:
        import google.genai as genai
        _genai = genai
    return _genai


class GeminiClient:
    """
    Low-level client for the Gemini Vision API.

    Usage::

        client = GeminiClient()
        result = client.extract(image_path)
        data = json.loads(result)
    """

    def __init__(self) -> None:
        self.model: str = settings.OCR_GEMINI_MODEL
        self.timeout: int = settings.OCR_TIMEOUT
        self.max_retries: int = settings.OCR_MAX_RETRIES
        self.retry_delay: float = settings.OCR_RETRY_DELAY
        self._client = None

    def extract(
        self,
        image_path: str | Path,
        prompt: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict:
        """
        Send an image to Gemini and return the parsed JSON result.

        Args:
            image_path: Path to the preprocessed image file.
            prompt: Optional extraction prompt. Defaults to the static
                EXTRACTION_PROMPT when omitted.
            response_schema: Optional Gemini response_schema. Defaults
                to the static EXTRACTION_SCHEMA when omitted.

        Returns:
            The parsed JSON dictionary from Gemini.

        Raises:
            GeminiConnectionException: If the API is unreachable.
            GeminiTimeoutException: If the request times out.
            GeminiRateLimitException: If rate-limited (HTTP 429).
            GeminiValidationException: If the response is not valid JSON.
        """
        request_id = uuid.uuid4().hex[:8]
        logger.info(
            'Gemini extraction started — request_id=%s image=%s model=%s',
            request_id, image_path, self.model,
        )

        start = time.perf_counter()
        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response_text = self._call_api(
                    image_path,
                    request_id,
                    prompt=prompt,
                    response_schema=response_schema,
                )
                result = self._parse_response(response_text, request_id)

                latency_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    'Gemini extraction completed — request_id=%s '
                    'attempt=%d latency=%.2fms',
                    request_id, attempt, latency_ms,
                )
                return result

            except (GeminiTimeoutException, GeminiRateLimitException) as exc:
                last_exception = exc
                logger.warning(
                    'Gemini extraction attempt %d/%d failed — '
                    'request_id=%s error=%s',
                    attempt, self.max_retries, request_id, exc,
                )
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.info(
                        'Retrying in %.2f seconds (attempt %d/%d)...',
                        delay, attempt + 1, self.max_retries,
                    )
                    time.sleep(delay)

            except GeminiValidationException as exc:
                # Validation failures are not retried unless it's
                # the first attempt (in case of transient parse issues)
                last_exception = exc
                if attempt < self.max_retries:
                    continue
                raise

            except Exception as exc:
                last_exception = exc
                logger.error(
                    'Gemini extraction failed — request_id=%s '
                    'attempt=%d error=%s',
                    request_id, attempt, exc,
                )
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    time.sleep(delay)

        # All retries exhausted
        latency_ms = (time.perf_counter() - start) * 1000
        logger.error(
            'Gemini extraction failed after %d attempts — '
            'request_id=%s latency=%.2fms',
            self.max_retries, request_id, latency_ms,
        )
        if isinstance(last_exception, GeminiTimeoutException):
            raise GeminiTimeoutException(
                f'Gemini API timed out after {self.max_retries} attempts.'
            ) from last_exception
        if isinstance(last_exception, GeminiRateLimitException):
            raise GeminiRateLimitException(
                f'Gemini API rate limit exceeded after '
                f'{self.max_retries} attempts.'
            ) from last_exception
        raise GeminiConnectionException(
            f'Gemini API request failed after {self.max_retries} attempts: '
            f'{last_exception}'
        ) from last_exception

    def _call_api(
        self,
        image_path: str | Path,
        request_id: str,
        prompt: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        """
        Make the actual API call to Gemini.

        Args:
            image_path: Path to the image file.
            request_id: Unique request identifier for logging.
            prompt: Optional extraction prompt.
            response_schema: Optional Gemini response_schema.

        Returns:
            Raw response text from Gemini.

        Raises:
            GeminiConnectionException: If the API is unreachable.
            GeminiTimeoutException: If the request times out.
            GeminiRateLimitException: If rate-limited.
        """
        genai = _get_genai()

        try:
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options={'timeout': self.timeout * 1000},
            )
        except Exception as exc:
            raise GeminiConnectionException(
                f'Failed to create Gemini client: {exc}'
            ) from exc

        effective_prompt = prompt or EXTRACTION_PROMPT
        effective_schema = response_schema or _json_object_schema()

        try:
            image = genai.types.Part.from_uri(
                file_uri=str(image_path),
                mime_type='image/png',
            )
            response = client.models.generate_content(
                model=self.model,
                contents=[SYSTEM_PROMPT, effective_prompt, image],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=effective_schema,
                ),
            )
        except TimeoutError as exc:
            raise GeminiTimeoutException(
                f'Gemini API request timed out after {self.timeout}s: {exc}'
            ) from exc
        except Exception as exc:
            error_str = str(exc).lower()
            if '429' in error_str or 'rate' in error_str or 'quota' in error_str:
                raise GeminiRateLimitException(
                    f'Gemini API rate limit exceeded: {exc}'
                ) from exc
            if 'timeout' in error_str or 'deadline' in error_str:
                raise GeminiTimeoutException(
                    f'Gemini API request timed out after {self.timeout}s: {exc}'
                ) from exc
            if 'connection' in error_str or 'dns' in error_str or 'unreachable' in error_str:
                raise GeminiConnectionException(
                    f'Gemini API unreachable: {exc}'
                ) from exc
            raise GeminiConnectionException(
                f'Gemini API request failed: {exc}'
            ) from exc

        if not response or not response.text:
            raise GeminiValidationException(
                'Gemini returned an empty response.'
            )

        return response.text

    @staticmethod
    def _parse_response(response_text: str, request_id: str) -> dict:
        """
        Parse the Gemini response text as JSON.

        Strips markdown code fences if present, then parses the JSON.

        Args:
            response_text: Raw response text from Gemini.
            request_id: Unique request identifier for logging.

        Returns:
            Parsed JSON dictionary.

        Raises:
            GeminiValidationException: If parsing fails.
        """
        text = response_text.strip()

        # Strip markdown code fences if present
        if text.startswith('```'):
            lines = text.splitlines()
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            text = '\n'.join(lines).strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error(
                'Failed to parse Gemini response as JSON — '
                'request_id=%s response=%s error=%s',
                request_id, text[:500], exc,
            )
            raise GeminiValidationException(
                f'Failed to parse Gemini response as JSON: {exc}'
            ) from exc

        if not isinstance(result, dict):
            raise GeminiValidationException(
                'Gemini response is not a JSON object.'
            )

        return result
