# YJ-64 Android monitor
[app]
title = YJ-64 Monitor
package.name = yj64monitor
package.domain = org.blackmirror
source.dir = .
source.include_exts = py,json,md,txt
version = 0.1.0
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 0
android.api = 35
android.minapi = 24
android.archs = arm64-v8a
android.permissions = PACKAGE_USAGE_STATS,QUERY_ALL_PACKAGES,FOREGROUND_SERVICE,FOREGROUND_SERVICE_SPECIAL_USE
android.allow_backup = False
services = monitor:services/monitor.py:foreground:sticky:foregroundServiceType=specialUse

[buildozer]
log_level = 2
warn_on_root = 1
