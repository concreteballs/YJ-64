# Android runtime diagnostics

YJ-64 now includes a dependency-free ADB collector based on capabilities we
evaluated in established tools.

- DeepADB: persistent logcat watchers and diagnostics such as dumpsys and top.
- Android-App-Memory-Analysis: meminfo, gfxinfo, HPROF and SMAPS correlation.
- DebugOverlay-Android: CPU, heap, PSS, FPS, thermal, logcat and app-exit data.
- simvyn: device discovery, app lifecycle control and streamed ADB logs.

YJ-64 does not copy these projects wholesale. It exposes the non-destructive,
CI-friendly subset needed for an external monitor:

1. device state;
2. crash-buffer logcat;
3. dumpsys meminfo;
4. dumpsys gfxinfo;
5. a top CPU/memory snapshot;
6. Android app-exit history.

All probes are best-effort. A missing ADB binary or unavailable device does not
make the diagnostic engine fail.

The target application package is configurable in
config/android_runtime.json. Kerosene Rose 3 currently uses package domain
org.blackmirror and package name blackmirror, so its Android application id is
org.blackmirror.blackmirror.
