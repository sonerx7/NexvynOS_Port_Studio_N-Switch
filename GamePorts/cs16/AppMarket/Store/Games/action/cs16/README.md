# Counter-Strike 1.6 Launcher Preview for Nexvyn OS

## What it does
Counter-Strike 1.6 launcher preview and game-data validator for Nexvyn OS, built as an integrated native AArch64 module (`cs16.nxvmod`). It checks your selected Counter-Strike 1.6 installation folder and verifies the required WAD headers (`cstrike/cstrike.wad` and `valve/halflife.wad`). The Xash3D FWGS game engine is not yet bundled in this preview release.

## Setup and supported data versions
Proprietary game assets (maps, models, sounds, textures) are NOT included in the store package.
Supported data versions:
- Counter-Strike 1.6 (Retail / Steam / Build 8684 or compatible)
- Required game directories: `cstrike/` and `valve/` containing valid `WAD2`/`WAD3` files (`cstrike.wad`, `halflife.wad`).

Use the folder picker in the launcher to select your Counter-Strike 1.6 folder on the SD card, or bundle your files into a personal test package.

## Controls and display modes
- **Windowed & Live Resize**: 1280x720 default window with live resize support.
- **Navigation**: Gamepad, touch and mouse/keyboard support in the native Nexvyn OS UI.

## Version, requirements and known issues
- Version 1.0.1
- Target Nexvyn OS: 1.3.28-beta.2+ / SDK 1.15 / Native ABI 1
- Known issue: Launcher preview only; Xash3D FWGS engine integration is pending.

## Licenses and credits
- Original game by Valve Corporation.
- Nexvyn OS Native Launcher and data validator by sonerx7 (GPL-3.0).
