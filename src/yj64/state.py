"""Manage diagnostic engine lifecycle state."""

from __future__ import annotations

from enum import Enum, auto


class EngineState(Enum):
    INITIALIZING = auto()
    CALIBRATING = auto()
    ACTIVE_PROFILING = auto()
    STOPPED = auto()


class StateMachine:
    """Manage lifecycle transitions for a diagnostic engine."""

    def __init__(self) -> None:
        self._state = EngineState.INITIALIZING

    @property
    def state(self) -> EngineState:
        """Return the current engine state."""
        return self._state

    def calibrate(self) -> None:
        """Transition from initialization to calibration."""
        self._require(EngineState.INITIALIZING)
        self._state = EngineState.CALIBRATING

    def activate(self) -> None:
        """Transition from calibration to active profiling."""
        self._require(EngineState.CALIBRATING)
        self._state = EngineState.ACTIVE_PROFILING

    def stop(self) -> None:
        """Transition the engine to the stopped state."""
        if self._state is not EngineState.STOPPED:
            self._state = EngineState.STOPPED

    def _require(self, expected: EngineState) -> None:
        if self._state is not expected:
            raise RuntimeError(
                f"invalid transition from {self._state.name}; "
                f"expected {expected.name}"
            )
