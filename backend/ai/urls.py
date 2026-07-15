from django.urls import path

from ai.views import ChatView, ConversationHistoryView, ConversationMessagesView

urlpatterns = [
    path('chat/', ChatView.as_view(), name='ai-chat'),
    path('history/', ConversationHistoryView.as_view(), name='ai-history'),
    path('history/<uuid:conversation_id>/messages/', ConversationMessagesView.as_view(), name='ai-history-messages'),
]
