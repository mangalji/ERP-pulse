from django.urls import path

from mail_integration.views import (
    EmailIntegrationActivateView,
    EmailIntegrationCollectionView,
    EmailIntegrationInitialSyncView,
    EmailIntegrationSyncReadinessView,
    EmailIntegrationPauseView,
    EmailIntegrationResumeView,
    EmailIntegrationDisconnectView,
    EmailIntegrationReconnectView,
    EmailOAuthCallbackView,
)


urlpatterns = [
    path("integrations/", EmailIntegrationCollectionView.as_view(), name="email-integration-collection"),
    path("callback/", EmailOAuthCallbackView.as_view(), name="email-oauth-callback"),
    path("integrations/<uuid:integration_id>/activate/", EmailIntegrationActivateView.as_view(), name="email-integration-activate"),
    path("integrations/<uuid:integration_id>/initial-sync/", EmailIntegrationInitialSyncView.as_view(), name="email-integration-initial-sync"),
    path("integrations/<uuid:integration_id>/sync-readiness/", EmailIntegrationSyncReadinessView.as_view(), name="email-integration-sync-readiness"),
    path("integrations/<uuid:integration_id>/pause/", EmailIntegrationPauseView.as_view(), name="email-integration-pause"),
    path("integrations/<uuid:integration_id>/resume/", EmailIntegrationResumeView.as_view(), name="email-integration-resume"),
    path("integrations/<uuid:integration_id>/disconnect/", EmailIntegrationDisconnectView.as_view(), name="email-integration-disconnect"),
    path("integrations/<uuid:integration_id>/reconnect/", EmailIntegrationReconnectView.as_view(), name="email-integration-reconnect"),
]
