"""Coordinate telemetry validation and diagnostic processing."""

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
    """Orchestrate telemetry ingestion, validation, and diagnostics."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.state = StateMachine()
        self.telemetry = TelemetryEngine(config.thresholds)
        self.query_generator = DiagnosticQueryGenerator(config.diagnostics)

    def initialize(self) -> None:
        """Initialize the engine state for a validation cycle."""
        self.state.calibrate()
        self.state.activate()

    def validate(self, payload: Mapping[str, Any]) -> DiagnosticResult:
        """Validate one telemetry payload against configured thresholds."""
        packet = self.telemetry.ingest(payload)
        if packet is None:
            return DiagnosticResult(
                node_id="unknown",
                approved=False,
                reason="malformed_or_incomplete_packet",
            )

        if not self.telemetry.evaluate(packet):
            return DiagnosticResult(
                node_id=packet.node_id,
                approved=False,
                reason="below_configured_thresholds",
            )

        return DiagnosticResult(
            node_id=packet.node_id,
            approved=True,
            reason="thresholds_satisfied",
            query=self.query_generator.generate(),
        )

    async def run(
        self, packets: AsyncIterable[Mapping[str, Any]]
    ) -> list[DiagnosticResult]:
        """Process one bounded asynchronous validation cycle."""
        self.initialize()
        results: list[DiagnosticResult] = []
        try:
            async for payload in packets:
                if len(results) >= self.config.validation.max_nodes_per_cycle:
                    break
                try:
                    result = self.validate(payload)
                except Exception:
                    logger.exception("validation cycle failed for telemetry payload")
                    result = DiagnosticResult(
                        node_id="unknown",
                        approved=False,
                        reason="validation_error",
                    )
                results.append(result)
                interval = self.config.validation.interval_seconds
                if interval:
                    await asyncio.sleep(interval)
        finally:
            self.state.stop()
        return results
