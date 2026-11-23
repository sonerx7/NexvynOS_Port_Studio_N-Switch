# Changelog

## 1.0.3

- Personal test package carries only the two WAD files the launcher preview checks (17 files, about 30 MB). The 1.0.2 package with all 5,930 game files made the OS install sheet sit on "Checking the package" for minutes. Full game data is meant to come from the folder picker.

## 1.0.2

- Added the shared Port Studio "How to play" section to the launcher and the experience layer (`port.json` controls and profiles).
- Personal test package now maps the whole `cstrike` and `valve` folders instead of two WAD files.

## 1.0.1

- Clarified the launcher status. This version contains the Nexvyn OS native launcher preview and WAD header checker. Xash3D FWGS integration remains pending.
- Added `WAD2` and `WAD3` header checks for `cstrike/cstrike.wad` and `valve/halflife.wad`.
- Added personal test packaging under `_RealesedBuilds/game/cs16/`.
- Localized the display initialization error in all eight launcher locales.

## 1.0.0

- Added the initial native launcher and data checker for Nexvyn OS 1.3.28-beta.2, Native SDK 1.2, and ABI 1.
- Added the Dear ImGui launcher and locale files for English, Turkish, German, Spanish, French, Japanese, Korean, and Chinese.
