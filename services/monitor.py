"""YJ-64 Android foreground monitor service."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
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

# Ignore historical exits that happened before this monitor instance started.
_last_exit_key = None
_last_process_state = None

_event_sequence = 0
_last_command_id = None


def _new_message_metadata(prefix: str) -> dict[str, Any]:
    global _event_sequence
    _event_sequence += 1
    return {
        "message_id": f"{prefix}-{uuid.uuid4().hex}",
        "sequence": _event_sequence,
        "wall_time": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "monotonic_ns": time.monotonic_ns(),
    }


def _latest_exit_key() -> tuple[int, int] | None:
    try:
        manager = service.getSystemService("activity")
        history = manager.getHistoricalProcessExitReasons(TARGET, 0, 1)
        if not history:
            return None
        latest = history[0]
        return (int(latest.getTimestamp()), int(latest.getReason()))
    except Exception:
        return None


def _target_process_snapshot() -> list[dict[str, Any]]:
    """Return currently running processes belonging to the target UID."""
    try:
        package_manager = service.getPackageManager()
        target_uid = int(package_manager.getApplicationInfo(TARGET, 0).uid)
        manager = service.getSystemService("activity")
        processes = manager.getRunningAppProcesses() or []
        return [
            {
                "pid": int(process.pid),
                "process_name": str(process.processName or ""),
                "importance": int(process.importance),
                "importance_reason_code": int(process.importanceReasonCode),
                "importance_reason_pid": int(process.importanceReasonPid),
            }
            for process in processes
            if int(process.uid) == target_uid
        ]
    except Exception as exc:
        write_event(
            "target_process_state_failed",
            target_package=TARGET,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return []


def inspect_target_process_state() -> None:
    global _last_process_state
    processes = _target_process_snapshot()
    state = "running" if processes else "not_in_running_process_list"
    key = (state, tuple((item["pid"], item["process_name"]) for item in processes))
    if key == _last_process_state:
        return
    previous = _last_process_state
    _last_process_state = key
    write_event(
        "target_process_state_changed",
        target_package=TARGET,
        previous_state=(previous[0] if previous else None),
        state=state,
        process_count=len(processes),
        processes=processes,
    )


_last_exit_key = _latest_exit_key()

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
    metadata = _new_message_metadata("EXT")
    write_jsonl(
        {
            "source": "external_monitor",
            "event": event,
            "timestamp_ms": int(time.time() * 1000),
            **metadata,
            **details,
        }
    )


def inspect_target_exit() -> None:
    global _last_exit_key
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
        if _last_exit_key == key or timestamp <= (_last_exit_key[0] if _last_exit_key else -1):
            return
        _last_exit_key = key
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
    global _last_command_id
    try:
        connection.settimeout(2.0)
        received_wall_time = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        received_monotonic_ns = time.monotonic_ns()
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

        received_meta = _new_message_metadata("EXT-RECV")
        write_jsonl(
            {
                "source": "internal_diagnostic_agent",
                "bridge_received": True,
                "received_at_wall_time": received_wall_time,
                "received_at_monotonic_ns": received_monotonic_ns,
                **received_meta,
                "report": report,
            }
        )

        if report.get("event") == "diagnostic_test_result":
            data = report.get("data") or {}
            received_command_id = data.get("command_id")
            write_event(
                "diagnostic_test_verification",
                expected_command_id=_last_command_id,
                received_command_id=received_command_id,
                match=bool(
                    _last_command_id
                    and received_command_id == _last_command_id
                ),
                report_message_id=report.get("message_id"),
                report_wall_time=report.get("wall_time"),
                received_at_wall_time=received_wall_time,
            )

        ack_meta = _new_message_metadata("EXT-ACK")
        ack = {
            "ok": True,
            "report_id": report.get("report_id"),
            "ack_message_id": ack_meta["message_id"],
            "ack_sequence": ack_meta["sequence"],
            "ack_wall_time": ack_meta["wall_time"],
            "ack_monotonic_ns": ack_meta["monotonic_ns"],
            "received_at_wall_time": received_wall_time,
            "received_at_monotonic_ns": received_monotonic_ns,
        }

        if (
            os.environ.get("YJ64_AUTO_DIAGNOSTIC_TEST", "1") == "1"
            and report.get("event") == "target_launch_result"
        ):
            command_meta = _new_message_metadata("EXT-CMD")
            _last_command_id = command_meta["message_id"]
            ack["command"] = {
                "command": "RUN_DIAGNOSTIC_TEST",
                **command_meta,
                "issued_after_report_id": report.get("report_id"),
                "issued_at_wall_time": command_meta["wall_time"],
                "issued_at_monotonic_ns": command_meta["monotonic_ns"],
                "ack_wall_time": ack_meta["wall_time"],
                "ack_monotonic_ns": ack_meta["monotonic_ns"],
            }

        connection.sendall((json.dumps(ack, sort_keys=True) + "\n").encode("utf-8"))
        write_event(
            "bridge_command_response",
            reply_to=report.get("report_id"),
            command=ack.get("command"),
            report_received_at_wall_time=received_wall_time,
            report_received_at_monotonic_ns=received_monotonic_ns,
        )
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
        inspect_target_process_state()
        inspect_target_exit()
    except Exception as exc:
        write_event(
            "monitor_poll_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
    time.sleep(3)
