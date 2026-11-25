# Nexvyn Port SDK Guide

This document describes the current port helper header. For new ports, use the [public SDK's native port contract](../nexvyn_sdk/Guides/PORT_AND_LAUNCHER.md) for OS input ownership, system dialogs and persistent application data.

The Nexvyn Port SDK (`nexvyn_port_core`) is a C/C++ library that standardizes the common problems met when porting classic PC games and software to the console (libnx) and modern platforms.

## Core Problems Solved

1. **Input Translation:**
   - Cursor control with the analog stick for PC games that need a mouse and keyboard (`Virtual Mouse`).
   - Converting touchscreen input to left/right mouse clicks and dragging (`Touch to Mouse`).
   - Integration of a virtual keyboard or the Switch software keyboard (swkbd).

2. **Display and Resolution Scaling:**
   - Scaling fixed legacy resolutions such as 640x480 and 800x600 to Switch handheld mode (720p) and docked mode (1080p) while preserving the aspect ratio.

3. **File Path and Storage Standards:**
   - Emulation of case-insensitive file paths (case-sensitivity handling).
   - Safe storage of save files under `sdmc:/switch/nexvyn/<app_id>/saves`.

4. **Audio and Synchronization:**
   - Redirecting legacy DirectSound / WinMM audio calls to SDL2_mixer or the libnx hardware audio pipeline.

## SDK candidates and libraries

- **Preview candidates:** `sdk-local --stage` writes a preview candidate for comparison only. `stage` and `pack` refuse a payload with preview-only SDK files (`nxn_vk.h`, `nxn_imgui_vk.h`, content changed in the candidate) that the active SDK does not ship.
- **Library sources:** the platform list names where each library comes from: a Nexvyn sysroot recipe (17), a devkitPro portlib (versions installed on the build host), or kit-vendored. brotli is not shipped.
- **Compatibility runtimes:** PocketPy, Squirrel, TinyCC and miniJVM come as on-demand components.
- **gepack:** Game Engine packages exist in the OS source but are undocumented and not verified.
- **Platform facts:** `platform_refresh.py` applies `ownerReleased` (Vulkan) last, after it derives statuses.
- Not tested on a device.
