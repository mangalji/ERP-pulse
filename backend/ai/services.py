"""
AI business logic.

AIService orchestrates a single question/answer turn. It performs no
business calculations and contains no NetSuite logic itself — business
context comes from context_builder, and provider calls are delegated
entirely to whichever AIProvider is injected, so swapping providers never
requires changing this class.

Capability-driven pipeline (v4):
    Planner -> ToolExecutor -> ResultValidator -> capability prompt -> AI Provider
    Falls back to the existing ContextBuilder flow if anything fails.

Existing context-driven pipeline (v1-v3):
    ContextBuilder -> PromptBuilder -> AI Provider
    Remains available as a backward-compatible fallback.
"""

import logging
import time

from django.db import transaction
from accounts.models import User
from ai.business_context import AIRequestContext
from ai.context_builder import build_context
from ai.exceptions import AIConversationNotFoundException
from ai.executor import ToolExecutor
from ai.models import AIConversation, AIMessage
from ai.planner import Planner
from ai.prompts import (
    CAPABILITY_DRIVEN_SYSTEM_PROMPT,
    PROMPT_VERSION,
    build_system_prompt,
    build_user_prompt,
)
from ai.providers import AIProvider, AIProviderFactory
from ai.repositories import AIAuditLogRepository, ConversationRepository, MessageRepository
from ai.tools.registry import ToolRegistry
from ai.validator import ResultValidator, ToolResult
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
        self.audit_log_repository = AIAuditLogRepository()

        # New v4 components — created lazily so they don't affect existing flows.
        self._planner: Planner | None = None
        self._tool_registry: ToolRegistry | None = None
        self._tool_executor: ToolExecutor | None = None
        self._result_validator: ResultValidator | None = None

    @property
    def planner(self) -> Planner:
        if self._planner is None:
            self._planner = Planner(provider=self.provider)
        return self._planner

    @property
    def tool_registry(self) -> ToolRegistry:
        if self._tool_registry is None:
            self._tool_registry = ToolRegistry()
        return self._tool_registry

    @property
    def tool_executor(self) -> ToolExecutor:
        if self._tool_executor is None:
            self._tool_executor = ToolExecutor(registry=self.tool_registry)
        return self._tool_executor

    @property
    def result_validator(self) -> ResultValidator:
        if self._result_validator is None:
            self._result_validator = ResultValidator()
        return self._result_validator

    def ask(self, *, user: User, message: str, conversation_id=None) -> dict:
        """
        Receive a user question, persist it, generate a reply, persist
        that too, and return both the conversation id and the answer.

        Tries the capability-driven pipeline (v4) first. If that fails
        at any step, falls back to the existing context-driven pipeline
        (v1-v3). Backward compatible — no caller sees a difference.
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

        # Try capability-driven pipeline first.
        answer = self._try_capability_pipeline(
            user=user, message=message, conversation=conversation, history=history,
        )

        # Fallback to context-driven pipeline if capability pipeline
        # returned None (indicating a failure at some step).
        if answer is None:
            logger.info(
                "Capability pipeline produced no answer; falling back to context-driven flow "
                "for user %s (conversation=%s).",
                user.id, conversation.id,
            )
            context = build_context(user)
            answer = self._generate_answer(
                context=context, message=message, history=history,
                user=user, conversation=conversation,
            )

        self.message_repository.save(
            conversation=conversation, role=AIMessage.Role.ASSISTANT, content=answer
        )

        logger.info(
            'AI response generated for user %s (conversation=%s).', user.id, conversation.id
        )

        return {'conversation_id': str(conversation.id), 'answer': answer}

    def _try_capability_pipeline(
        self,
        *,
        user: User,
        message: str,
        conversation: AIConversation,
        history: list[dict] | None = None,
    ) -> str | None:
        """
        Attempt the capability-driven pipeline (v4).

        Steps:
        1. Planner decides which tools to call.
        2. ToolExecutor runs the tools.
        3. ResultValidator validates and formats results.
        4. Build capability-driven prompt with tool results.
        5. Call AI provider.

        Returns the answer string on success, or None to trigger fallback.
        """
        started_at = time.monotonic()

        try:
            # Step 1: Planner
            tool_descriptions = self.tool_registry.list_descriptions()
            plan = self.planner.plan(
                question=message,
                tool_descriptions=tool_descriptions,
            )

            if plan.is_empty:
                logger.info("Planner returned empty plan for: %.100s", message)
                return None

            # Step 2: Tool Executor
            raw_results = self.tool_executor.execute(plan=plan, user=user)
            if not raw_results:
                logger.info("ToolExecutor returned no results.")
                return None

            # Step 3: Result Validator
            validated_results = self.result_validator.validate_all(raw_results)

            # Step 4: Build capability-driven prompt
            user_prompt = self._build_capability_prompt(
                question=message,
                validated_results=validated_results,
            )

            # Step 5: Call AI provider
            answer = self.provider.generate_response(
                system_prompt=CAPABILITY_DRIVEN_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                history=history,
            )

            self.audit_log_repository.log(
                user=user,
                conversation=conversation,
                provider=self.provider.__class__.__name__,
                model=getattr(self.provider, 'model', None),
                prompt_version=PROMPT_VERSION,
                success=True,
                latency_ms=self._elapsed_ms(started_at),
            )

            return answer

        except Exception as exc:
            logger.exception(
                "Capability pipeline failed for user %s; will fall back.",
                user.id,
            )
            self.audit_log_repository.log(
                user=user,
                conversation=conversation,
                provider=self.provider.__class__.__name__,
                model=getattr(self.provider, 'model', None),
                prompt_version=PROMPT_VERSION,
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                error_message=str(exc)[:2000],
            )
            return None

    def _build_capability_prompt(
        self,
        *,
        question: str,
        validated_results: list[ToolResult],
    ) -> str:
        """Build a user prompt for the capability-driven pipeline."""
        sections = []
        for result in validated_results:
            header = f"--- Tool: {result.tool_name} ---"
            meta = result.metadata
            meta_line = (
                f"(validated: {meta['validation_success']}, "
                f"truncated: {meta['truncated']}, "
                f"items_removed: {meta['items_removed']})"
            )
            sections.append(f"{header}\n{meta_line}\n{result.formatted}")

        tool_results_block = "\n\n".join(sections)

        return (
            f"Tool results:\n{tool_results_block}\n\n"
            f"======= START USER INPUT =======\n"
            f"{question}\n"
            f"======= END USER INPUT ======="
        )

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

    def _generate_answer(
        self,
        *,
        context: AIRequestContext,
        message: str,
        history: list[dict] | None = None,
        user: User,
        conversation: AIConversation,
    ) -> str:
        """
        Existing context-driven flow (v1-v3). Unchanged — used as
        fallback when the capability pipeline fails.
        """
        if not context.netsuite_connected:
            return NETSUITE_NOT_CONNECTED_ANSWER

        # AIProviderNotConfiguredException / AIProviderRequestException are
        # intentionally left to propagate to the view and the standard
        # exception handler — a missing API key is a real configuration
        # problem, not something to silently mask as a successful reply.
        # They're still audit-logged (success=False) below before
        # re-raising, since a failed provider call is exactly the kind of
        # thing worth auditing.
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context=context, message=message)

        started_at = time.monotonic()
        try:
            answer = self.provider.generate_response(
                system_prompt=system_prompt, user_prompt=user_prompt, history=history
            )
        except Exception as exc:
            self.audit_log_repository.log(
                user=user,
                conversation=conversation,
                provider=self.provider.__class__.__name__,
                model=getattr(self.provider, 'model', None),
                prompt_version=PROMPT_VERSION,
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                error_message=str(exc)[:2000],
            )
            raise

        self.audit_log_repository.log(
            user=user,
            conversation=conversation,
            provider=self.provider.__class__.__name__,
            model=getattr(self.provider, 'model', None),
            prompt_version=PROMPT_VERSION,
            success=True,
            latency_ms=self._elapsed_ms(started_at),
        )
        return answer

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return int((time.monotonic() - started_at) * 1000)
