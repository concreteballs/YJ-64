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
android.api = 33
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = develop
p4a.commit = 5865575d81d53617784428ee29f57be2716311ea

[buildozer]
log_level = 2
warn_on_root = 1
bin_dir = ./bin

# APK build probe: force a fresh Android packaging run.
