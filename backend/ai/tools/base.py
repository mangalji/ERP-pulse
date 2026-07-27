"""
SelfDescribingTool abstraction.

Every tool wraps exactly one existing service method. Tools contain zero
business logic — they only delegate to the appropriate service and return
its output as-is. The metadata (name, description, parameters) lets the
Planner decide which tools to call without knowing their implementations.

Follows the same ABC pattern as AIProvider (ai/providers.py).
"""

from abc import ABC, abstractmethod
from typing import Any

from accounts.models import User


class SelfDescribingTool(ABC):
    """Abstract base for all tools. Each tool wraps one service method."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this tool (snake_case)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Plain-English explanation of what this tool does, for the Planner."""
        raise NotImplementedError

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """
        JSON Schema describing the tool's expected parameters.

        Used by the Planner to decide what arguments to supply. Example::

            {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return.",
                        "default": 5,
                    },
                },
            }
        """
        raise NotImplementedError

    @abstractmethod
    def execute(self, *, user: User, **kwargs) -> Any:
        """
        Execute this tool against its underlying service method.

        Args:
            user: The requesting user (forwarded to the service).
            **kwargs: Tool-specific parameters validated against `parameters`.

        Returns:
            The raw output from the existing service method — no
            reshaping, no business logic.
        """
        raise NotImplementedError

