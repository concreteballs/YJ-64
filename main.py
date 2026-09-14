"""CLI entry point for a local diagnostic verification cycle."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from yj64.agent_core import DiagnosticEngine
from yj64.config import load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def _packets() -> Any:
    for packet in (
        {"id": "node_alpha", "entropy": 0.4, "autonomy": 0.5},
        {"id": "node_omega", "entropy": 0.85, "autonomy": 0.92},
        {"id": "malformed", "entropy": "invalid"},
    ):
        yield packet


async def main() -> None:
    config = load_config(Path("config/telemetry.json"))
    engine = DiagnosticEngine(config)
    results = await engine.run(_packets())
    for result in results:
        print(json.dumps({
            "node_id": result.node_id,
            "approved": result.approved,
            "reason": result.reason,
            "query": result.query,
        }, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
