"""
AI business logic.

AIService orchestrates a single question/answer turn. It performs no
business calculations and contains no NetSuite logic itself — business
context comes from context_builder, and provider calls are delegated
entirely to whichever AIProvider is injected, so swapping providers never
requires changing this class.
"""

import logging
from django.db import transaction
from accounts.models import User
from ai.context_builder import build_context
from ai.exceptions import AIConversationNotFoundException
from ai.models import AIConversation, AIMessage
from ai.prompts import build_system_prompt, build_user_prompt
from ai.providers import AIProvider, OpenAIProvider
from ai.repositories import ConversationRepository, MessageRepository
# from ai.providers import get_ai_provider
from ai.providers import AIProviderFactory
from common.constants import AI_CONVERSATION_HISTORY_LIMIT

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 60

# Used when NetSuite isn't connected yet — deliberately returned without
# calling the provider at all (Section: "Context Builder" / API example in
# the task spec). There is provably no business data to reason over yet,
# so the answer is deterministic rather than an LLM guess, and no provider
# cost is spent on a guaranteed non-informative reply.

NETSUITE_NOT_CONNECTED_ANSWER = (
    'Your NetSuite account is not connected yet. '
    'Please connect NetSuite to receive business insights.'
)

class AIService:
    def __init__(
        self,
        conversation_repository: ConversationRepository | None = None,
        message_repository: MessageRepository | None = None,
        provider: AIProvider | None = None,
    ):
        self.conversation_repository = conversation_repository or ConversationRepository()
        self.message_repository = message_repository or MessageRepository()
        self.provider = provider or AIProviderFactory.create()

    def ask(self, *, user: User, message: str, conversation_id=None) -> dict:
        """
        Receive a user question, persist it, generate a reply, persist
        that too, and return both the conversation id and the answer.
        """
        # _get_or_create_conversation() may create a new AIConversation
        # row, and the user's message is saved as an AIMessage row right
        # after — two different models that should either both succeed
        # or both roll back together, or a failed message-save would
        # leave an empty orphan conversation behind. The AI provider call
        # below is deliberately outside this block: it's an external HTTP
        # call and must never hold a DB transaction open while it runs.
        with transaction.atomic():
            conversation = self._get_or_create_conversation(
                user=user, conversation_id=conversation_id, message=message
            )

            self.message_repository.save(
                conversation=conversation, role=AIMessage.Role.USER, content=message
            )

        # Fetch +1 to account for the message we just saved, which we will exclude from history
        recent_messages = self.message_repository.get_recent_history(
            conversation=conversation, limit=AI_CONVERSATION_HISTORY_LIMIT + 1
        )
        
        # Skip the message we just saved (index 0) and reverse the rest for chronological order
        past_messages = recent_messages[1:]
        history = [
            {'role': msg.role.lower(), 'content': msg.content}
            for msg in reversed(past_messages)
        ]

        context = build_context(user)
        answer = self._generate_answer(context=context, message=message, history=history)

        self.message_repository.save(
            conversation=conversation, role=AIMessage.Role.ASSISTANT, content=answer
        )

        logger.info(
            'AI response generated for user %s (conversation=%s).', user.id, conversation.id
        )

        return {'conversation_id': str(conversation.id), 'answer': answer}

    def _get_or_create_conversation(
        self, *, user: User, conversation_id, message: str
    ) -> AIConversation:
        if conversation_id:
            conversation = self.conversation_repository.get_by_id_for_user(
                conversation_id=conversation_id, user=user
            )
            if conversation is None:
                raise AIConversationNotFoundException('Conversation not found.')
            return conversation

        return self.conversation_repository.create(user=user, title=self._build_title(message))

    @staticmethod
    def _build_title(message: str) -> str:
        stripped = message.strip()
        if not stripped:
            return 'New conversation'
        if len(stripped) <= TITLE_MAX_LENGTH:
            return stripped
        return f'{stripped[:TITLE_MAX_LENGTH - 1]}\u2026'

    def _generate_answer(self, *, context: dict, message: str, history: list[dict] | None = None) -> str:
        if not context.get('netsuite_connected'):
            return NETSUITE_NOT_CONNECTED_ANSWER

        # AIProviderNotConfiguredException / AIProviderRequestException are
        # intentionally left to propagate to the view and the standard
        # exception handler — a missing API key is a real configuration
        # problem, not something to silently mask as a successful reply.
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context=context, message=message)
        return self.provider.generate_response(
            system_prompt=system_prompt, user_prompt=user_prompt, history=history
        )