"""Configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Thresholds:
    entropy: float
    autonomy: float


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    max_nodes_per_cycle: int
    interval_seconds: float


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    queries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineConfig:
    thresholds: Thresholds
    validation: ValidationConfig
    diagnostics: DiagnosticConfig


def _bounded_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return result


def load_config(path: Path) -> EngineConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    thresholds = raw["thresholds"]
    validation = raw["validation"]
    diagnostics = raw["diagnostics"]
    queries = diagnostics.get("queries", [])
    if not isinstance(queries, list) or not all(isinstance(item, str) and item.strip() for item in queries):
        raise ValueError("diagnostics.queries must be a non-empty list of strings")

    max_nodes = int(validation["max_nodes_per_cycle"])
    if max_nodes < 1:
        raise ValueError("max_nodes_per_cycle must be positive")

    interval = float(validation["interval_seconds"])
    if interval < 0.0:
        raise ValueError("interval_seconds cannot be negative")

    return EngineConfig(
        thresholds=Thresholds(
            entropy=_bounded_float(thresholds["entropy"], "entropy threshold"),
            autonomy=_bounded_float(thresholds["autonomy"], "autonomy threshold"),
        ),
        validation=ValidationConfig(max_nodes, interval),
        diagnostics=DiagnosticConfig(tuple(queries)),
    )
