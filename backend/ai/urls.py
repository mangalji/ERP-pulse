from django.urls import path

from ai.views import ChatView, ConversationHistoryView

urlpatterns = [
    path('chat/', ChatView.as_view(), name='ai-chat'),
    path('history/', ConversationHistoryView.as_view(), name='ai-history'),
]
