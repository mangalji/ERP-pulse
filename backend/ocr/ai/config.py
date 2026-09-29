"""Static supported AI providers with database-backed model catalogue."""

from __future__ import annotations

from ocr.models import AIProviderModel


SUPPORTED_PROVIDERS = (
    {"value": "google", "label": "Google"},
    {"value": "openai", "label": "OpenAI"},
    {"value": "anthropic", "label": "Anthropic"},
)


def providers_for() -> list[dict]:
    """Return the AI providers implemented by AGSuite."""
    return list(SUPPORTED_PROVIDERS)


def provider_exists(provider: str) -> bool:
    """Return whether AGSuite has an implemented provider adapter."""
    return any(
        item["value"] == provider
        for item in SUPPORTED_PROVIDERS
    )


def model_exists(provider: str, model: str) -> bool:
    """Return whether an active model exists in the database catalogue."""
    return (
        AIProviderModel.objects
        .filter(
            provider_key=provider,
            model_id=model,
            is_active=True,
        )
        .exists()
    )


def models_for(provider: str) -> list[dict]:
    """Return active models for a provider from the database."""
    rows = (
        AIProviderModel.objects
        .filter(
            provider_key=provider,
            is_active=True,
        )
        .order_by("model_name", "model_id")
    )

    return [
        {
            "value": row.model_id,
            "label": row.model_name,
            "metadata": row.metadata,
        }
        for row in rows
    ]