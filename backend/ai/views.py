"""
AI Assistant API views.

Views only: authenticate, validate via serializer, call AIService, return
the standard response envelope — no business logic here, matching
accounts/views.py's established pattern exactly.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ai.repositories import ConversationRepository
from ai.serializers import AIChatRequestSerializer, AIConversationSerializer
from ai.services import AIService
from common.utils.response import success_response

ai_service = AIService()
conversation_repository = ConversationRepository()


class ChatView(APIView):
    """
    POST /api/v1/ai/chat/

    Sends a message to the AI Assistant and returns its reply. Creates a
    new conversation automatically when conversation_id is omitted.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = ai_service.ask(user=request.user, **serializer.validated_data)

        return success_response(
            message='Response generated successfully.',
            data=result,
        )


class ConversationHistoryView(APIView):
    """
    GET /api/v1/ai/history/

    Returns all AI conversations for the logged-in user, most recently
    updated first (AIConversation.Meta.ordering).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = conversation_repository.get_all_for_user(user=request.user)

        return success_response(
            message='Conversation history fetched successfully.',
            data=AIConversationSerializer(conversations, many=True).data,
        )
