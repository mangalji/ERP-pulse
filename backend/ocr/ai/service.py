"""Company-scoped AI configuration and provider resolution."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from ocr.ai.config import (
    DEFAULT_MODELS,
    model_exists,
    models_for,
    provider_exists,
)
from ocr.ai.providers import AIProviderError, build_provider
from ocr.models import AIConfiguration


class AIConfigurationService:
    def get_configuration(self, *, company) -> AIConfiguration | None:
        return (
            AIConfiguration.objects
            .filter(company=company)
            .first()
        )

    def serialize(self, configuration: AIConfiguration | None) -> dict:
        if configuration is None:
            return {
                "connected": False,
                "provider": "",
                "model": "",
                "api_key_set": False,
                "last_tested_at": None,
            }

        return {
            "connected": bool(configuration.is_active and configuration.api_key),
            "provider": configuration.provider,
            "model": configuration.model,
            "api_key_set": bool(configuration.api_key),
            "last_tested_at": configuration.last_tested_at,
        }

    def models(self, *, provider: str) -> list[dict]:
        if not provider_exists(provider):
            raise ValueError("Unsupported AI provider.")
        return models_for(provider)

    def _resolve_key(
        self,
        *,
        configuration: AIConfiguration | None,
        supplied_api_key: str | None,
    ) -> str:
        supplied = (supplied_api_key or "").strip()
        if supplied:
            return supplied
        if configuration is not None:
            return configuration.api_key or ""
        return ""

    def test(
        self,
        *,
        company,
        provider: str,
        model: str,
        api_key: str | None,
        user,
    ) -> None:
        provider = (provider or "").strip().lower()
        model = (model or "").strip()

        if not provider_exists(provider):
            raise ValueError("Unsupported AI provider.")
        if not model_exists(provider, model):
            raise ValueError("Selected model is not supported for this provider.")

        configuration = self.get_configuration(company=company)
        key = self._resolve_key(
            configuration=configuration,
            supplied_api_key=api_key,
        )
        if not key:
            raise ValueError("API key is required.")

        provider_client = build_provider(
            provider=provider,
            api_key=key,
            model=model,
        )
        provider_client.test_connection()

        if configuration is not None and configuration.is_active:
            configuration.last_tested_at = timezone.now()
            configuration.save(update_fields=["last_tested_at", "updated_at"])

    @transaction.atomic
    def connect(
        self,
        *,
        company,
        provider: str,
        model: str,
        api_key: str,
        user,
        request=None,
    ) -> AIConfiguration:
        provider = (provider or "").strip().lower()
        model = (model or "").strip()
        api_key = (api_key or "").strip()

        if not provider_exists(provider):
            raise ValueError("Unsupported AI provider.")
        if not model_exists(provider, model):
            raise ValueError("Selected model is not supported for this provider.")
        if not api_key:
            raise ValueError("API key is required.")

        provider_client = build_provider(
            provider=provider,
            api_key=api_key,
            model=model,
        )
        provider_client.test_connection()

        configuration, created = AIConfiguration.objects.get_or_create(
            company=company,
            defaults={
                "provider": provider,
                "model": model,
            },
        )

        configuration.provider = provider
        configuration.model = model
        configuration.api_key = api_key
        configuration.is_active = True
        configuration.last_tested_at = timezone.now()
        configuration.save()

        audit_service.log(
            module=AuditModule.AI,
            action=AuditAction.CONNECT,
            entity="AIConfiguration",
            entity_id=str(configuration.id),
            company=company,
            user=user,
            new_value={
                "event": "connected",
                "provider": provider,
                "model": model,
            },
            ip_address=getattr(request, "META", {}).get("REMOTE_ADDR")
            if request else None,
        )

        return configuration

    @transaction.atomic
    def disconnect(
        self,
        *,
        company,
        user,
        request=None,
    ) -> None:
        configuration = self.get_configuration(company=company)
        if configuration is None:
            return

        old_value = {
            "provider": configuration.provider,
            "model": configuration.model,
            "connected": configuration.is_active,
        }

        # Disconnect means credentials are removed, not merely hidden.
        configuration.api_key = ""
        configuration.is_active = False
        configuration.last_tested_at = None
        configuration.save(
            update_fields=[
                "api_key",
                "is_active",
                "last_tested_at",
                "updated_at",
            ]
        )

        audit_service.log(
            module=AuditModule.AI,
            action=AuditAction.DISCONNECT,
            entity="AIConfiguration",
            entity_id=str(configuration.id),
            company=company,
            user=user,
            old_value=old_value,
            new_value={"event": "disconnected"},
            ip_address=getattr(request, "META", {}).get("REMOTE_ADDR")
            if request else None,
        )

    def resolve_provider(self, *, company):
        configuration = (
            AIConfiguration.objects
            .filter(company=company, is_active=True)
            .first()
        )
        if configuration is None or not configuration.api_key:
            raise AIProviderError(
                "No active AI provider is configured for this company."
            )

        return build_provider(
            provider=configuration.provider,
            api_key=configuration.api_key,
            model=configuration.model,
        )


ai_configuration_service = AIConfigurationService()
