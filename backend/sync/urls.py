from django.urls import path
from sync.views import RetrySyncRunView, SyncRunListCreateView, SyncRunDetailView

url_patterns = [
    path('runs/',SyncRunListCreateView.as_view(),name='sync-runs'),
    path('runs/<uuid:run_id>/',SyncRunDetailView.as_view(),name='sync-run-detail'),
    path('runs/<uuid:run_id>/retry/', RetrySyncRunView.as_view(), name='sync-run-retry'),
]
