from __future__ import annotations

from pathlib import Path

import pytest

from yj64.agent_core import DiagnosticEngine
from yj64.config import load_config
from yj64.oasis_adapter import OasisActionEvent, OasisTelemetryAdapter


CONFIG = Path(__file__).parents[1] / "config" / "telemetry.json"


def _adapter() -> OasisTelemetryAdapter:
    return OasisTelemetryAdapter(DiagnosticEngine(load_config(CONFIG)))


def test_oasis_event_is_forwarded_to_diagnostics() -> None:
    result = _adapter().observe(
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
    result = _adapter().observe_mapping(
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


def test_oasis_mapping_rejects_missing_fields() -> None:
    with pytest.raises(ValueError, match="missing OASIS event field"):
        OasisActionEvent.from_mapping(
            {
                "agent_id": "agent-a",
                "action": "create_post",
                "entropy": 0.8,
            }
        )


def test_oasis_event_rejects_empty_identity() -> None:
    with pytest.raises(ValueError, match="agent_id"):
        OasisActionEvent(
            agent_id=" ",
            action="create_post",
            entropy=0.8,
            autonomy=0.9,
        )


def test_oasis_event_rejects_empty_action() -> None:
    with pytest.raises(ValueError, match="action"):
        OasisActionEvent(
            agent_id=1,
            action="",
            entropy=0.8,
            autonomy=0.9,
        )
