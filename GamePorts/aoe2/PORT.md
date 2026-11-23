# Age of Empires II PC native port record

> **Status: launcher preview only (2026-11-23).** The native AArch64 launcher, file checker and local packaging work. The game engine is not linked, so the game cannot be played. A function catalog of `empires2.exe` exists as a first step toward a lift.

## Target and status

- **Product:** Age of Empires II: The Age of Kings (2.0a), developed by Ensemble Studios and published by Microsoft for Windows PC.
- **Target:** Nexvyn OS on Nintendo Switch, AArch64, Native ABI 1.
- **Target data:** User's verified retail installation at `C:\Program Files (x86)\Microsoft Games\Age of Empires II`.
- **Verified binaries & hashes:**
  - `empires2.exe`: SHA-1 `9ad7fdd5c294cafff60862a3cbbe18999118c570` (2,560,000 bytes)
  - `EMPIRES2.ICD`: SHA-1 `3b12f0e0eed55d453c4baa4fbf34d8e6dbbe3f21` (2,560,045 bytes)
  - `Data/graphics.drs`: 73,566,713 bytes
  - `Data/interfac.drs`: 35,591,977 bytes
  - `Data/sounds.drs`: 29,678,340 bytes
  - `Data/terrain.drs`: 4,810,396 bytes
  - `Data/gamedata.drs`: 532,476 bytes
  - `Data/empires2.dat`: 659,808 bytes
  - `language.dll`: 499,712 bytes
- **Planned experience (not implemented):** Real-time strategy (RTS) with dual-stick cursor and box-selection, touchscreen gestures (pinch-zoom, tap-select, hold-command), and docked USB keyboard/mouse support.

## Research and feasibility

| Dependency / Candidate | Verified source | Effect on the decision |
| --- | --- | --- |
| User retail installation | `C:\Program Files (x86)\Microsoft Games\Age of Empires II` | Verified on host. Validated PE headers: EntryPoint `0x200281` (WinMainCRTStartup in `.text`), Base `0x400000`. The `.text` code section is plain, unencrypted x86 code with standard MSVC CRT prologue. |
| Function recovery (`disasm32.py`) | `_LocalData/pcrecomp/tools/disasm/disasm32.py` | Disassembled `empires2.exe` to `work/functions.json`: **19,140 functions** recovered across 2,603,224 instructions, achieving **95.0% byte coverage** (2,097,638 / 2,207,744 bytes). |
| Upstream decompilation | [samuelcaldas/age-of-empires-2-decomp](https://github.com/samuelcaldas/age-of-empires-2-decomp) (commit `505de76dfcb1f3a2eab081a4370d517cb16025ee`) | Decompilation project currently has 0% splits for PC editions (`AGE2_X1_1_0C_EN` / `EMPIRES2_2_0A_EN`) and lacks IDA Pro split exports. PS2 matching progress (~40%) does not provide a standalone PC engine. |
| Nexvyn public SDK | Commit `7c6a0bbd2d4dd334f24a9fbbdc922904c9507fc6`, SDK 1.15, Native SDK 1.2, ABI 1 | Windowed module and RTS input contract fully supported. |
| Compiler | devkitA64 GCC 15.2.0 | Standard toolchain for AArch64 native modules. |

Feasibility: the launcher and data packaging are done. Lifting the engine is **not started**: the function catalog (`work/functions.json`, ignored by Git) is only the first step, and it is not known whether the shipped `.text` is complete.

## Switch constraints and architecture

- **CPU / ABI:** Cortex-A57 (AArch64) @ 1.02 GHz. Requires 64-bit native code; 32-bit x86 code runs through static recompilation lift.
- **Memory:** 4 GB unified LPDDR4. Age of Empires II PC requires ~64–128 MB RAM, well within Switch limits.
- **Graphics:** 1280x720 handheld / 1920x1080 docked. Software/DirectDraw 8-bit paletted rendering requires a 32-bit RGBA surface upload or GLES3 texture shader.
- **Input:** Native support for touchscreen (single touch select, two-finger pan, pinch zoom), gamepad dual-stick emulation, and full USB mouse/keyboard when docked.
- **Copy protection:** open question. The `.text` section looked like plain x86 code in the PE header check, but an `EMPIRES2.ICD` file ships beside the executable and other notes describe a SafeDisc wrapper. Resolve this before any lift.

## Build from a fresh checkout

Run from the repository root:

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py bootstrap --port GamePorts/aoe2
python -X utf8 _PortStudioMain/tools/port_studio.py experience generate GamePorts/aoe2
python -X utf8 _PortStudioMain/tools/port_studio.py build GamePorts/aoe2
python -X utf8 _PortStudioMain/tools/port_studio.py check store GamePorts/aoe2
```

`build` compiles `aoe2.nxvmod` using the Native SDK CMake toolchain, validates ABI and imports, and stages the module into the App Market source tree.

To generate a personal test package with the user's data:

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py pack local GamePorts/aoe2 --data-root "C:\Program Files (x86)\Microsoft Games\Age of Empires II"
```

Output: `_RealesedBuilds/game/aoe2/com.sonerx7.aoe2-1.0.0-local.nxvapp`

## Planned RTS controls (not working yet)

| Action | Gamepad | Touch | Keyboard / Mouse |
| --- | --- | --- | --- |
| Move pointer | Left stick | Direct tap | Move mouse |
| Select / primary action | A button | Single tap | Left click |
| Command / secondary action | X button | Press and hold | Right click |
| Box selection | ZR + Left stick | Drag with one finger | Drag left button |
| Cancel selection | B button | Two-finger tap | Escape |
| Pan camera | Right stick | Two-finger drag | Screen edge / W A S D |
| Zoom view | ZL / ZR | Pinch in / out | Mouse wheel |
| Game menu | + button | Screen menu button | F10 / Escape |

## Verification

| Scenario | Environment, OS, package, and data | Result and evidence |
| --- | --- | --- |
| Fresh source checkout on Windows | devkitA64 GCC 15.2.0, SDK 1.15, Native SDK 1.2 | Compiles `aoe2.nxvmod`; passes native relocation, import, and store checks. |
| Store compliance check | `check store GamePorts/aoe2` | Verified manifest, licenses, 8 locale dictionaries, and RTS experience contract. |
| Personal package generation | `pack local GamePorts/aoe2 --data-root ...` | Packaged 23 files (148.9 MB unpacked, 84.8 MB compressed) to `_RealesedBuilds/game/aoe2/com.sonerx7.aoe2-1.0.0-local.nxvapp`. Manifest intact. |
| x86 function recovery | `disasm32.py` on `empires2.exe` | 19,140 functions listed in `work/functions.json` (checked by counting entries; the 95% byte coverage the tool reported was not re-checked). |
