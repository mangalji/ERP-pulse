"""
AI Assistant API views.

Views only: authenticate, validate via serializer, call AIService, return
the standard response envelope — no business logic here, matching
accounts/views.py's established pattern exactly.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ai.exceptions import AIConversationNotFoundException
from ai.repositories import ConversationRepository, MessageRepository
from ai.serializers import AIChatRequestSerializer, AIConversationSerializer, AIMessageSerializer
from ai.services import AIService
from common.utils.response import success_response
from common.throttles import AIChatThrottle
from rest_framework.response import Response
from rest_framework import status

conversation_repository = ConversationRepository()
message_repository = MessageRepository()


class ChatView(APIView):
    """
    POST /api/v1/ai/chat/

    Sends a message to the AI Assistant and returns its reply. Creates a
    new conversation automatically when conversation_id is omitted.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [AIChatThrottle]

    def post(self, request):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = AIService().ask(
                user=request.user,
                **serializer.validated_data,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

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


class ConversationMessagesView(APIView):
    """
    GET /api/v1/ai/history/<conversation_id>/messages/

    Returns all messages for a specific AI conversation.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = conversation_repository.get_by_id_for_user(
            conversation_id=conversation_id, user=request.user
        )
        if not conversation:
            raise AIConversationNotFoundException('Conversation not found.')

        messages = message_repository.get_history(conversation=conversation)

        return success_response(
            message='Conversation messages fetched successfully.',
            data=AIMessageSerializer(messages, many=True).data,
        )
