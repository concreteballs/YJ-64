"""CLI entry point and Android UI for the YJ-64 diagnostic monitor."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import time
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
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9333
BRIDGE_TOKEN = "yj64-dev-bridge-v1"
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9333
BRIDGE_TOKEN = "yj64-dev-bridge-v1"


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
    from kivy.core.clipboard import Clipboard
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

            self._showing_service_log = False
            self._monitor_active = True

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

            copy_button = Button(
                text="Скопировать весь отчёт",
                size_hint_y=None,
                height=60,
            )
            copy_button.bind(on_release=self.copy_report)
            root.add_widget(copy_button)

            clear_report_button = Button(
                text="Сбросить предыдущий отчёт",
                size_hint_y=None,
                height=60,
            )
            clear_report_button.bind(on_release=self.clear_report)
            root.add_widget(clear_report_button)

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

        def capture_target_runtime_snapshot(self, package_manager):
            """Capture live target process state and the newest recorded exit on every manual diagnostic press."""
            ActivityManager = autoclass("android.app.ActivityManager")
            ApplicationExitInfo = autoclass("android.app.ApplicationExitInfo")
            snapshot = {
                "source": "monitor_ui",
                "event": "target_runtime_snapshot",
                "target_package": TARGET_PACKAGE,
                "captured_at_ms": int(time.time() * 1000),
            }
            try:
                target_uid = int(
                    package_manager.getApplicationInfo(TARGET_PACKAGE, 0).uid
                )
                snapshot["target_uid"] = target_uid
                activity_manager = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity.getSystemService("activity")
                processes = activity_manager.getRunningAppProcesses() or []
                matching = [
                    {
                        "pid": int(process.pid),
                        "process_name": str(process.processName or ""),
                        "uid": int(process.uid),
                        "importance": int(process.importance),
                        "importance_reason_code": int(process.importanceReasonCode),
                        "importance_reason_pid": int(process.importanceReasonPid),
                    }
                    for process in processes
                    if int(process.uid) == target_uid
                ]
                snapshot["process_count"] = len(matching)
                snapshot["processes"] = matching
                # Android restricts cross-application process visibility on modern
                # releases. An empty filtered list therefore cannot be treated as
                # proof that the target is dead.
                snapshot["process_state"] = (
                    "visible_running"
                    if matching
                    else "not_observable_via_cross_app_process_list"
                )
                snapshot["process_visibility_limit"] = (
                    "target_is_a_different_application_uid"
                )
            except Exception as exc:
                snapshot["process_state"] = "inspection_failed"
                snapshot["process_error_type"] = type(exc).__name__
                snapshot["process_error"] = str(exc)

            try:
                application_info = package_manager.getApplicationInfo(
                    TARGET_PACKAGE, 0
                )
                stopped_flag = int(
                    getattr(application_info, "FLAG_STOPPED", 2097152)
                )
                app_flags = int(application_info.flags)
                snapshot["package_state"] = {
                    "application_flags": app_flags,
                    "stopped": bool(app_flags & stopped_flag),
                    "enabled": bool(application_info.enabled),
                    "installed": bool(
                        app_flags
                        & int(getattr(application_info, "FLAG_INSTALLED", 8388608))
                    ),
                    "suspended": bool(
                        app_flags
                        & int(getattr(application_info, "FLAG_SUSPENDED", 1073741824))
                    ),
                }
            except Exception as exc:
                snapshot["package_state_error_type"] = type(exc).__name__
                snapshot["package_state_error"] = str(exc)

            try:
                activity_manager = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity.getSystemService("activity")
                history = activity_manager.getHistoricalProcessExitReasons(
                    TARGET_PACKAGE, 0, 10
                )
                snapshot["exit_history_count"] = len(history)
                if history:
                    latest = history[0]
                    reason = int(latest.getReason())
                    snapshot["latest_exit"] = {
                        "timestamp_ms": int(latest.getTimestamp()),
                        "reason": reason,
                        "reason_name": str(
                            ApplicationExitInfo.reasonToString(reason)
                        ),
                        "status": int(latest.getStatus()),
                        "pid": int(latest.getPid()),
                        "process_name": str(latest.getProcessName() or ""),
                        "importance": int(latest.getImportance()),
                        "description": str(latest.getDescription() or ""),
                        "package_uid": int(latest.getPackageUid()),
                    }
                else:
                    snapshot["latest_exit"] = None
            except Exception as exc:
                snapshot["exit_query_error_type"] = type(exc).__name__
                snapshot["exit_query_error"] = str(exc)

            self._append_local_report(snapshot)
            return snapshot

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
            diagnostics["runtime_snapshot"] = self.capture_target_runtime_snapshot(
                package_manager
            )

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
            """Request the Base application's service log through the diagnostic bridge."""
            self._showing_service_log = True
            command_id = f"UI-{time.monotonic_ns()}"
            self.status.text = "Запрашиваю service log Base..."
            try:
                payload = {"token": BRIDGE_TOKEN, "ui_request": "GET_BASE_SERVICE_LOG", "message_id": command_id}
                with socket.create_connection((BRIDGE_HOST, BRIDGE_PORT), timeout=5.0) as connection:
                    connection.sendall((json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))
                    connection.settimeout(5.0)
                    raw = connection.recv(262144).decode("utf-8", errors="replace").strip()
                if not raw: raise RuntimeError("monitor service returned an empty response")
                response = json.loads(raw)
                if response.get("ok") is not True: raise RuntimeError(f"bridge request failed: {response.get('error', 'unknown_error')}")
                report = response.get("report")
                if not isinstance(report, dict): raise RuntimeError("bridge response does not contain a report")
                data = report.get("data")
                if not isinstance(data, dict): raise RuntimeError("Base response does not contain report data")
                lines = data.get("primary_log_lines", [])
                path_text = str(data.get("primary_log_path", "не определён"))
                line_count = int(data.get("primary_log_line_count", 0))
                truncated = bool(data.get("primary_log_truncated", False))
                fault_report = data.get("fault_report")
                if not data.get("primary_log_exists"):
                    text = "BASE SERVICE LOG: ФАЙЛ НЕ НАЙДЕН\nПуть, который проверил Base:\n" + path_text
                elif not lines:
                    text = "BASE SERVICE LOG: ФАЙЛ НАЙДЕН, НО ПУСТ\nПуть:\n" + path_text + f"\nСтрок в файле: {line_count}"
                else:
                    text = "BASE SERVICE LOG\nИсточник: " + path_text + f"\nСтрок в файле: {line_count}" + ("\nПоказана последняя часть файла." if truncated else "") + "\n\n" + "\n".join(str(line) for line in lines)
                if fault_report is not None:
                    text += "\n\n===== PERSISTED FAULT REPORT =====\n" + json.dumps(fault_report, indent=2, sort_keys=True, ensure_ascii=False)
                self.report_view.text = text
                self.status.text = "Service log Base получен через bridge."
                self._append_local_report({"source":"monitor_ui","event":"base_service_log_received","command_id":command_id,"report_id":report.get("report_id"),"primary_log_path":path_text,"primary_log_line_count":line_count,"primary_log_truncated":truncated})
            except Exception as exc:
                self.report_view.text = "BASE SERVICE LOG: НЕ УДАЛОСЬ ПОЛУЧИТЬ\n\n" + f"Причина: {type(exc).__name__}: {exc}"
                self.status.text = "Service log Base: ошибка запроса: " + f"{type(exc).__name__}: {exc}"

        def stop_monitor(self, *_):
            try:
                Service = autoclass("org.blackmirror.yj64monitor.ServiceMonitor")
                activity = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity
                Service.stop(activity)
                self._monitor_active = False
                self._showing_service_log = False
                self.status.text = "Монитор остановлен. Автообновление отчёта отключено."
            except Exception as exc:
                self.status.text = (
                    f"Остановка монитора не удалась: {type(exc).__name__}: {exc}"
                )

        def copy_report(self, *_):
            try:
                report = Path(self.user_data_dir) / "yj64-monitor.jsonl"
                text = report.read_text(encoding="utf-8") if report.exists() else self.report_view.text
                Clipboard.copy(text)
                self.status.text = "Весь текущий отчёт скопирован в буфер обмена."
            except OSError as exc:
                self.status.text = f"Копирование не удалось: {type(exc).__name__}: {exc}"

        def clear_report(self, *_):
            report = Path(self.user_data_dir) / "yj64-monitor.jsonl"
            try:
                report.write_text("", encoding="utf-8")
                self._showing_service_log = False
                self.report_view.text = (
                    "Предыдущий отчёт сброшен. Ожидание новых событий..."
                )
                self.status.text = "Предыдущий отчёт очищен."
            except OSError as exc:
                self.status.text = (
                    f"Не удалось сбросить отчёт: {type(exc).__name__}: {exc}"
                )

        def refresh(self, *_):
            if not getattr(self, "_monitor_active", True):
                return
            if getattr(self, "_showing_service_log", False):
                return
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
