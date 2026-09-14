"""Explicit diagnostic engine state machine."""

from __future__ import annotations

from enum import Enum, auto


class EngineState(Enum):
    INITIALIZING = auto()
    CALIBRATING = auto()
    ACTIVE_PROFILING = auto()
    STOPPED = auto()


class StateMachine:
    """Small, explicit state machine with guarded transitions."""

    def __init__(self) -> None:
        self._state = EngineState.INITIALIZING

    @property
    def state(self) -> EngineState:
        return self._state

    def calibrate(self) -> None:
        self._require(EngineState.INITIALIZING)
        self._state = EngineState.CALIBRATING

    def activate(self) -> None:
        self._require(EngineState.CALIBRATING)
        self._state = EngineState.ACTIVE_PROFILING

    def stop(self) -> None:
        if self._state is not EngineState.STOPPED:
            self._state = EngineState.STOPPED

    def _require(self, expected: EngineState) -> None:
        if self._state is not expected:
            raise RuntimeError(
                f"invalid transition from {self._state.name}; expected {expected.name}"
            )
