from rest_framework import serializers

from ai.models import AIConversation, AIMessage


class AIChatRequestSerializer(serializers.Serializer):
    """
    Validates POST /api/v1/ai/chat/ input.

    Field-level validation only. Whether conversation_id actually belongs
    to the requesting user is a business rule, decided by AIService (which
    raises AIConversationNotFoundException) — not duplicated here.
    """

    message = serializers.CharField(max_length=4000, allow_blank=False, trim_whitespace=True)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)


class AIConversationSerializer(serializers.ModelSerializer):
    """
    Used by GET /api/v1/ai/history/. Deliberately excludes nested messages
    — no endpoint in this task exposes individual message content, only
    the conversation list itself (title, timestamps).
    """

    class Meta:
        model = AIConversation
        fields = ['id', 'title', 'created_at', 'updated_at']
        read_only_fields = fields


class AIMessageSerializer(serializers.ModelSerializer):
    """Used by GET /api/v1/ai/history/<conversation_id>/messages/."""

    class Meta:
        model = AIMessage
        fields = ['id', 'role', 'content', 'created_at']
        read_only_fields = fields
