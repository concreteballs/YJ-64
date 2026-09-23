"""YJ-64 Android foreground monitor service."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from jnius import autoclass

TARGET = os.environ.get("YJ64_TARGET_PACKAGE", "org.blackmirror.blackmirror")
REPORT = Path(os.environ.get("YJ64_MONITOR_REPORT", "/data/data/org.blackmirror.yj64monitor/files/yj64-monitor.jsonl"))
REPORT.parent.mkdir(parents=True, exist_ok=True)

PythonService = autoclass("org.kivy.android.PythonService")
PythonService.mService.setAutoRestartService(True)

Context = autoclass("android.content.Context")
PythonActivity = autoclass("org.kivy.android.PythonActivity")
activity = PythonActivity.mActivity
usage = activity.getSystemService(Context.USAGE_STATS_SERVICE)
Event = autoclass("android.app.usage.UsageEvents$Event")

last_event = None

while True:
    now = int(time.time() * 1000)
    begin = now - 10_000
    events = usage.queryEvents(begin, now)
    event = Event()
    newest = None
    while events is not None and events.hasNextEvent():
        events.getNextEvent(event)
        if event.getPackageName() != TARGET:
            continue
        event_type = event.getEventType()
        if event_type in (Event.MOVE_TO_FOREGROUND, Event.MOVE_TO_BACKGROUND):
            newest = {
                "timestamp_ms": int(event.getTimeStamp()),
                "package": TARGET,
                "event": "foreground" if event_type == Event.MOVE_TO_FOREGROUND else "background",
            }
    if newest and newest != last_event:
        with REPORT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(newest, sort_keys=True) + "\n")
        last_event = newest
    time.sleep(1)
