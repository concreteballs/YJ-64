[app]
title = YJ-64 Monitor
package.name = yj64monitor
package.domain = org.blackmirror
source.dir = .
source.include_exts = py,json,md,txt
version = 0.1.2
icon.filename = icon.png
requirements = python3==3.10.11,hostpython3==3.10.11,kivy==2.3.0,pyjnius,android,sh<2.0,certifi
orientation = portrait
fullscreen = 0
android.api = 34
android.minapi = 24
android.ndk_api = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.permissions = INTERNET,FOREGROUND_SERVICE,FOREGROUND_SERVICE_SPECIAL_USE
services = monitor:services/monitor.py:foreground:sticky:foregroundServiceType=specialUse
android.debug_artifact = apk
p4a.extra_args = --cflags="-Wno-error=implicit-function-declaration"
android.extra_manifest_xml = ./android/extra_manifest.xml

[buildozer]
log_level = 2
warn_on_root = 1
bin_dir = ./bin
