"""
Lightweight execution metrics for the capability pipeline.

Captures timing and outcome data at each pipeline stage without
introducing business logic. Metrics are collected by PipelineMetrics
and reset per-request. The collector is a simple dict-based container
so it can be created and discarded freely without side effects.

No secrets, credentials, or business data are ever stored here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineMetrics:
    """
    Per-request execution metrics for the capability pipeline.

    Each stage records its start/end monotonic timestamps and optional
    outcome data. Durations are computed as properties, not stored, so
    there is a single source of truth.

    Stages
    ------
    planning   : Planner.plan() — LLM-driven tool selection
    execution  : ToolExecutor.execute() — running all selected tools
    validation : ResultValidator.validate_all() — formatting results
    llm        : provider.generate_response() — the final LLM call

    Fields
    ------
    planning_start / planning_end : float | None
    execution_start / execution_end : float | None
    validation_start / validation_end : float | None
    llm_start / llm_end : float | None

    total_tool_count  : int — how many tools the Planner selected
    successful_tools  : int — how many tools completed without error
    failed_tools      : int — how many tools raised / returned error
    fallback_used     : bool — whether the context-driven fallback ran
    """

    planning_start: float | None = None
    planning_end: float | None = None
    execution_start: float | None = None
    execution_end: float | None = None
    validation_start: float | None = None
    validation_end: float | None = None
    llm_start: float | None = None
    llm_end: float | None = None

    total_tool_count: int = 0
    successful_tools: int = 0
    failed_tools: int = 0
    fallback_used: bool = False

    # ----- Timing helpers -----

    def mark_planning_start(self) -> None:
        self.planning_start = time.monotonic()

    def mark_planning_end(self) -> None:
        self.planning_end = time.monotonic()

    def mark_execution_start(self) -> None:
        self.execution_start = time.monotonic()

    def mark_execution_end(self) -> None:
        self.execution_end = time.monotonic()

    def mark_validation_start(self) -> None:
        self.validation_start = time.monotonic()

    def mark_validation_end(self) -> None:
        self.validation_end = time.monotonic()

    def mark_llm_start(self) -> None:
        self.llm_start = time.monotonic()

    def mark_llm_end(self) -> None:
        self.llm_end = time.monotonic()

    # ----- Duration properties (computed) -----

    @property
    def planning_duration_ms(self) -> float | None:
        if self.planning_start is not None and self.planning_end is not None:
            return (self.planning_end - self.planning_start) * 1000
        return None

    @property
    def execution_duration_ms(self) -> float | None:
        if self.execution_start is not None and self.execution_end is not None:
            return (self.execution_end - self.execution_start) * 1000
        return None

    @property
    def validation_duration_ms(self) -> float | None:
        if self.validation_start is not None and self.validation_end is not None:
            return (self.validation_end - self.validation_start) * 1000
        return None

    @property
    def llm_duration_ms(self) -> float | None:
        if self.llm_start is not None and self.llm_end is not None:
            return (self.llm_end - self.llm_start) * 1000
        return None

    @property
    def total_duration_ms(self) -> float | None:
        """Earliest start to latest end across all stages."""
        starts = [v for v in (self.planning_start, self.execution_start,
                              self.validation_start, self.llm_start) if v is not None]
        ends = [v for v in (self.planning_end, self.execution_end,
                            self.validation_end, self.llm_end) if v is not None]
        if starts and ends:
            return (max(ends) - min(starts)) * 1000
        return None

    # ----- Serialisation -----

    def to_dict(self) -> dict[str, Any]:
        """Flat dict for structured logging. Omits None durations."""
        d: dict[str, Any] = {
            "total_tool_count": self.total_tool_count,
            "successful_tools": self.successful_tools,
            "failed_tools": self.failed_tools,
            "fallback_used": self.fallback_used,
        }
        for name, prop in (
            ("planning_duration_ms", self.planning_duration_ms),
            ("execution_duration_ms", self.execution_duration_ms),
            ("validation_duration_ms", self.validation_duration_ms),
            ("llm_duration_ms", self.llm_duration_ms),
            ("total_duration_ms", self.total_duration_ms),
        ):
            if prop is not None:
                d[name] = round(prop, 2)
        return d
