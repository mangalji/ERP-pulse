"""Root URL configuration for ERP Pulse.

All API endpoints are namespaced under /api/v1/ per BACKEND_CONTEXT.md.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/netsuite/', include('netsuite.urls')),
    path('api/v1/ai/', include('ai.urls')),
    path('api/v1/dashboard/', include('dashboard.urls')),
    path('api/v1/reports/', include('reports.urls')),
    path('api/v1/monitoring/', include('monitoring.urls')),
    path('api/v1/sync/', include('sync.urls')),
    path('api/v1/ocr/', include('ocr.urls')),
    path('api/v1/invoice/', include('invoice.urls')),
    path('api/v1/superadmin/', include('superadmin.urls')),
    path('api/v1/client/', include('tenancy.urls')),
    path('api/v1/bi/', include('bi.urls')),
    path('api/v1/reports-engine/', include('reports_engine.urls')),
    path('api/v1/demo/', include('demo.urls')),
    path('api/v1/invitations/', include('invitations.urls')),
    path('api/v1/subscriptions/', include('subscriptions.urls')),
]
