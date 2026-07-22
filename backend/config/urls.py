"""
Root URL configuration for ERP Pulse.

All API endpoints are namespaced under /api/v1/ per BACKEND_CONTEXT.md.
No app currently exposes endpoints (only the `common` app exists on Day 1,
and it holds no views), so the /api/v1/ prefix is not yet mounted here.
It will be added starting Day 2 as app-level urls.py files are created,
e.g. path('api/v1/accounts/', include('accounts.urls')).
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
]
