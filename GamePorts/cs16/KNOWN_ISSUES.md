# Known issues

## 1.0.3

- Online play, LAN play, bots and map download need the Xash3D FWGS and CS16Client integration, which has not started building for Nexvyn OS. Nothing about multiplayer is verified.
- The preview package bundles only the two WADs. Use the launcher's folder picker for a full installation once an engine exists.

## 1.0.2

- The personal package now carries the full `cstrike` and `valve` folders (5,930 files). The launcher preview still only checks the two WAD headers; there is no engine, so gameplay, the buy menu and weapon selection cannot be tested yet.
- The "How to play" section was added to the launcher source but has not been shown in the emulator for this port.

## 1.0.1

- The native launcher preview checks the headers of `cstrike/cstrike.wad` and `valve/halflife.wad`. Xash3D FWGS and CS16Client integration is pending. A passed WAD check confirms the file signature and minimum length required by the preview. Compatibility with individual game builds and gameplay still require engine tests.
- Physical Switch and emulator verification is pending for folder selection, controller and pointer input, resize, and locale rendering. Store screenshots from the running preview and clearance to redistribute store artwork are also pending.

## 1.0.0

- The initial preview did not clearly show the engine status in the launcher. Version 1.0.1 made that status explicit.
