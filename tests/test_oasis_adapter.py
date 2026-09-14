from __future__ import annotations

from yj64.agent_core import DiagnosticEngine
from yj64.config import load_config
from yj64.oasis_adapter import OasisActionEvent, OasisTelemetryAdapter


CONFIG = __import__("pathlib").Path(__file__).parents[1] / "config" / "telemetry.json"


def test_oasis_event_is_forwarded_to_diagnostics() -> None:
    adapter = OasisTelemetryAdapter(DiagnosticEngine(load_config(CONFIG)))
    result = adapter.observe(
        OasisActionEvent(
            agent_id=7,
            action="create_post",
            entropy=0.9,
            autonomy=0.95,
        )
    )

    assert result.approved is True
    assert result.node_id == "7"
    assert result.reason == "thresholds_satisfied"


def test_oasis_mapping_preserves_action_boundary() -> None:
    adapter = OasisTelemetryAdapter(DiagnosticEngine(load_config(CONFIG)))
    result = adapter.observe_mapping(
        {
            "agent_id": "agent-a",
            "action": "like_post",
            "entropy": 0.2,
            "autonomy": 0.9,
        }
    )

    assert result.approved is False
    assert result.node_id == "agent-a"
    assert result.reason == "below_configured_thresholds"
