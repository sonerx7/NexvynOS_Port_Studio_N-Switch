# RA2 Yuri Port 1.2.1

Native Yuri's Revenge static recompilation runtime for Nexvyn OS, with a system-themed setup launcher, non-destructive overlay configuration, and RTS camera controls for Gamepad, Touch, and Keyboard/Mouse.

| Field | Value |
|---|---|
| App ID | `com.sonerx7.redalert2` |
| Version | `1.2.1` |
| Channel | App Market (`kind: port`, strategy) |
| Runtime | Native `.nxvmod`, Native SDK 1.2; minimum general SDK 1.10 |
| Target | General SDK 1.15, Native SDK 1.2 |
| Launcher languages | English, Turkish, German, Spanish, French, Japanese, Korean, Chinese |
| Upstream | [redalert2-recomp](https://github.com/sp00nznet/redalert2-recomp), [pcrecomp](https://github.com/sp00nznet/pcrecomp) |
| License | MIT for the recompilation engine and host wrappers; original game files are not included |

## Setup with your own game files

Open the launcher and choose your installed Yuri's Revenge game folder. It must contain the supported `gamemd.exe` (PE timestamp `0x3BDF544E`), `ra2.mix`, `ra2md.mix`, and the remaining archives from your installation. Missing files and unsupported executable variants are reported separately in the launcher.

Your original game folder is never modified: `ra2md.ini`, mod selections, and language overrides are written into the app's persistent overlay directory.

## Controls and display profiles

- **Left stick**: precision pointer movement (with optional L slow-precision / R fast-boost).
- **Right stick / D-pad**: 8-way RTS camera panning.
- **A / ZR**: left click and drag-box selection; **X / ZL**: right click.
- **B / Plus**: Escape; **Minus**: Tab (short press); **Y / L / R / L3 / R3**: configurable RTS actions (Deploy, Base, Select Type, Combat Units, Scatter, Stop, Control Groups, OSK).
- **Touch**: single-finger tap/drag, two-finger camera pan, and optional long-press or two-finger right click.
- **Keyboard & Mouse**: native mouse pointer, arrow/WASD camera panning, F11 fullscreen, F12 scaling filter.
- **Display**: Nexvyn OS Stable profile and optional Auto Dock / Handheld resolution (1080p docked, 720p handheld).
