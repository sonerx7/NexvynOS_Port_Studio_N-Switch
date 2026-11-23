# Counter-Strike 1.6 launcher architecture

## Current native module

`cs16.nxvmod` is a windowed AArch64 launcher preview built with the locked Nexvyn SDK 1.15 and Native SDK 1.2 (ABI 1). Building the preview requires devkitPro, devkitA64, and `switch-glad`. [Build instructions](../PORT.md#build-from-a-fresh-checkout)

- `src/main.cpp` opens the Nexvyn display, renders the Dear ImGui interface using the OS appearance tokens, and updates the viewport on resize. The shared SDK input bridge handles gamepad, touch, and keyboard/mouse input for the launcher.
- `src/launcher.cpp` checks bundled `game/` data first and then looks for a saved folder with a valid access grant. The system folder picker lets users select another path. The preview saves that path in `game_dir.txt` in the app data directory.
- The file check reads 12 bytes from each required WAD and accepts the `WAD2` or `WAD3` signature. The launcher reports the result for each file. Map loading and compatibility with specific retail or Steam builds require an engine test.
- Launcher labels use the Nexvyn OS language at startup and fall back to English through `nxn_tr`. The preview ships English, Turkish, German, Spanish, French, Japanese, Korean, and Chinese locale files.

## Planned engine integration

Xash3D FWGS and CS16Client are candidates for hosting the user's GoldSrc game data. The engine, client, and game module revisions still need to be selected and tested with the windowed Nexvyn SDK. The first gameplay milestone is loading a map with the local client and server.

Gameplay input, profiles, remapping, handheld and dock performance, and session behavior across resize and suspend require implementation and runtime verification. See the proposed controls and release status in the [port record](../PORT.md).
