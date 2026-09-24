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

Context = autoclass("android.content.Context")
usage = service.getSystemService(Context.USAGE_STATS_SERVICE)
Event = autoclass("android.app.usage.UsageEvents$Event")
ActivityManager = autoclass("android.app.ActivityManager")
activity_manager = service.getSystemService(Context.ACTIVITY_SERVICE)

report_path = os.environ.get("YJ64_MONITOR_REPORT")
if report_path:
    REPORT = Path(report_path)
else:
    REPORT = Path(str(service.getFilesDir())) / "yj64-monitor.jsonl"

REPORT.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(payload: dict[str, Any]) -> None:
    with REPORT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


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


threading.Thread(target=bridge_server, name="diagnostic-bridge", daemon=True).start()

last_event = None
seen_target_running = False
reported_target_termination = False


def target_process_running() -> bool:
    processes = activity_manager.getRunningAppProcesses()
    if processes is None:
        return False
    for process in processes:
        if process.processName == TARGET:
            return True
    return False


while True:
    now = int(time.time() * 1000)

    running = target_process_running()
    if running:
        seen_target_running = True
        reported_target_termination = False
    elif seen_target_running and not reported_target_termination:
        write_jsonl(
            {
                "timestamp_ms": now,
                "package": TARGET,
                "event": "target_process_terminated",
                "reason": "target_main_process_not_running",
                "detection": "activity_manager_poll",
            }
        )
        reported_target_termination = True

    begin = now - 10_000
    events = usage.queryEvents(begin, now)
    event = Event()
    newest = None

    while events is not None and events.hasNextEvent():
        events.getNextEvent(event)
        package_name = event.getPackageName()
        if package_name != TARGET:
            continue

        event_type = event.getEventType()
        if event_type in (Event.MOVE_TO_FOREGROUND, Event.MOVE_TO_BACKGROUND):
            newest = {
                "timestamp_ms": int(event.getTimeStamp()),
                "package": TARGET,
                "event": (
                    "foreground"
                    if event_type == Event.MOVE_TO_FOREGROUND
                    else "background"
                ),
            }

    if newest and newest != last_event:
        write_jsonl(newest)
        last_event = newest

    time.sleep(1)
