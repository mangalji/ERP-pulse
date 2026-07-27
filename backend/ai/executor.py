"""
Tool Executor — executes tools according to an ExecutionPlan.

Responsibilities:
- Accepts an ExecutionPlan and runs its tool calls in order.
- Passes validated parameters to each tool via ToolRegistry.
- Collects ToolResult objects (one per tool call).
- Handles individual tool failures gracefully (never crashes the chain).
- Never performs business logic, never calls repositories directly,
  never calculates metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from accounts.models import User
from ai.planner import ExecutionPlan
from ai.tools.registry import ToolRegistry
from ai.validator import ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tools according to an ExecutionPlan.

    Uses a shared ToolRegistry instance (avoids reconstructing services
    for every tool call). Each tool call produces a ToolResult; a single
    failure never crashes the entire batch.

    Parameters
    ----------
    registry : ToolRegistry | None
        The tool registry to use. If None, creates a fresh one.
    """

    def __init__(self, registry: ToolRegistry | None = None):
        self._registry = registry or ToolRegistry()

    def execute(
        self,
        *,
        plan: ExecutionPlan,
        user: User,
    ) -> list[ToolResult]:
        """
        Execute all tool calls in the plan, in order.

        Args:
            plan: The ExecutionPlan from the Planner.
            user: The requesting user.

        Returns:
            A list of ToolResult objects, one per tool call in the plan.
            Failed tool calls produce a ToolResult with success=False
            and the error message captured, rather than raising.
        """
        if plan.is_empty:
            logger.info("Executor received empty plan — no tools to run.")
            return []

        tool_names = [tc.name for tc in plan.tool_calls]
        logger.info(
            "Executor starting %d tool(s): %s",
            len(tool_names),
            ", ".join(tool_names),
        )

        results: list[ToolResult] = []
        for idx, tool_call in enumerate(plan.tool_calls, start=1):
            logger.debug(
                "Executor running tool %d/%d: '%s' with params=%s",
                idx,
                len(plan.tool_calls),
                tool_call.name,
                tool_call.params,
            )
            result = self._execute_single(
                name=tool_call.name,
                params=tool_call.params,
                user=user,
            )
            results.append(result)

        # Log execution summary
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        if fail_count > 0:
            logger.warning(
                "Executor completed: %d succeeded, %d failed.",
                success_count,
                fail_count,
            )
        else:
            logger.info(
                "Executor completed: all %d tool(s) succeeded.",
                success_count,
            )

        return results

    def _execute_single(
        self,
        *,
        name: str,
        params: dict[str, Any],
        user: User,
    ) -> ToolResult:
        """
        Execute a single tool call and return a ToolResult.

        Catches all exceptions so one failed tool never breaks the
        remaining tools in the plan.
        """
        tool = self._registry.get_tool(name)
        if tool is None:
            logger.warning("Executor: unknown tool '%s' — skipping.", name)
            return ToolResult(
                tool_name=name,
                raw_data=None,
                success=False,
                error_message=f"Unknown tool: '{name}'.",
            )

        try:
            raw_data = self._registry.execute(name=name, user=user, **params)
            logger.debug("Executor: tool '%s' completed successfully.", name)
            return ToolResult(
                tool_name=name,
                raw_data=raw_data,
                success=True,
            )
        except Exception as exc:
            logger.exception("Executor: tool '%s' execution failed.", name)
            return ToolResult(
                tool_name=name,
                raw_data=None,
                success=False,
                error_message=str(exc)[:2000],
            )

