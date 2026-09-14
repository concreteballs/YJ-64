"""Adapter for feeding OASIS social-simulation events into YJ-64."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .agent_core import DiagnosticEngine
from .models import DiagnosticResult


@dataclass(frozen=True, slots=True)
class OasisActionEvent:
    """Normalized observation emitted by an OASIS simulation."""

    agent_id: int | str
    action: str
    entropy: float
    autonomy: float

    def to_payload(self) -> dict[str, Any]:
        """Convert the event into the telemetry schema consumed by YJ-64."""
        return {
            "id": str(self.agent_id),
            "entropy": self.entropy,
            "autonomy": self.autonomy,
        }


class OasisTelemetryAdapter:
    """Bridge normalized OASIS observations to the YJ-64 diagnostic engine.

    The adapter deliberately does not invent entropy or autonomy scores from
    social actions. The simulation/instrumentation layer supplies those
    metrics, while this class remains responsible only for normalization and
    diagnostic validation.
    """

    def __init__(self, engine: DiagnosticEngine) -> None:
        self._engine = engine

    def observe(self, event: OasisActionEvent) -> DiagnosticResult:
        """Validate one normalized OASIS event."""
        return self._engine.validate(event.to_payload())

    def observe_many(
        self, events: Iterable[OasisActionEvent]
    ) -> list[DiagnosticResult]:
        """Validate a bounded iterable of OASIS observations."""
        return [self.observe(event) for event in events]

    def observe_mapping(self, event: Mapping[str, Any]) -> DiagnosticResult:
        """Validate a mapping with OASIS event fields."""
        normalized = OasisActionEvent(
            agent_id=event["agent_id"],
            action=str(event["action"]),
            entropy=float(event["entropy"]),
            autonomy=float(event["autonomy"]),
        )
        return self.observe(normalized)
