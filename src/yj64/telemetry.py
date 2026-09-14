"""Telemetry ingestion and metric evaluation."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from .config import Thresholds
from .models import TelemetryPacket

logger = logging.getLogger(__name__)


class TelemetryEngine:
    """Validate packets and evaluate them against configured thresholds."""

    def __init__(self, thresholds: Thresholds) -> None:
        self._thresholds = thresholds

    def ingest(self, payload: Mapping[str, Any]) -> TelemetryPacket | None:
        try:
            return TelemetryPacket.from_mapping(payload)
        except (TypeError, ValueError, OverflowError) as exc:
            logger.warning("telemetry packet rejected: %s", exc)
            return None

    def evaluate(self, packet: TelemetryPacket) -> bool:
        return (
            packet.entropy > self._thresholds.entropy
            and packet.autonomy > self._thresholds.autonomy
        )

    def ingest_many(self, payloads: Iterable[Mapping[str, Any]]) -> list[TelemetryPacket]:
        valid_packets: list[TelemetryPacket] = []
        for payload in payloads:
            packet = self.ingest(payload)
            if packet is not None:
                valid_packets.append(packet)
        return valid_packets
