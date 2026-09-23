from __future__ import annotations

from yj64.android_runtime import AndroidRuntimeCollector


def test_collector_degrades_cleanly_without_adb() -> None:
    collector = AndroidRuntimeCollector(adb_path="")
    snapshot = collector.snapshot("org.blackmirror")

    assert snapshot.package == "org.blackmirror"
    assert snapshot.adb_available is False
    assert snapshot.probes[0].name == "adb"
    assert snapshot.probes[0].error == "adb_not_available"


def test_probe_command_is_non_destructive() -> None:
    collector = AndroidRuntimeCollector(adb_path="/usr/bin/adb")
    result = collector._run("state", ("get-state",))

    assert result.name == "state"
    assert isinstance(result.available, bool)
