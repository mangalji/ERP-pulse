"""AI provider model catalogue refresh service."""

from __future__ import annotations

import json
import logging
import time

from django.db import transaction
from django.utils import timezone

from ocr.ai.config import (
    SUPPORTED_PROVIDERS,
    models_for,
    provider_exists,
)
from ocr.ai.providers import AIProviderError, build_provider
from ocr.models import AIConfiguration, AIProviderModel


logger = logging.getLogger(__name__)

PROVIDER_NAMES = {
    item["value"]: item["label"]
    for item in SUPPORTED_PROVIDERS
}

CATALOGUE_TIMEOUT = 20.0
MAX_FETCH_ATTEMPTS = 2


def _safe_metadata(value) -> dict:
    """Keep provider metadata JSON-safe before storing it."""
    if not isinstance(value, dict):
        return {}

    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )
        )
    except (TypeError, ValueError):
        logger.warning("AI provider returned invalid metadata.")
        return {}


class AIModelCatalogueService:
    def refresh_provider(
        self,
        *,
        company,
        provider: str,
        supplied_api_key: str | None,
    ) -> dict:
        provider = (provider or "").strip().lower()
        supplied_api_key = (supplied_api_key or "").strip()

        if not provider_exists(provider):
            raise ValueError("Unsupported AI provider.")

        configuration = (
            AIConfiguration.objects
            .filter(company=company)
            .first()
        )

        api_key = supplied_api_key

        # Never reuse a saved key for a different provider.
        if (
            not api_key
            and configuration is not None
            and configuration.is_active
            and configuration.provider == provider
        ):
            api_key = configuration.api_key or ""

        if not api_key:
            raise ValueError(
                "Enter the API key for this provider before refreshing models."
            )

        provider_client = build_provider(
            provider=provider,
            api_key=api_key,
            model="",
        )

        remote_models = None

        for attempt in range(MAX_FETCH_ATTEMPTS):
            try:
                remote_models = provider_client.list_models(
                    timeout=CATALOGUE_TIMEOUT,
                )
                break

            except AIProviderError as exc:
                if (
                    attempt >= MAX_FETCH_ATTEMPTS - 1
                    or exc.quota_exhausted
                    or not exc.retryable
                ):
                    raise

                wait_seconds = min(2 ** attempt, 4)
                time.sleep(wait_seconds)

        if not remote_models:
            raise AIProviderError(
                "The provider returned no usable models."
            )

        normalized_models: dict[str, dict] = {}

        for item in remote_models:
            model_id = str(
                item.get("model_id") or ""
            ).strip()

            if not model_id:
                continue

            model_name = str(
                item.get("model_name") or model_id
            ).strip() or model_id

            normalized_models[model_id] = {
                "model_name": model_name,
                "metadata": _safe_metadata(
                    item.get("metadata") or {}
                ),
            }

        if not normalized_models:
            raise AIProviderError(
                "The provider returned invalid model information."
            )

        now = timezone.now()
        synced_count = 0

        # External API call is intentionally outside this transaction.
        # Only DB changes happen inside the transaction.
        with transaction.atomic():
            for model_id, model_data in normalized_models.items():
                AIProviderModel.objects.update_or_create(
                    provider_key=provider,
                    model_id=model_id,
                    defaults={
                        "provider_name": PROVIDER_NAMES[provider],
                        "model_name": model_data["model_name"],
                        "metadata": model_data["metadata"],
                        "is_active": True,
                        "last_seen_at": now,
                    },
                )

                synced_count += 1

        return {
            "provider": provider,
            "provider_name": PROVIDER_NAMES[provider],
            "models": models_for(provider),
            "count": synced_count,
        }


ai_model_catalogue_service = AIModelCatalogueService()