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
TARGET_LABEL = "YJ-64 Fault Injection"


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
    from kivy.uix.textinput import TextInput
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
                    text=(
                        "YJ-64 Monitor\n"
                        f"Target: {TARGET_LABEL}\n"
                        f"Package: {TARGET_PACKAGE}"
                    ),
                    size_hint_y=None,
                    height=110,
                )
            )
            root.add_widget(self.status)

            self.report_view = TextInput(
                text="Отчёт мониторинга появится здесь.",
                readonly=True,
                multiline=True,
                font_size=14,
                size_hint_y=1,
            )
            root.add_widget(self.report_view)

            start_button = Button(
                text="Запустить монитор",
                size_hint_y=None,
                height=60,
            )
            start_button.bind(on_release=self.start_monitor)
            root.add_widget(start_button)

            package_diag_button = Button(
                text="Диагностика пакетов YJ-64",
                size_hint_y=None,
                height=60,
            )
            package_diag_button.bind(on_release=self.diagnose_yj64_packages)
            root.add_widget(package_diag_button)

            service_log_button = Button(
                text="Показать service log",
                size_hint_y=None,
                height=60,
            )
            service_log_button.bind(on_release=self.show_service_log)
            root.add_widget(service_log_button)

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

        def start_monitor(self, *_):
            try:
                Service = autoclass("org.blackmirror.yj64monitor.ServiceMonitor")
                activity = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity
                Service.start(activity, "")
                self.status.text = "Монитор запущен."
                self._append_local_report(
                    {
                        "source": "monitor_ui",
                        "event": "monitor_start_confirmed",
                        "message": "Foreground monitor service started.",
                    }
                )
            except Exception as exc:
                self.status.text = (
                    f"Монитор не запустился: {type(exc).__name__}: {exc}"
                )

        def _append_local_report(self, payload):
            report = Path(self.user_data_dir) / "yj64-monitor.jsonl"
            try:
                with report.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, sort_keys=True) + "\n")
            except OSError as exc:
                self.status.text = (
                    f"Не удалось записать отчёт запуска: {type(exc).__name__}: {exc}"
                )

        def diagnose_target_package(self, package_manager):
            """Report PackageManager visibility and launcher activities for TARGET."""
            PackageManager = autoclass("android.content.pm.PackageManager")
            diagnostics = {
                "source": "monitor_ui",
                "event": "target_package_diagnostics",
                "target_package": TARGET_PACKAGE,
            }
            try:
                context = autoclass("org.kivy.android.PythonActivity").mActivity
                source_package = str(context.getPackageName())
                diagnostics["can_package_query_source_package"] = source_package
                diagnostics["can_package_query"] = bool(
                    package_manager.canPackageQuery(
                        source_package,
                        TARGET_PACKAGE,
                    )
                )
            except Exception as exc:
                diagnostics["can_package_query"] = None
                diagnostics["can_package_query_error_type"] = type(exc).__name__
                diagnostics["can_package_query_error"] = str(exc)

            try:
                package_manager.getApplicationInfo(TARGET_PACKAGE, 0)
                diagnostics["package_visible"] = True
            except Exception as exc:
                diagnostics["package_visible"] = False
                diagnostics["package_visibility_error_type"] = type(exc).__name__
                diagnostics["package_visibility_error"] = str(exc)
                return diagnostics

            try:
                package_info = package_manager.getPackageInfo(
                    TARGET_PACKAGE, PackageManager.GET_ACTIVITIES
                )
                activities = package_info.activities or []
                diagnostics["activity_count"] = len(activities)
                diagnostics["activities"] = [
                    {
                        "name": str(info.name),
                        "enabled": bool(info.enabled),
                        "exported": bool(info.exported),
                        "permission": str(info.permission or ""),
                    }
                    for info in activities
                ]
            except Exception as exc:
                diagnostics["activity_query_error_type"] = type(exc).__name__
                diagnostics["activity_query_error"] = str(exc)

            try:
                Intent = autoclass("android.content.Intent")
                launcher_intent = Intent(Intent.ACTION_MAIN)
                launcher_intent.addCategory(Intent.CATEGORY_LAUNCHER)
                launcher_intent.setPackage(TARGET_PACKAGE)
                matches = package_manager.queryIntentActivities(
                    launcher_intent, PackageManager.MATCH_ALL
                )
                diagnostics["launcher_activity_count"] = len(matches)
                diagnostics["launcher_activities"] = [
                    {
                        "package": str(resolve.activityInfo.packageName),
                        "name": str(resolve.activityInfo.name),
                        "enabled": bool(resolve.activityInfo.enabled),
                        "exported": bool(resolve.activityInfo.exported),
                    }
                    for resolve in matches
                ]
            except Exception as exc:
                diagnostics["launcher_query_error_type"] = type(exc).__name__
                diagnostics["launcher_query_error"] = str(exc)

            try:
                diagnostics["launch_intent_available"] = (
                    package_manager.getLaunchIntentForPackage(TARGET_PACKAGE) is not None
                )
            except Exception as exc:
                diagnostics["launch_intent_query_error_type"] = type(exc).__name__
                diagnostics["launch_intent_query_error"] = str(exc)
            return diagnostics

        def diagnose_yj64_packages(self, *_):
            """Diagnose the target by package identity, labels, and launcher visibility without launching it."""
            PackageManager = autoclass("android.content.pm.PackageManager")
            Intent = autoclass("android.content.Intent")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            package_manager = activity.getPackageManager()
            search_terms = ("yj-64", "fault injection", "blackmirror")
            diagnostics = {
                "source": "monitor_ui",
                "event": "yj64_package_diagnostics_started",
                "target_package": TARGET_PACKAGE,
                "target_label": TARGET_LABEL,
                "search_terms": list(search_terms),
                "target_launch_attempted": False,
            }

            target_details = self.diagnose_target_package(package_manager)
            diagnostics["target_package_diagnostics"] = target_details

            matches = []
            try:
                applications = package_manager.getInstalledApplications(
                    PackageManager.MATCH_ALL
                )
                for application in applications:
                    package_name = str(application.packageName or "")
                    try:
                        label = str(application.loadLabel(package_manager) or "")
                    except Exception:
                        label = ""
                    haystack = f"{package_name} {label}".lower()
                    matched_terms = [
                        term for term in search_terms if term in haystack
                    ]
                    if matched_terms:
                        matches.append(
                            {
                                "package": package_name,
                                "label": label,
                                "matched_terms": matched_terms,
                            }
                        )
                diagnostics["installed_application_query"] = "success"
                diagnostics["matching_application_count"] = len(matches)
                diagnostics["matching_applications"] = matches
            except Exception as exc:
                diagnostics["installed_application_query"] = "failed"
                diagnostics["installed_application_query_error_type"] = type(exc).__name__
                diagnostics["installed_application_query_error"] = str(exc)

            try:
                installed_packages = package_manager.getInstalledPackages(
                    PackageManager.MATCH_ALL
                )
                target_package_entries = [
                    {
                        "package": str(info.packageName),
                        "version_name": str(info.versionName or ""),
                        "version_code": int(info.longVersionCode),
                    }
                    for info in installed_packages
                    if str(info.packageName) == TARGET_PACKAGE
                ]
                visible_matching_packages = []
                for info in installed_packages:
                    package_name = str(info.packageName or "")
                    if any(term in package_name.lower() for term in search_terms):
                        visible_matching_packages.append(
                            {
                                "package": package_name,
                                "version_name": str(info.versionName or ""),
                                "version_code": int(info.longVersionCode),
                            }
                        )
                diagnostics["installed_package_query"] = "success"
                diagnostics["target_in_installed_packages"] = bool(
                    target_package_entries
                )
                diagnostics["target_installed_package_entries"] = target_package_entries
                diagnostics["visible_matching_packages"] = visible_matching_packages
            except Exception as exc:
                diagnostics["installed_package_query"] = "failed"
                diagnostics["target_in_installed_packages"] = False
                diagnostics["installed_package_query_error_type"] = type(exc).__name__
                diagnostics["installed_package_query_error"] = str(exc)

            launcher_apps = []
            try:
                launcher_intent = Intent(Intent.ACTION_MAIN)
                launcher_intent.addCategory(Intent.CATEGORY_LAUNCHER)
                launcher_matches = package_manager.queryIntentActivities(
                    launcher_intent, PackageManager.MATCH_ALL
                )
                for resolve in launcher_matches:
                    package_name = str(resolve.activityInfo.packageName or "")
                    try:
                        label = str(
                            resolve.activityInfo.applicationInfo.loadLabel(
                                package_manager
                            )
                            or ""
                        )
                    except Exception:
                        label = ""
                    haystack = f"{package_name} {label}".lower()
                    matched_terms = [
                        term for term in search_terms if term in haystack
                    ]
                    if matched_terms:
                        launcher_apps.append(
                            {
                                "package": package_name,
                                "label": label,
                                "activity": str(resolve.activityInfo.name),
                                "matched_terms": matched_terms,
                            }
                        )
                diagnostics["launcher_query"] = "success"
                diagnostics["matching_launcher_count"] = len(launcher_apps)
                diagnostics["matching_launcher_activities"] = launcher_apps
            except Exception as exc:
                diagnostics["launcher_query"] = "failed"
                diagnostics["launcher_query_error_type"] = type(exc).__name__
                diagnostics["launcher_query_error"] = str(exc)

            diagnostics["interpretation"] = {
                "target_package_visible": target_details.get("package_visible"),
                "visible_matching_package_names": [
                    item.get("package")
                    for item in diagnostics.get("visible_matching_packages", [])
                ],
                "target_launch_intent_available": target_details.get(
                    "launch_intent_available"
                ),
                "target_identity_found_in_installed_applications": any(
                    item.get("package") == TARGET_PACKAGE for item in matches
                ),
                "target_identity_found_in_launcher": any(
                    item.get("package") == TARGET_PACKAGE for item in launcher_apps
                ),
            }
            self._append_local_report(diagnostics)
            self.status.text = (
                "Расширенная диагностика пакетов завершена. "
                "Запуск Fault Injection не выполнялся."
            )

        def show_service_log(self, *_):
            """Load the foreground-service diagnostic log into the UI."""
            try:
                service_report = Path(self.user_data_dir) / "yj64-service-monitor.jsonl"
                if not service_report.exists():
                    self.report_view.text = "Service log пока не создан."
                    self.status.text = "Service log отсутствует."
                    return
                lines = [
                    line
                    for line in service_report.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.report_view.text = "\n".join(lines[-200:])
                self.status.text = (
                    "Показан service log: {} событий."
                    .format(len(lines))
                )
            except OSError as exc:
                self.status.text = (
                    f"Не удалось прочитать service log: {type(exc).__name__}: {exc}"
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
                self.report_view.text = "\n".join(lines[-50:])
                self.status.text = (
                    "Получено отчётов: {}\nПоследнее событие получено."
                    .format(len(lines))
                )

    MonitorApp().run()
else:
    asyncio.run(_cli_main())
