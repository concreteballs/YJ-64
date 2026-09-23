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
android.permissions = PACKAGE_USAGE_STATS,QUERY_ALL_PACKAGES
android.allow_backup = False
android.add_src = android_src

[buildozer]
log_level = 2
warn_on_root = 1
