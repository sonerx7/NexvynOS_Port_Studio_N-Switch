# Age of Empires II PC native launcher preview for Nexvyn OS

Version 1.0.0 is an integrated native launcher preview, data validator, and RTS controls experience layer for Age of Empires II on Nexvyn OS. Upstream PC decompilation is tracked from `samuelcaldas/age-of-empires-2-decomp`, where executable splits remain pending. The preview targets Nexvyn OS 1.3.28-beta.2 with SDK 1.15 and Native ABI 1.

## What it does

- Provides an interactive windowed launcher for Nexvyn OS with gamepad, touchscreen, and keyboard/mouse navigation.
- Validates essential original Age of Empires II PC data files (`data/graphics.drs`, `data/empires2.dat`, and game executables `empires2.exe` / `age2_x1.exe`).
- Displays the complete RTS control schema and "How to play" guidance for handheld touch, gamepad dual-stick, and desktop keyboard/mouse setups.
- Saves and restores selected game folder paths and OS folder permissions.

## Setup and supported data versions

Use **Select Game Folder** to choose your Age of Empires II PC installation folder on your SD card. The launcher validates the presence and minimum file size of:
- `data/graphics.drs`
- `data/empires2.dat` (or `data/empires2_x1.dat`)
- `empires2.exe` or `age2_x1/age2_x1.exe`

Users supply legitimate game files from their own PC retail or CD installation. No copyrighted game assets or engine code are distributed in this package.

## Controls and display modes

The preview opens in a resizable 1280 × 720 window by default, supporting live window resizing:
- **Touch:** Tap to select, drag to box-select or pan camera, pinch to zoom.
- **Gamepad:** Left stick moves pointer, A button selects, X button issues command, ZR + stick box-selects, Right stick pans camera, + opens menu.
- **Keyboard / Mouse:** Left click selects, Right click commands, Drag box-selects, Mouse wheel zooms, F10 / Esc opens menu.

## Version, requirements and known issues

- **Target OS:** Nexvyn OS 1.3.28-beta.2 (or newer).
- **Target Native:** 1.2 / ABI 1.
- **Engine integration:** Pending. The PC decompilation in `samuelcaldas/age-of-empires-2-decomp` is currently at 0% matched splits. Full gameplay execution is blocked until an engine is integrated.

## Licenses and credits

- Age of Empires II was created by Ensemble Studios and published by Microsoft.
- Native launcher and validator by sonerx7 under GPL-3.0. [License](source/LICENSE) · [Source notice](source/NOTICE.md)
- Dear ImGui is distributed under the MIT license. [Dear ImGui license](source/LICENSE-IMGUI.txt)
