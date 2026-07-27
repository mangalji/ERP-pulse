"""
Result Validator — prepares tool output for downstream consumption.

Responsibilities (no business calculations):
- Serialisation of tool results into LLM-friendly text or structured dicts.
- Truncation of oversized datasets to stay within provider context limits.
- Handling of missing/None values (null -> "N/A" or empty string).
- Normalisation of result shapes so downstream consumers get consistent types.
- Exposure of validation metadata (truncated, items_removed, serialization_errors).

The Validator performs zero business calculations — it only transforms
existing data into a more suitable format for LLM consumption.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Soft limit on the serialised string length of a single tool result.
# Beyond this, the result is truncated to avoid blowing the LLM context.
# Reduced from 5_000 to 3_000 in Sprint 3 — tool results rarely need
# more than 3K chars for the LLM to summarise, and the saved context
# space improves token efficiency.
MAX_RESULT_CHARS = 3_000

# Maximum number of items preserved from list-shaped results.
MAX_LIST_ITEMS = 50

# Maximum nesting depth when serialising dict-shaped results.
# Prevents infinite recursion on deeply nested or circular structures.
MAX_DICT_DEPTH = 5


class ToolResult:
    """
    Wraps a raw tool execution result with validation and formatting.

    Parameters
    ----------
    tool_name : str
        The name of the tool that produced this result.
    raw_data : Any
        The raw output from the tool's execute() call.
    success : bool
        Whether the tool executed without error.
    error_message : str | None
        If success is False, a description of what went wrong.
    """

    def __init__(
        self,
        *,
        tool_name: str,
        raw_data: Any,
        success: bool = True,
        error_message: str | None = None,
    ):
        self.tool_name = tool_name
        self.raw_data = raw_data
        self.success = success
        self.error_message = error_message
        self._validated = False
        self._formatted: str | None = None

        # Metadata — populated during validate()
        self.validation_success: bool = True
        self.truncated: bool = False
        self.items_removed: int = 0
        self.serialization_errors: int = 0

    def validate(self) -> ToolResult:
        """
        Validate and format this result.

        After calling this method, ``.formatted`` contains a string-safe
        representation suitable for inclusion in an LLM prompt, and the
        metadata fields (truncated, items_removed, serialization_errors,
        validation_success) are populated.
        """
        if self._validated:
            return self

        if not self.success:
            self._formatted = (
                f"[Tool '{self.tool_name}' failed: "
                f"{self.error_message or 'Unknown error.'}]"
            )
            self.validation_success = False
            self._validated = True
            return self

        try:
            self._formatted, metadata = self._serialize(self.raw_data)
            self.truncated = metadata.get("truncated", False)
            self.items_removed = metadata.get("items_removed", 0)
            self.serialization_errors = metadata.get("serialization_errors", 0)
            self.validation_success = True
        except Exception as exc:
            self._formatted = (
                f"[Tool '{self.tool_name}' serialization failed: {exc}]"
            )
            self.validation_success = False
            self.serialization_errors = 1
            logger.exception("ToolResult serialization failed for '%s'.", self.tool_name)

        self._validated = True
        return self

    @property
    def formatted(self) -> str:
        """The validated, string-safe representation of this result."""
        if not self._validated:
            raise RuntimeError("Call .validate() before accessing .formatted")
        return self._formatted or ""

    @property
    def metadata(self) -> dict[str, Any]:
        """
        Validation metadata for downstream consumers.

        Returns a dict with:
        - validation_success: bool
        - truncated: bool
        - items_removed: int
        - serialization_errors: int
        """
        if not self._validated:
            raise RuntimeError("Call .validate() before accessing .metadata")
        return {
            "validation_success": self.validation_success,
            "truncated": self.truncated,
            "items_removed": self.items_removed,
            "serialization_errors": self.serialization_errors,
        }

    def _serialize(self, data: Any, _depth: int = 0) -> tuple[str, dict[str, Any]]:
        """
        Recursively serialize data into a string-safe format.

        Returns (formatted_string, metadata_dict).
        """
        metadata: dict[str, Any] = {
            "truncated": False,
            "items_removed": 0,
            "serialization_errors": 0,
        }

        if data is None:
            return "N/A", metadata

        if isinstance(data, (str, int, float, bool)):
            return str(data), metadata

        if isinstance(data, (list, tuple)):
            return self._serialize_list(list(data))

        if isinstance(data, dict):
            return self._serialize_dict(data)

        # Fallback for any other type (e.g. Decimal, datetime).
        try:
            return str(data), metadata
        except Exception:
            metadata["serialization_errors"] = 1
            return "[Unserializable value]", metadata

    def _serialize_list(self, items: list) -> tuple[str, dict[str, Any]]:
        metadata: dict[str, Any] = {
            "truncated": False,
            "items_removed": 0,
            "serialization_errors": 0,
        }

        if not items:
            return "[]", metadata

        total = len(items)
        truncated = items[:MAX_LIST_ITEMS]
        if len(truncated) < total:
            metadata["items_removed"] = total - MAX_LIST_ITEMS

        serialized_parts = []
        errors = 0
        for item in truncated:
            try:
                part, _ = self._serialize(item, _depth=1)
                serialized_parts.append(part)
            except Exception:
                serialized_parts.append("[Error]")
                errors += 1

        metadata["serialization_errors"] = errors

        result = "\n".join(serialized_parts)
        if metadata["items_removed"] > 0:
            result += f"\n... and {metadata['items_removed']} more items."

        # Char-level truncation if still too long.
        if len(result) > MAX_RESULT_CHARS:
            result = result[:MAX_RESULT_CHARS] + "\n... [truncated]"
            metadata["truncated"] = True

        return result, metadata

    def _serialize_dict(self, data: dict) -> tuple[str, dict[str, Any]]:
        metadata: dict[str, Any] = {
            "truncated": False,
            "items_removed": 0,
            "serialization_errors": 0,
        }

        try:
            serialized = json.dumps(data, indent=2, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fallback for non-JSON-serializable dicts (e.g. Django model instances).
            serialized = str(data)
            metadata["serialization_errors"] = 1

        if len(serialized) > MAX_RESULT_CHARS:
            serialized = serialized[:MAX_RESULT_CHARS] + "\n... [truncated]"
            metadata["truncated"] = True

        return serialized, metadata

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return f"<ToolResult {self.tool_name} ({status})>"


class ResultValidator:
    """
    Orchestrates validation and formatting for a collection of tool results.

    Usage::

        validator = ResultValidator()
        validated = validator.validate_all(results)
        for vr in validated:
            print(vr.formatted)
            print(vr.metadata)
    """

    def validate_all(self, results: list[ToolResult]) -> list[ToolResult]:
        """
        Validate every ToolResult in the list.

        Args:
            results: Raw tool results, possibly unvalidated.

        Returns:
            The same list of ToolResult instances, each with .validate()
            already called. This is safe to call multiple times.
        """
        for result in results:
            result.validate()
        return results

