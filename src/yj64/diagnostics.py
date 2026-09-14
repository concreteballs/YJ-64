"""Generate diagnostic queries from configured templates."""

from __future__ import annotations

import random

from .config import DiagnosticConfig


class DiagnosticQueryGenerator:
    """Select diagnostic queries from configured templates."""

    def __init__(
        self,
        config: DiagnosticConfig,
        rng: random.Random | None = None,
    ) -> None:
        self._queries = config.queries
        self._rng = rng or random.Random()

    def generate(self, state_drift: float = 0.0) -> str:
        """Select a query, prioritizing a deterministic index during drift."""
        if not self._queries:
            raise RuntimeError("no diagnostic queries configured")

        index = int(abs(state_drift) * len(self._queries)) % len(self._queries)
        if state_drift > 0.0:
            return self._queries[index]
        return self._rng.choice(self._queries)
