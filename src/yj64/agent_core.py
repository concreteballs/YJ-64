"""Application orchestration for the telemetry diagnostic engine."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable, Mapping
from typing import Any

from .config import EngineConfig
from .diagnostics import DiagnosticQueryGenerator
from .models import DiagnosticResult
from .state import StateMachine
from .telemetry import TelemetryEngine

logger = logging.getLogger(__name__)


class DiagnosticEngine:
    """Coordinate ingestion, state transitions, validation, and diagnostics."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.state = StateMachine()
        self.telemetry = TelemetryEngine(config.thresholds)
        self.query_generator = DiagnosticQueryGenerator(config.diagnostics)

    def initialize(self) -> None:
        self.state.calibrate()
        self.state.activate()

    def validate(self, payload: Mapping[str, Any]) -> DiagnosticResult:
        packet = self.telemetry.ingest(payload)
        if packet is None:
            return DiagnosticResult(
                node_id="unknown",
                approved=False,
                reason="malformed_or_incomplete_packet",
            )
        approved = self.telemetry.evaluate(packet)
        if not approved:
            return DiagnosticResult(
                node_id=packet.node_id,
                approved=False,
                reason="below_configured_thresholds",
            )
        query = self.query_generator.generate()
        return DiagnosticResult(
            node_id=packet.node_id,
            approved=True,
            reason="thresholds_satisfied",
            query=query,
        )

    async def run(self, packets: AsyncIterable[Mapping[str, Any]]) -> list[DiagnosticResult]:
        """Run one bounded asynchronous validation cycle."""
        self.initialize()
        results: list[DiagnosticResult] = []
        try:
            async for payload in packets:
                if len(results) >= self.config.validation.max_nodes_per_cycle:
                    break
                try:
                    result = self.validate(payload)
                except Exception:
                    logger.exception("diagnostic validation failed")
                    result = DiagnosticResult(
                        node_id="unknown",
                        approved=False,
                        reason="validation_error",
                    )
                results.append(result)
                if self.config.validation.interval_seconds:
                    await asyncio.sleep(self.config.validation.interval_seconds)
        finally:
            self.state.stop()
        return results
