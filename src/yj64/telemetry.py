"""Ingest telemetry and evaluate configured metrics."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from .config import Thresholds
from .models import TelemetryPacket

logger = logging.getLogger(__name__)


class TelemetryEngine:
    """Validate telemetry packets and evaluate configured thresholds."""

    def __init__(self, thresholds: Thresholds) -> None:
        self._thresholds = thresholds

    def ingest(self, payload: Mapping[str, Any]) -> TelemetryPacket | None:
        """Parse and validate one telemetry payload."""
        try:
            return TelemetryPacket.from_mapping(payload)
        except (TypeError, ValueError, OverflowError) as exc:
            logger.warning("telemetry packet rejected: %s", exc)
            return None

    def evaluate(self, packet: TelemetryPacket) -> bool:
        """Return whether a packet satisfies the configured thresholds."""
        return (
            packet.entropy > self._thresholds.entropy
            and packet.autonomy > self._thresholds.autonomy
        )

    def ingest_many(
        self, payloads: Iterable[Mapping[str, Any]]
    ) -> list[TelemetryPacket]:
        """Parse all valid packets from an iterable of payloads."""
        valid_packets: list[TelemetryPacket] = []
        for payload in payloads:
            packet = self.ingest(payload)
            if packet is not None:
                valid_packets.append(packet)
        return valid_packets
