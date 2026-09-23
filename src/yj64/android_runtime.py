"""Best-effort Android runtime diagnostics inspired by established ADB tooling.

The collector intentionally uses the system adb executable instead of embedding a
large third-party runtime. This keeps YJ-64 dependency-free while exposing the
same useful diagnostic primitives used by DeepADB and Android-App-Memory-Analysis.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class ProbeResult:
    name: str
    available: bool
    output: str = ""
    error: str = ""


@dataclass(frozen=True)
class AndroidRuntimeSnapshot:
    package: str
    adb_available: bool
    probes: tuple[ProbeResult, ...] = field(default_factory=tuple)


class AndroidRuntimeCollector:
    """Collect non-destructive diagnostics from a connected Android device."""

    def __init__(self, adb_path: str | None = None, timeout: float = 8.0) -> None:
        self.adb_path = adb_path or shutil.which("adb") or ""
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.adb_path)

    def _run(self, name: str, args: Sequence[str]) -> ProbeResult:
        if not self.available:
            return ProbeResult(name=name, available=False, error="adb_not_available")
        try:
            completed = subprocess.run(
                [self.adb_path, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ProbeResult(name=name, available=False, error=str(exc))
        output = completed.stdout.strip()
        error = completed.stderr.strip()
        return ProbeResult(
            name=name,
            available=completed.returncode == 0,
            output=output,
            error=error or (f"exit_code={completed.returncode}" if completed.returncode else ""),
        )

    def snapshot(self, package: str) -> AndroidRuntimeSnapshot:
        if not self.available:
            return AndroidRuntimeSnapshot(
                package=package,
                adb_available=False,
                probes=(ProbeResult("adb", False, error="adb_not_available"),),
            )

        probes = (
            self._run("device_state", ("get-state",)),
            self._run("logcat_crash", ("logcat", "-b", "crash", "-d", "-t", "120")),
            self._run("meminfo", ("shell", "dumpsys", "meminfo", package)),
            self._run("gfxinfo", ("shell", "dumpsys", "gfxinfo", package)),
            self._run("top", ("shell", "top", "-b", "-n", "1", "-m", "20")),
            self._run(
                "app_exit_info",
                ("shell", "dumpsys", "activity", "exit-info", package),
            ),
        )
        return AndroidRuntimeSnapshot(
            package=package,
            adb_available=True,
            probes=probes,
        )
