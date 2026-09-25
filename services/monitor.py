"""YJ-64 Android foreground monitor service."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

from jnius import autoclass


TARGET = os.environ.get("YJ64_TARGET_PACKAGE", "org.blackmirror.blackmirror")
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = int(os.environ.get("YJ64_BRIDGE_PORT", "9333"))
BRIDGE_TOKEN = os.environ.get("YJ64_BRIDGE_TOKEN", "yj64-dev-bridge-v1")
BRIDGE_SCHEMA = "yj64.diagnostic.v1"

PythonService = autoclass("org.kivy.android.PythonService")
service = PythonService.mService
service.setAutoRestartService(True)

report_path = os.environ.get("YJ64_MONITOR_REPORT")
if report_path:
    REPORT = Path(report_path)
else:
    REPORT = Path(str(service.getFilesDir())) / "yj64-service-monitor.jsonl"

REPORT.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(payload: dict[str, Any]) -> None:
    with REPORT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def write_event(event: str, **details: Any) -> None:
    write_jsonl(
        {
            "source": "external_monitor",
            "event": event,
            "timestamp_ms": int(time.time() * 1000),
            **details,
        }
    )


def inspect_target_exit() -> None:
    try:
        ApplicationExitInfo = autoclass("android.app.ApplicationExitInfo")
        manager = service.getSystemService("activity")
        history = manager.getHistoricalProcessExitReasons(TARGET, 0, 10)
        if not history:
            write_event(
                "target_exit_poll_empty",
                target_package=TARGET,
            )
            return

        latest = history[0]
        timestamp = int(latest.getTimestamp())
        reason = int(latest.getReason())
        reason_names = {
            0: "UNKNOWN",
            1: "EXIT_SELF",
            2: "SIGNALED",
            3: "LOW_MEMORY",
            4: "CRASH",
            5: "CRASH_NATIVE",
            6: "ANR",
            7: "INITIALIZATION_FAILURE",
            8: "PERMISSION_CHANGE",
            9: "EXCESSIVE_RESOURCE_USAGE",
            10: "USER_REQUESTED",
            11: "USER_STOPPED",
            12: "DEPENDENCY_DIED",
            13: "OTHER",
            14: "FREEZER",
            15: "PACKAGE_STATE_CHANGE",
            16: "PACKAGE_UPDATED",
            17: "MEMORY_LIMITER",
            18: "ANOMALY",
        }
        write_event(
            "target_exit_poll",
            target_package=TARGET,
            history_count=len(history),
            latest_timestamp_ms=timestamp,
            latest_reason=reason,
            latest_reason_name=reason_names.get(reason, "UNKNOWN"),
            latest_status=int(latest.getStatus()),
            latest_pid=int(latest.getPid()),
            latest_process_name=str(latest.getProcessName() or ""),
            latest_importance=int(latest.getImportance()),
            latest_description=str(latest.getDescription() or ""),
            latest_package_uid=int(latest.getPackageUid()),
        )
        key = (timestamp, reason)
        if getattr(inspect_target_exit, "_last_key", None) == key:
            return
        inspect_target_exit._last_key = key
        write_event(
            "target_process_exit_observed",
            target_package=TARGET,
            exit_reason=reason,
            exit_reason_name=str(ApplicationExitInfo.reasonToString(reason)),
            target_exit_timestamp_ms=timestamp,
        )
        try:
            Intent = autoclass("android.content.Intent")
            intent = service.getPackageManager().getLaunchIntentForPackage(
                service.getPackageName()
            )
            if intent is None:
                raise RuntimeError("monitor launch intent unavailable")
            intent.addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_CLEAR_TOP
            )
            service.startActivity(intent)
            write_event("monitor_foreground_return_requested")
        except Exception as exc:
            write_event(
                "monitor_foreground_return_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
    except Exception as exc:
        write_event(
            "target_exit_diagnostic_failed",
            target_package=TARGET,
            error_type=type(exc).__name__,
            error=str(exc),
        )


def handle_bridge_connection(connection: socket.socket) -> None:
    try:
        connection.settimeout(2.0)
        raw = connection.recv(65536).decode("utf-8", errors="replace").strip()
        envelope = json.loads(raw)
        if envelope.get("token") != BRIDGE_TOKEN:
            connection.sendall(b'{"ok":false,"error":"invalid_token"}\n')
            return

        report = envelope.get("report")
        if not isinstance(report, dict):
            connection.sendall(b'{"ok":false,"error":"invalid_report"}\n')
            return
        if report.get("schema") != BRIDGE_SCHEMA:
            connection.sendall(b'{"ok":false,"error":"unsupported_schema"}\n')
            return

        write_jsonl(
            {
                "source": "internal_diagnostic_agent",
                "bridge_received": True,
                "received_at_ms": int(time.time() * 1000),
                "report": report,
            }
        )
        ack = {
            "ok": True,
            "report_id": report.get("report_id"),
        }
        connection.sendall((json.dumps(ack) + "\n").encode("utf-8"))
    except (OSError, ValueError, TypeError):
        try:
            connection.sendall(b'{"ok":false,"error":"malformed_message"}\n')
        except OSError:
            pass
    finally:
        try:
            connection.close()
        except OSError:
            pass


def bridge_server() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((BRIDGE_HOST, BRIDGE_PORT))
    server.listen(4)
    while True:
        connection, _ = server.accept()
        threading.Thread(
            target=handle_bridge_connection,
            args=(connection,),
            daemon=True,
        ).start()


write_event(
    "monitor_started",
    target_package=TARGET,
    bridge_host=BRIDGE_HOST,
    bridge_port=BRIDGE_PORT,
    service_mode="foreground_sticky",
)

try:
    ApplicationExitInfo = autoclass("android.app.ApplicationExitInfo")
    write_event(
        "target_exit_diagnostics_available",
        api_level=int(service.getApplicationInfo().targetSdkVersion),
        api_class=str(ApplicationExitInfo),
    )
except Exception as exc:
    write_event(
        "target_exit_diagnostics_unavailable",
        error_type=type(exc).__name__,
        error=str(exc),
    )

threading.Thread(target=bridge_server, name="diagnostic-bridge", daemon=True).start()

while True:
    try:
        inspect_target_exit()
    except Exception as exc:
        write_event(
            "monitor_poll_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
    time.sleep(3)
