from django.urls import path

from ocr.ai.views import (
    AIConfigurationDisconnectView,
    AIConfigurationTestView,
    AIConfigurationView,
    AIProvidersView,
)

urlpatterns = [
    path("config/", AIConfigurationView.as_view(), name="ocr-ai-config"),
    path("config/test/", AIConfigurationTestView.as_view(), name="ocr-ai-config-test"),
    path("config/disconnect/", AIConfigurationDisconnectView.as_view(), name="ocr-ai-config-disconnect"),
    path("providers/", AIProvidersView.as_view(), name="ocr-ai-providers"),
]
