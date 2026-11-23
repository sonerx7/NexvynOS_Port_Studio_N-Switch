# Counter-Strike 1.6 launcher preview for Nexvyn OS

Version 1.0.1 is a native launcher preview that checks original Counter-Strike 1.6 data. Gameplay, bot matches, and LAN play require the pending Xash3D FWGS and CS16Client integration. The preview targets Nexvyn OS 1.3.28-beta.2 with SDK 1.15 and Native ABI 1.

## Check your game files

Use **Select Game Folder** to choose the directory on your SD card containing `cstrike/` and `valve/`. The launcher remembers the selection when it can save the path and retain the folder grant. It uses valid bundled data first when you supply your own files in a personal test package.

The launcher checks the `WAD2` or `WAD3` signatures in `cstrike/cstrike.wad` and `valve/halflife.wad`. A passed check applies to those headers. Compatibility with specific retail and Steam builds, including Build 8684, remains unverified. Supply the original game files from your own installation.

## Launcher controls and display

The preview uses Nexvyn OS navigation for gamepad, touch, and keyboard/mouse input. It opens in a resizable 1280 × 720 window by default. It uses the Nexvyn OS language at launch, with English as the fallback. The package includes English, Turkish, German, Spanish, French, Japanese, Korean, and Chinese locale files. Input, resize, and locale rendering still need device or emulator verification.

## Licenses and credits

- Original game by Valve Corporation.
- Native launcher and file checker by sonerx7 under GPL-3.0. [License](source/LICENSE) · [Source notice](source/NOTICE.md)
- Dear ImGui is distributed under the MIT license. [Dear ImGui license](source/LICENSE-IMGUI.txt)
