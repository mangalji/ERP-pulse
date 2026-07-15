"""
Persistence-only operations for AIConversation and AIMessage.

No business logic here — deciding *whether* to create a new conversation,
what its title should be, or what counts as "the history to send to a
provider" is AIService's job (services.py). These classes only read from
and write to the database.
"""

from accounts.models import User
from ai.models import AIConversation, AIMessage


class ConversationRepository:
    def create(self, *, user: User, title: str) -> AIConversation:
        return AIConversation.objects.create(user=user, title=title)

    def get_by_id_for_user(self, *, conversation_id, user: User) -> AIConversation | None:
        """
        Scoped to `user` on every lookup so one user can never fetch (or
        continue) another user's conversation by guessing/supplying an ID.
        """
        return AIConversation.objects.filter(id=conversation_id, user=user).first()

    def get_all_for_user(self, *, user: User):
        return AIConversation.objects.filter(user=user)


class MessageRepository:
    def save(self, *, conversation: AIConversation, role: str, content: str) -> AIMessage:
        return AIMessage.objects.create(conversation=conversation, role=role, content=content)

    def get_history(self, *, conversation: AIConversation):
        return AIMessage.objects.filter(conversation=conversation)

    def get_recent_history(self, *, conversation: AIConversation, limit: int) -> list[AIMessage]:
        """
        Most recent `limit` messages, in reverse-chronological order
        (most recent first). Used only to build bounded prompt context
        (AIService) — deliberately a different method from get_history()
        rather than a `limit=None` parameter on it, so the two very
        different callers (full conversation display vs. bounded LLM
        context) can't be confused with each other at the call site.
        Callers that need chronological order (e.g. for a prompt) should
        reverse this themselves — ordering-for-a-purpose is a service
        concern, not a persistence one.
        """
        return list(
            AIMessage.objects.filter(conversation=conversation).order_by('-created_at')[:limit]
            )
    