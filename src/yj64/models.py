"""Typed data models for telemetry and validation results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TelemetryPacket:
    """Validated telemetry received from a node."""

    node_id: str
    entropy: float
    autonomy: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "TelemetryPacket":
        """Create a validated packet from a mapping."""
        node_id = payload.get("id")
        entropy = payload.get("entropy")
        autonomy = payload.get("autonomy")

        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("telemetry packet has no valid node id")
        if isinstance(entropy, bool) or isinstance(autonomy, bool):
            raise ValueError("metric values must be numeric")

        try:
            entropy_value = float(entropy)
            autonomy_value = float(autonomy)
        except (TypeError, ValueError) as exc:
            raise ValueError("metric values must be numeric") from exc

        if not 0.0 <= entropy_value <= 1.0:
            raise ValueError("entropy must be within [0, 1]")
        if not 0.0 <= autonomy_value <= 1.0:
            raise ValueError("autonomy must be within [0, 1]")

        return cls(
            node_id=node_id.strip(),
            entropy=entropy_value,
            autonomy=autonomy_value,
        )


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    """Result emitted by the validation stage."""

    node_id: str
    approved: bool
    reason: str
    query: str | None = None
