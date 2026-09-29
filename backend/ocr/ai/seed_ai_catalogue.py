from __future__ import annotations

import os
import uuid

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.local",
)

from django import setup

setup()
from ocr.models import AIProviderModel


PROVIDERS = {
    "google": {
        "name": "Google",
        "models": [
            # Gemini 3 family
            ("gemini-3.8-flash", "Gemini 3.8 Flash"),
            ("gemini-3.8-live", "Gemini 3.8 Live"),
            (
                "gemini-3.8-live-extended-thinking",
                "Gemini 3.8 Live Extended Thinking",
            ),
            ("gemini-3.8-flash-tts", "Gemini 3.8 Flash TTS"),
            ("gemini-3.8-flash-lite-tts", "Gemini 3.8 Flash-Lite TTS"),
            ("gemini-3.7-flash", "Gemini 3.7 Flash"),
            ("gemini-3.1-pro-preview", "Gemini 3.1 Pro"),
            ("gemini-3-flash-preview", "Gemini 3 Flash"),
            (
                "gemini-3.5-live-translate-preview",
                "Gemini 3.5 Live Translate",
            ),
            (
                "gemini-3.1-flash-live-preview",
                "Gemini 3.1 Flash Live",
            ),
            (
                "gemini-3.1-flash-tts-preview",
                "Gemini 3.1 Flash TTS",
            ),
            ("gemini-omni-1.1-flash", "Gemini Omni Flash"),
            ("gemini-3.5-transcribe", "Gemini 3.5 Transcribe"),
            (
                "gemini-3.5-transcribe-live",
                "Gemini 3.5 Transcribe Live",
            ),

            # Gemini 2.5 family
            ("gemini-2.5-flash", "Gemini 2.5 Flash"),
            ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite"),
            ("gemini-2.5-pro", "Gemini 2.5 Pro"),
            (
                "gemini-2.5-flash-image",
                "Gemini 2.5 Flash Image",
            ),
            (
                "gemini-2.5-flash-native-audio-preview-12-2025",
                "Gemini 2.5 Flash Live",
            ),
            (
                "gemini-2.5-flash-preview-tts",
                "Gemini 2.5 Flash TTS",
            ),
            (
                "gemini-2.5-pro-preview-tts",
                "Gemini 2.5 Pro TTS",
            ),

            # Specialized Gemini models
            (
                "gemini-embedding-2-preview",
                "Gemini Embedding 2",
            ),
            (
                "gemini-embedding-001",
                "Gemini Embedding",
            ),
            (
                "gemini-robotics-er-2-preview",
                "Gemini Robotics ER 2",
            ),
            (
                "gemini-robotics-er-1.6-preview",
                "Gemini Robotics ER 1.6",
            ),
            (
                "gemini-2.5-computer-use-preview-10-2025",
                "Gemini Computer Use",
            ),
            (
                "deep-research-preview-04-2026",
                "Gemini Deep Research",
            ),
            (
                "deep-research-max-preview-04-2026",
                "Gemini Deep Research Max",
            ),
            (
                "antigravity-preview-09-2026",
                "Antigravity Agent",
            ),
        ],
    },

    "openai": {
        "name": "OpenAI",
        "models": [
            # GPT-6
            ("gpt-6-astra", "GPT-6 Astra"),
            ("gpt-6-sol", "GPT-6 Sol"),
            ("gpt-6-luna", "GPT-6 Luna"),

            # GPT-5.6
            ("gpt-5.6-sol", "GPT-5.6 Sol"),
            ("gpt-5.6-terra", "GPT-5.6 Terra"),
            ("gpt-5.6-luna", "GPT-5.6 Luna"),

            # GPT-5.x
            ("gpt-5.5", "GPT-5.5"),
            ("gpt-5.5-pro", "GPT-5.5 Pro"),
            ("gpt-5.4", "GPT-5.4"),
            ("gpt-5.4-pro", "GPT-5.4 Pro"),
            ("gpt-5.4-mini", "GPT-5.4 Mini"),
            ("gpt-5.4-nano", "GPT-5.4 nano"),
            ("gpt-5.3-codex", "GPT-5.3 Codex"),
            ("gpt-5.2", "GPT-5.2"),
            ("gpt-5.2-pro", "GPT-5.2 Pro"),
            ("gpt-5.1", "GPT-5.1"),
            ("gpt-5", "GPT-5"),
            ("gpt-5-mini", "GPT-5 Mini"),
            ("gpt-5-nano", "GPT-5 nano"),
            ("gpt-5-pro", "GPT-5 Pro"),

            # o-series
            ("o3-pro", "o3-pro"),
            ("o3", "o3"),

            # GPT-4.1 family
            ("gpt-4.1", "GPT-4.1"),
            ("gpt-4.1-mini", "GPT-4.1 Mini"),

            # GPT-4o family
            ("gpt-4o", "GPT-4o"),
            ("gpt-4o-mini", "GPT-4o Mini"),

            # Embeddings
            ("text-embedding-3-large", "text-embedding-3-large"),
            ("text-embedding-3-small", "text-embedding-3-small"),
            ("text-embedding-ada-002", "text-embedding-ada-002"),

            # Open-weight
            ("gpt-oss-120b", "gpt-oss-120b"),
            ("gpt-oss-20b", "gpt-oss-20b"),

            # Audio / transcription
            ("gpt-realtime-2.1", "GPT-Realtime-2.1"),
            ("gpt-realtime-2.1-mini", "GPT-Realtime-2.1 Mini"),
            ("gpt-realtime-2", "GPT-Realtime-2"),
            ("gpt-realtime-translate", "GPT-Realtime-Translate"),
            ("gpt-live-1", "GPT-Live 1"),
            ("gpt-live-transcribe", "GPT-Live-Transcribe"),
            ("gpt-realtime-whisper", "GPT-Realtime-Whisper"),
            ("gpt-realtime-1.5", "GPT-Realtime-1.5"),
            ("gpt-audio-1.5", "GPT-Audio-1.5"),
            ("gpt-transcribe", "GPT-Transcribe"),
            ("gpt-4o-transcribe", "GPT-4o Transcribe"),
            ("gpt-4o-mini-transcribe", "GPT-4o Mini Transcribe"),

            # Text-to-speech
            ("gpt-4o-mini-tts", "GPT-4o Mini TTS"),
            ("tts-1", "TTS-1"),
            ("tts-1-hd", "TTS-1 HD"),

            # Moderation
            ("omni-moderation", "omni-moderation"),
        ],
    },

    "anthropic": {
        "name": "Anthropic",
        "models": [
            ("claude-fable-5-1", "Claude Fable 5.1"),
            ("claude-opus-5-5", "Claude Opus 5.5"),
            ("claude-opus-5", "Claude Opus 5"),
            ("claude-sonnet-5", "Claude Sonnet 5"),
            (
                "claude-haiku-4-5-20251001",
                "Claude Haiku 4.5",
            ),
        ],
    },
}


def seed_catalogue() -> None:
    total_created = 0
    total_updated = 0

    for provider_key, provider_data in PROVIDERS.items():
        provider_name = provider_data["name"]

        for model_id, model_name in provider_data["models"]:
            obj, created = AIProviderModel.objects.update_or_create(
                provider_key=provider_key,
                model_id=model_id,
                defaults={
                    "id": uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"agsuite-ai:{provider_key}:{model_id}",
                    ),
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "metadata": {},
                    "is_active": True,
                },
            )

            if created:
                total_created += 1
            else:
                total_updated += 1

    print(
        f"AI catalogue seeded successfully. "
        f"Created={total_created}, Updated={total_updated}"
    )


if __name__ == "__main__":
    seed_catalogue()