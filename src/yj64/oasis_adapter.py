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

    def __post_init__(self) -> None:
        if isinstance(self.agent_id, bool) or not str(self.agent_id).strip():
            raise ValueError("agent_id must be a non-empty identifier")
        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must be a non-empty string")

    @classmethod
    def from_mapping(cls, event: Mapping[str, Any]) -> "OasisActionEvent":
        """Build an event from an OASIS-shaped mapping."""
        try:
            return cls(
                agent_id=event["agent_id"],
                action=event["action"],
                entropy=float(event["entropy"]),
                autonomy=float(event["autonomy"]),
            )
        except KeyError as exc:
            raise ValueError(f"missing OASIS event field: {exc.args[0]}") from exc
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid OASIS event field") from exc

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
        """Validate an iterable of OASIS observations."""
        return [self.observe(event) for event in events]

    def observe_mapping(self, event: Mapping[str, Any]) -> DiagnosticResult:
        """Normalize and validate an OASIS event mapping."""
        return self.observe(OasisActionEvent.from_mapping(event))
