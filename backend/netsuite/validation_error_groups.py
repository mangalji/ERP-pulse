"""Helpers for presenting repeated line validation errors once.

Validation keeps every source line intact.  These groups are deliberately a
read-only view used by the UI and AI diagnostics, never by posting.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


_LINE_REFERENCE_KEYS = {"line_index", "affected_lines"}


def _stable_value(value: Any) -> str:
    """Return an order-independent representation suitable for grouping."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return str(value)


def _line_for_index(
    line_items: Sequence[Any],
    line_index: Any,
) -> Any:
    try:
        index = int(line_index)
    except (TypeError, ValueError):
        return None

    if index < 1 or index > len(line_items):
        return None

    line = line_items[index - 1]
    return line if isinstance(line, Mapping) else None


def _error_without_line_references(error: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in error.items()
        if str(key) not in _LINE_REFERENCE_KEYS
    }


def build_validation_error_groups(
    errors: Any,
    line_items: Any,
) -> list[dict[str, Any]]:
    """Group identical errors raised for identical OCR item rows.

    A line error is grouped only when both its error details and its complete
    source-line values match.  Header errors remain distinct.  The returned
    objects retain the original error and include all affected line numbers.
    """
    raw_errors = errors if isinstance(errors, list) else []
    raw_lines = line_items if isinstance(line_items, list) else []
    groups: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}

    for error_index, raw_error in enumerate(raw_errors):
        if not isinstance(raw_error, Mapping):
            continue

        error = dict(raw_error)
        affected_lines = error.get("affected_lines")
        if not isinstance(affected_lines, list):
            affected_lines = []
        if not affected_lines and error.get("line_index") is not None:
            affected_lines = [error["line_index"]]

        normalized_lines: list[int] = []
        signatures: list[str] = []
        for line_index in affected_lines:
            try:
                normalized_index = int(line_index)
            except (TypeError, ValueError):
                continue
            if normalized_index not in normalized_lines:
                normalized_lines.append(normalized_index)
            signatures.append(
                _stable_value(_line_for_index(raw_lines, normalized_index))
            )

        # Only line-level errors can be repeated across OCR rows.  Header
        # errors are keyed by their full payload and keep no line signature.
        grouping_key = {
            "scope": "line" if normalized_lines else "header",
            "error": _error_without_line_references(error),
            "line_values": sorted(signatures) if normalized_lines else [],
        }
        key = _stable_value(grouping_key)
        group = by_key.get(key)

        if group is None:
            group = {
                "error": error,
                "representative_error_index": error_index,
                "error_indexes": [error_index],
                "affected_lines": normalized_lines,
            }
            by_key[key] = group
            groups.append(group)
            continue

        group["error_indexes"].append(error_index)
        for line_index in normalized_lines:
            if line_index not in group["affected_lines"]:
                group["affected_lines"].append(line_index)

    for group in groups:
        group["affected_lines"].sort()
        group["affected_count"] = len(group["affected_lines"])

    return groups
