# Nexvyn Port Studio

Nexvyn Port Studio is a workspace for porting existing games and applications to Nintendo Switch as native Nexvyn OS modules. Its workflow covers feasibility, engine selection, SDK setup, launcher and controls, and personal and App Market packaging.

## Start here

Read [FIRST_RUN.md](FIRST_RUN.md) to set up a fresh clone, check the SDK, and continue an existing port or start a new one. The public SDK ships with the repository. Coding agents start from [AGENTS.md](AGENTS.md).

From the repository root with Python 3.10 or newer:

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py doctor --json
python -X utf8 _PortStudioMain/tools/port_studio.py bootstrap
```

| Location | Purpose |
| --- | --- |
| `GamePorts/` | Game ports |
| `SoftwarePorts/` | Application ports |
| [`_PortStudioMain/`](_PortStudioMain/README.md) | Public SDK, shared tools, templates, and guides |
| `_RealesedBuilds/game/` and `_RealesedBuilds/software/` | Personal test packages that can include user-supplied data |
| `<port>/AppMarket/Store/` | Store source bundle, screenshots, and local submission candidates |

## What Studio gives you

| Command | What it does |
| --- | --- |
| `doctor`, `bootstrap` | Check the locked SDK snapshot and the native toolchain. |
| `init` | Create the feasibility, release, changelog and known-issues records for a new port. |
| `build`, `stage`, `check` | Build an SDK CMake port, stage it, and validate it for the App Market. |
| `pack local` / `pack store` | Personal `.nxvapp` with your own game data, or a data-free store package. Warns when a package has too many files. |
| `experience` | Declare input modes, gestures and performance profiles; generates the per-port how-to text and `nx_experience.h`. |
| `analyze`, `updates` | Suggest an experience profile from a game folder; check for new Nexvyn OS releases. |
| `bump` | Bump a port version everywhere (`app.json`, store copy, CMake) and open changelog and known-issues entries. |

Emulator testing, scripted taps and two-finger gestures, and handheld and docked modes are in [`emulator_test.py`](_PortStudioMain/tools/emulator_test.py) (see "Emulator test" in the [release workflow](_PortStudioMain/docs/RELEASE_WORKFLOW.md)). Shared launcher widgets are in [`portkit/`](_PortStudioMain/portkit).

## Existing ports

| Port | State |
| --- | --- |
| [Red Alert 2 / Yuri’s Revenge](GamePorts/RedAlert2/PORT.md) | Native RTS runtime and launcher (overview, video, controls, how to play, files, logs). Touch, gamepad and keyboard/mouse work; two-finger drag pans the map. Pinch zoom is not available because the game ignores the mouse wheel. Verified in an emulator only, not on a physical Switch. The build needs your own original executable to generate the lift. |
| [Age of Empires II (1999)](GamePorts/aoe2/PORT.md) | Launcher preview and data validator only. The game engine is not linked, so nothing is playable yet. |
| [Counter-Strike 1.6](GamePorts/cs16/PORT.md) | Paused. Launcher preview and game-data validator only. |
| [Chromium NX](SoftwarePorts/chromium-nx/PORT.md) | Record of an upstream browser build and a direct-start patch. The Linux kernel layer boots in an emulator; the full browser needs a real Switch with a title forwarder. |
| [Diablo 1](GamePorts/Diablo%201/README.md), [Blender](SoftwarePorts/Blender/README.md) | Initial research records. |

No game data, keys or personal packages are in this repository. You supply original game files yourself; they stay in `_RealesedBuilds/` and `_LocalData/`, which Git ignores.

## Guides

- [Porting playbook](_PortStudioMain/docs/INSTANT_PORT_PLAYBOOK.md)
- [Switch cross-compilation](_PortStudioMain/docs/CROSS_COMPILATION_CHEATSHEET.md)
- [SDK updates](_PortStudioMain/docs/SDK_UPDATES.md)
- [Launcher standard](_PortStudioMain/docs/PORT_LAUNCHER_STANDARD.md)
- [Port experience layer](_PortStudioMain/docs/PORT_EXPERIENCE.md)
- [Release workflow and emulator test](_PortStudioMain/docs/RELEASE_WORKFLOW.md)
- [Port Market](_PortStudioMain/docs/PORT_MARKET.md)
