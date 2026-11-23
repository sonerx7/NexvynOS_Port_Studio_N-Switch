# Counter-Strike 1.6 native port record

> **Status: paused (2026-11-23).** Engine integration has not started; only the launcher preview exists. No gameplay, online or LAN play was built or verified.

## Target and status

- **Product** Counter-Strike 1.6 on GoldSrc, originally distributed for PC.
- **Target** Nexvyn OS on Nintendo Switch, AArch64, Native ABI 1.
- **Target data** A supported user-owned Steam or retail installation. This preview validates the WAD2/WAD3 headers of `cstrike/cstrike.wad` and `valve/halflife.wad`. Full build compatibility, including Build 8684, still needs an integrated engine test.
- **Planned experience** Offline bot matches and LAN play with dual-stick, gyro, touch, and keyboard/mouse support. The current module is a launcher preview.

## Engine feasibility

| Candidate | Evidence | Status |
| --- | --- | --- |
| [Xash3D FWGS](https://github.com/FWGS/xash3d-fwgs) | GoldSrc-compatible engine. Test the windowed graphics, sound, and input backends on Nexvyn OS. | Candidate commit `0119ead19d61f1064b996f26d17d2f3e1c075fd2` (fetched 2026-11-23, not yet built for Nexvyn OS). Source read, not run: it has a software renderer (`ref/soft`), a Switch target for libnx homebrew (`scripts/gha/build_nswitch.sh`, not the Nexvyn Native ABI), a `--low-memory-mode` option, and both protocol 49 and the GoldSrc protocol 48 constant (`PROTOCOL_GOLDSRC_VERSION`) needed to join CS 1.6 servers. Whether it joins a real server, and downloads maps from one, is unverified. |
| [CS16Client](https://github.com/FWGS/cs16-client) | The client and game DLLs need integration. The upstream license records GPL-2.0-or-later terms, a linking exception, and separate Half-Life SDK terms. | Pin revisions and review the client, server, bot code, and the combined redistribution basis. [Upstream license](https://github.com/FWGS/cs16-client/blob/main/LICENSE) |
| Nexvyn public SDK | SDK 1.15, Native SDK 1.2, ABI 1, OS 1.3.28-beta.2. | Using `7c6a0bbd2d4dd334f24a9fbbdc922904c9507fc6`. |

Feasibility is **limited**. The windowed launcher builds and validates as an AArch64 module. The next integration milestone is loading a real map with the local client and server. Measure the 60 FPS and 250 MB peak-memory targets on Switch. Review network permissions and test LAN functionality when networking is implemented. Users supply legitimate original game data.

## Build from a fresh checkout

Run from the repository root. Install devkitPro with the Switch `switch-glad` portlib.

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py bootstrap --port GamePorts/cs16 --fetch
python -X utf8 _PortStudioMain/tools/port_studio.py build GamePorts/cs16
python -X utf8 _PortStudioMain/tools/port_studio.py check store GamePorts/cs16
```

`build` makes `GamePorts/cs16/build/cs16.nxvmod`, then validates and stages it under the App Market source tree. For a personal preview package, use `pack local GamePorts/cs16 --data-root "<installation containing cstrike and valve>"`. The mapping includes the two WAD files the preview uses. The personal package is written to `_RealesedBuilds/game/cs16/`.

## Launcher and planned controls

The system folder picker and saved grant support external data. The launcher checks for bundled data first and shows the two WAD checks and engine status. The control map below describes the planned engine integration.

| Action | Gamepad | Touch | Keyboard/mouse |
| --- | --- | --- | --- |
| Attack / alternate attack | ZR / ZL | Fire / secondary buttons | Left / right mouse |
| Reload / jump / crouch | R / L / B | Action buttons | R / Space / Ctrl |
| Interact / buy / last weapon | A / X / Y | Action buttons | E / B / Q |
| Move / aim | Left stick / right stick + gyro | Virtual pad / swipe | WASD / mouse |
| Menu / scoreboard | Plus / Minus | Menu / score buttons | Esc / Tab |

## Verification

| Scenario | Result |
| --- | --- |
| Fresh source checkout on Windows, devkitA64 GCC 15.2.0, SDK 1.15 | Compiled the launcher and passed native identity, relocation, import, locale, and store source checks. |
| Physical Switch or emulator | Launcher behavior and full gameplay remain pending. |
| App Market release | Blocked while engine integration, device acceptance, and rights for store visuals are pending. |
