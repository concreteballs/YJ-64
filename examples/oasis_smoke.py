"""Run a small real OASIS simulation and bridge its trace into YJ-64."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from yj64.agent_core import DiagnosticEngine
from yj64.config import load_config
from yj64.oasis_adapter import OasisActionEvent, OasisTelemetryAdapter


def _read_trace(database_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT user_id, action, info FROM trace ORDER BY created_at"
        ).fetchall()

    return [
        {"agent_id": user_id, "action": action, "info": info}
        for user_id, action, info in rows
    ]


async def _run_oasis(database_path: Path) -> None:
    try:
        import oasis
        from oasis import ActionType, AgentGraph, ManualAction, SocialAgent, UserInfo
    except ImportError as exc:
        raise RuntimeError(
            "OASIS is not installed; use `pip install -e '.[oasis]'`"
        ) from exc

    agent_graph = AgentGraph()
    for agent_id, username in ((0, "yj64_alpha"), (1, "yj64_beta")):
        agent_graph.add_agent(
            SocialAgent(
                agent_id=agent_id,
                user_info=UserInfo(
                    user_name=username,
                    name=username,
                    description="Offline YJ-64 integration test agent",
                    profile=None,
                    recsys_type="reddit",
                ),
                agent_graph=agent_graph,
                model=None,
                available_actions=[ActionType.CREATE_POST],
            )
        )

    env = oasis.make(
        agent_graph=agent_graph,
        platform=oasis.DefaultPlatformType.REDDIT,
        database_path=str(database_path),
    )

    await env.reset()
    try:
        actions = {
            env.agent_graph.get_agent(0): ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": "YJ-64 OASIS integration smoke test."},
            ),
            env.agent_graph.get_agent(1): ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": "Second deterministic simulation event."},
            ),
        }
        await env.step(actions)
    finally:
        await env.close()


def _diagnose_trace(
    trace: list[dict[str, Any]], config_path: Path
) -> list[dict[str, Any]]:
    engine = DiagnosticEngine(load_config(config_path))
    adapter = OasisTelemetryAdapter(engine)

    # Metrics are intentionally supplied by the instrumentation boundary rather
    # than inferred from the social action name. This smoke test uses fixed,
    # explicit observations to exercise the end-to-end bridge deterministically.
    metrics = {0: (0.9, 0.95), 1: (0.2, 0.3)}
    results = []
    for event in trace:
        entropy, autonomy = metrics[int(event["agent_id"])]
        observation = OasisActionEvent(
            agent_id=event["agent_id"],
            action=event["action"],
            entropy=entropy,
            autonomy=autonomy,
        )
        result = adapter.observe(observation)
        results.append(
            {
                "agent_id": event["agent_id"],
                "action": event["action"],
                "approved": result.approved,
                "reason": result.reason,
            }
        )
    return results


def main() -> None:
    config_path = Path(__file__).parents[1] / "config" / "telemetry.json"
    with tempfile.TemporaryDirectory(prefix="yj64-oasis-") as directory:
        database_path = Path(directory) / "oasis_smoke.db"
        asyncio.run(_run_oasis(database_path))
        trace = _read_trace(database_path)
        results = _diagnose_trace(trace, config_path)
        print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
