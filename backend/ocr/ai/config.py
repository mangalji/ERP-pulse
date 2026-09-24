"""AI provider and OCR-capable model catalogue.

The catalogue is intentionally application-owned rather than trusting arbitrary
model IDs from the browser. Provider APIs can change independently; updating
this small catalogue lets the UI expose only models that AGSuite has explicitly
approved for OCR/document extraction.
"""

PROVIDERS = (
    {"value": "google", "label": "Google"},
    {"value": "openai", "label": "OpenAI"},
    {"value": "anthropic", "label": "Anthropic"},
)

MODELS = {
    "google": (
        {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
        {"value": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite"},
    ),
    "openai": (
        {"value": "gpt-4.1", "label": "GPT-4.1"},
        {"value": "gpt-4.1-mini", "label": "GPT-4.1 mini"},
        {"value": "gpt-5.1", "label": "GPT-5.1"},
        {"value": "gpt-5-mini", "label": "GPT-5 mini"},
    ),
    "anthropic": (
        {"value": "claude-opus-5", "label": "Claude Opus 5"},
        {"value": "claude-sonnet-5", "label": "Claude Sonnet 5"},
        {"value": "claude-opus-4-6", "label": "Claude Opus 4.6"},
        {"value": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
        {"value": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5"},
    ),
}

DEFAULT_MODELS = {
    "google": "gemini-2.5-flash",
    "openai": "gpt-5.1",
    "anthropic": "claude-sonnet-4-6",
}

def provider_exists(provider: str) -> bool:
    return provider in MODELS

def model_exists(provider: str, model: str) -> bool:
    return any(item["value"] == model for item in MODELS.get(provider, ()))

def models_for(provider: str) -> list[dict]:
    return list(MODELS.get(provider, ()))
