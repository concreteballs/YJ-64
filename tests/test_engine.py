from __future__ import annotations

import asyncio
import json
from pathlib import Path

from yj64.agent_core import DiagnosticEngine
from yj64.config import load_config
from yj64.models import TelemetryPacket
from yj64.state import EngineState, StateMachine


CONFIG = Path(__file__).parents[1] / "config" / "telemetry.json"


def test_packet_validation_and_bounds() -> None:
    packet = TelemetryPacket.from_mapping(
        {"id": "n1", "entropy": 0.8, "autonomy": 0.9}
    )
    assert packet.node_id == "n1"
    assert TelemetryPacket.from_mapping


def test_malformed_packet_is_rejected() -> None:
    config = load_config(CONFIG)
    engine = DiagnosticEngine(config)
    result = engine.validate({"id": "n1", "entropy": "bad"})
    assert result.approved is False
    assert result.reason == "malformed_or_incomplete_packet"


def test_threshold_filtering() -> None:
    engine = DiagnosticEngine(load_config(CONFIG))
    assert engine.validate({"id": "low", "entropy": 0.7, "autonomy": 0.9}).approved is False
    assert engine.validate({"id": "high", "entropy": 0.71, "autonomy": 0.81}).approved is True


def test_state_machine() -> None:
    machine = StateMachine()
    assert machine.state is EngineState.INITIALIZING
    machine.calibrate()
    machine.activate()
    assert machine.state is EngineState.ACTIVE_PROFILING
    machine.stop()
    assert machine.state is EngineState.STOPPED


def test_async_cycle_is_bounded() -> None:
    config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
    config_data["validation"]["max_nodes_per_cycle"] = 1
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
        json.dump(config_data, handle)
        handle.flush()
        engine = DiagnosticEngine(load_config(Path(handle.name)))

        async def packets():
            yield {"id": "n1", "entropy": 0.9, "autonomy": 0.9}
            yield {"id": "n2", "entropy": 0.9, "autonomy": 0.9}

        results = asyncio.run(engine.run(packets()))
        assert len(results) == 1
