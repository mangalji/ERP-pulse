"""
Planner — decides HOW a user request should be processed.

The Planner receives the user's natural-language question and a list of
available tool descriptions, then uses an LLM to decide which tools are
needed and with what parameters. It returns an ExecutionPlan — a
structured, tool-only sequence — and does nothing else.

The Planner must NEVER:
- Calculate business metrics (that's AnalyticsService's job)
- Access repositories or the database
- Communicate with NetSuite
- Duplicate AnalyticsService logic
- Answer user questions directly
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ai.exceptions import AIProviderNotConfiguredException, AIProviderRequestException
from ai.providers import AIProvider, AIProviderFactory
from ai.prompts import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ExecutionPlan:
    """
    The output of the Planner — a structured plan describing which tools
    to call and with what parameters.

    Fields
    ------
    tool_calls : list[ToolCall]
        Ordered list of tool invocations to execute.
    original_question : str
        The user's original message, preserved for downstream use.
    """

    @dataclass
    class ToolCall:
        """A single tool invocation within an ExecutionPlan."""

        name: str
        params: dict[str, Any] = field(default_factory=dict)

    tool_calls: list[ToolCall] = field(default_factory=list)
    original_question: str = ""

    @property
    def is_empty(self) -> bool:
        """True when no tools were selected — Planner found no relevant tool."""
        return len(self.tool_calls) == 0


class Planner:
    """
    Uses an LLM to map a user question to a sequence of tool calls.

    The Planner is stateless — it takes a question + tool descriptions,
    calls the LLM once, and returns an ExecutionPlan. It performs no
    business logic, accesses no databases, and communicates with no
    external systems except the AI provider.

    Supports dependency injection: pass a provider to override the
    default (useful for testing). If None, uses AIProviderFactory.

    Parameters
    ----------
    provider : AIProvider | None
        The AI provider instance to use for planning. If None, created
        from AIProviderFactory.
    """

    # Maximum number of tools the Planner is allowed to select per request.
    MAX_TOOLS_PER_PLAN = 5

    # Expected top-level keys in the JSON output from the LLM.
    EXPECTED_TOP_LEVEL_KEY = "tools"

    # Expected keys per tool entry.
    EXPECTED_TOOL_KEYS = {"name", "params"}

    def __init__(self, provider: AIProvider | None = None):
        self._provider = provider or AIProviderFactory.create()

    def plan(
        self,
        *,
        question: str,
        tool_descriptions: list[dict[str, Any]],
    ) -> ExecutionPlan:
        """
        Produce an ExecutionPlan for the given question.

        Args:
            question: The user's natural-language question.
            tool_descriptions: List of dicts with ``name``, ``description``,
                and ``parameters`` keys — the output of
                ``ToolRegistry.list_descriptions()``.

        Returns:
            An ExecutionPlan with zero or more tool calls.
        """
        if not tool_descriptions:
            return ExecutionPlan(
                tool_calls=[],
                original_question=question,
            )

        tool_descriptions_json = json.dumps(tool_descriptions, indent=2)
        user_prompt = (
            f"Available tools:\n{tool_descriptions_json}\n\n"
            f"User question: {question}\n\n"
            "Decide which tools are needed and output the JSON plan."
        )

        try:
            raw = self._provider.generate_response(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except (AIProviderNotConfiguredException, AIProviderRequestException):
            # If the LLM is unavailable, return an empty plan — the caller
            # (AIService) can fall back to the existing context-driven flow.
            logger.warning("Planner LLM unavailable; returning empty plan.")
            return ExecutionPlan(original_question=question)

        return self._parse_plan(raw, question=question)

    def _parse_plan(self, raw: str, *, question: str) -> ExecutionPlan:
        """
        Parse the LLM's JSON output into an ExecutionPlan.

        Validates structure before building the plan:
        - Must be valid JSON.
        - Must contain a "tools" key whose value is a list.
        - Each entry must be a dict with at least "name" (string) and
          optionally "params" (dict).
        - Unknown keys are silently ignored.
        - Malformed entries are skipped (not crashed on).

        If parsing fails at any level, returns an empty plan so the
        caller can fall back gracefully rather than crash.
        """
        # Step 1: Parse JSON.
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Planner received malformed JSON: %.200s", raw)
            return ExecutionPlan(original_question=question)

        # Step 2: Validate top-level structure.
        if not isinstance(payload, dict):
            logger.warning("Planner expected a JSON object, got %s.", type(payload).__name__)
            return ExecutionPlan(original_question=question)

        raw_tools = payload.get(self.EXPECTED_TOP_LEVEL_KEY, [])
        if not isinstance(raw_tools, list):
            logger.warning(
                "Planner expected '%s' to be a list, got %s.",
                self.EXPECTED_TOP_LEVEL_KEY,
                type(raw_tools).__name__,
            )
            return ExecutionPlan(original_question=question)

        # Step 3: Validate each tool entry.
        tool_calls = []
        for idx, item in enumerate(raw_tools[:self.MAX_TOOLS_PER_PLAN]):
            if not isinstance(item, dict):
                logger.warning("Planner tool entry %d is not a dict; skipping.", idx)
                continue

            name = item.get("name", "")
            if not isinstance(name, str) or not name.strip():
                logger.warning("Planner tool entry %d has no valid 'name'; skipping.", idx)
                continue

            params = item.get("params", {})
            if not isinstance(params, dict):
                logger.warning(
                    "Planner tool entry %d ('%s') has non-dict params; treating as empty.",
                    idx,
                    name,
                )
                params = {}

            tool_calls.append(ExecutionPlan.ToolCall(name=name.strip(), params=params))

        return ExecutionPlan(tool_calls=tool_calls, original_question=question)
