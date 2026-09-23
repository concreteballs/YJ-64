"""CLI entry point and Android UI for the YJ-64 diagnostic monitor."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Buildozer packages the repository root. The Python package lives in src/.
_SRC_DIR = Path(__file__).resolve().parent / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from yj64.agent_core import DiagnosticEngine
from yj64.android_runtime import AndroidRuntimeCollector
from yj64.config import load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
TARGET_PACKAGE = "org.blackmirror.blackmirror"


async def _packets() -> Any:
    for packet in (
        {"id": "node_alpha", "entropy": 0.4, "autonomy": 0.5},
        {"id": "node_omega", "entropy": 0.85, "autonomy": 0.92},
        {"id": "malformed", "entropy": "invalid"},
    ):
        yield packet


def _write_runtime_evidence() -> None:
    config = json.loads(
        (Path(__file__).resolve().parent / "config/android_runtime.json").read_text(
            encoding="utf-8"
        )
    )
    collector = AndroidRuntimeCollector(timeout=float(config["timeout_seconds"]))
    snapshot = collector.snapshot(str(config["package"]))
    evidence = {
        "package": snapshot.package,
        "adb_available": snapshot.adb_available,
        "probes": [
            {
                "name": probe.name,
                "available": probe.available,
                "output": probe.output,
                "error": probe.error,
            }
            for probe in snapshot.probes
        ],
    }
    output_path = Path(
        os.environ.get(
            "YJ64_RUNTIME_REPORT",
            str(Path(__file__).resolve().parent / "android-runtime.json"),
        )
    )
    output_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )


async def _cli_main() -> None:
    config = load_config(Path("config/telemetry.json"))
    engine = DiagnosticEngine(config)
    results = await engine.run(_packets())
    for result in results:
        print(
            json.dumps(
                {
                    "node_id": result.node_id,
                    "approved": result.approved,
                    "reason": result.reason,
                    "query": result.query,
                },
                sort_keys=True,
            )
        )
    _write_runtime_evidence()


if os.environ.get("ANDROID_ARGUMENT"):
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from jnius import autoclass

    class MonitorApp(App):
        def build(self):
            self.status = Label(
                text="YJ-64: запускается монитор...",
                halign="left",
                valign="top",
            )
            self.status.bind(
                size=lambda instance, value: setattr(instance, "text_size", value)
            )
            root = BoxLayout(orientation="vertical", padding=16, spacing=10)
            root.add_widget(
                Label(
                    text="YJ-64 Monitor\nTarget: " + TARGET_PACKAGE,
                    size_hint_y=None,
                    height=80,
                )
            )
            root.add_widget(self.status)

            open_button = Button(
                text="Открыть доступ к статистике приложений",
                size_hint_y=None,
                height=60,
            )
            open_button.bind(on_release=self.open_usage_settings)
            root.add_widget(open_button)

            start_button = Button(
                text="Запустить монитор",
                size_hint_y=None,
                height=60,
            )
            start_button.bind(on_release=self.start_monitor)
            root.add_widget(start_button)

            stop_button = Button(
                text="Остановить монитор",
                size_hint_y=None,
                height=60,
            )
            stop_button.bind(on_release=self.stop_monitor)
            root.add_widget(stop_button)

            Clock.schedule_once(self.start_monitor, 0)
            Clock.schedule_interval(self.refresh, 1)
            return root

        def open_usage_settings(self, *_):
            Settings = autoclass("android.provider.Settings")
            Intent = autoclass("android.content.Intent")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            activity.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
            self.status.text = "Открой доступ для YJ-64 в настройках Android."

        def start_monitor(self, *_):
            try:
                Service = autoclass("org.blackmirror.yj64monitor.ServiceMonitor")
                activity = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity
                Service.start(activity, "")
                self.status.text = (
                    "Монитор запущен. Теперь можно запускать целевое приложение."
                )
            except Exception as exc:
                self.status.text = (
                    f"Монитор не запустился: {type(exc).__name__}: {exc}"
                )

        def stop_monitor(self, *_):
            try:
                Service = autoclass("org.blackmirror.yj64monitor.ServiceMonitor")
                activity = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity
                Service.stop(activity)
                self.status.text = "Монитор остановлен."
            except Exception as exc:
                self.status.text = (
                    f"Остановка монитора не удалась: {type(exc).__name__}: {exc}"
                )

        def refresh(self, *_):
            report = Path(self.user_data_dir) / "yj64-monitor.jsonl"
            if not report.exists():
                return
            lines = [
                line
                for line in report.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if lines:
                self.status.text = "Последнее событие:\n" + lines[-1]

    MonitorApp().run()
else:
    asyncio.run(_cli_main())
