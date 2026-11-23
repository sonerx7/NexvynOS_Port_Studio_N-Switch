# Red Alert 2 / Yuri’s Revenge port record

## 1.2.1

The Nexvyn OS build targets Yuri’s Revenge. It statically recompiles the Windows x86 executable into an AArch64 module. The launcher looks for the supported `gamemd.exe` with PE timestamp `0x3BDF544E`. A local copy with that timestamp was verified.

| Dependency | Verified source |
| --- | --- |
| Nexvyn OS SDK | `7c6a0bbd2d4dd334f24a9fbbdc922904c9507fc6`, SDK 1.15 / Native SDK 1.2 |
| pcrecomp | [Commit 621860a9d22c9b25ae2be4575b956596f4ddaeeb](https://github.com/sp00nznet/pcrecomp/commit/621860a9d22c9b25ae2be4575b956596f4ddaeeb) with the [Nexvyn patch](patches/pcrecomp-nexvyn.patch). |
| Compiler | devkitA64 GCC 15.2.0 |

## Build from a fresh checkout

Shortcut: after step 1 below and with your own `game/gamemd.exe` in place, `bash GamePorts/RedAlert2/build_all.sh` runs steps 2 to 4 in order and skips what already exists. The numbered steps stay as the reference for each part.

1. Follow [FIRST_RUN.md](../../FIRST_RUN.md). On Windows, run the native CMake commands in devkitPro MSYS2. Install the `switch-glad` portlib.
   If devkitPro MSYS2 cannot find Python, set `$env:RA2_PYTHON = (Get-Command python).Source.Replace('\', '/')` in PowerShell before starting the shell. In Bash, set `RA2_PYTHON` to the interpreter on your PATH if the variable is unset.
2. From the Studio root in Bash, prepare pcrecomp at the locked commit. When reusing an existing checkout, verify the revision and that the patch has already been applied.

```bash
git clone https://github.com/sp00nznet/pcrecomp.git _LocalData/pcrecomp
export PCRECOMP="$PWD/_LocalData/pcrecomp"
git -C "$PCRECOMP" checkout --detach "$(tr -d '\r\n' < GamePorts/RedAlert2/patches/pcrecomp.commit)"
git -C "$PCRECOMP" apply --check "$PWD/GamePorts/RedAlert2/patches/pcrecomp-nexvyn.patch"
git -C "$PCRECOMP" apply "$PWD/GamePorts/RedAlert2/patches/pcrecomp-nexvyn.patch"
```

3. Build the windowed SDL2 sysroot from the same SDK snapshot. Put `patch` on PATH. On Windows it is available in Git for Windows under `usr/bin`, or as the `patch` package in devkitPro MSYS2. Set `PORTSTUDIO_SDK` to the selected candidate path when testing an upgrade.

```bash
export PORTSTUDIO_SDK="${PORTSTUDIO_SDK:-$PWD/_PortStudioMain/nexvyn_sdk}"
export NEXVYN_SYSROOT="$PWD/_LocalData/ra2-sysroot"
# Windows: keep the build cache path short. A long path fails with "opening dependency file ... No such file or directory".
export NEXVYN_SYSROOT_CACHE="${NEXVYN_SYSROOT_CACHE:-C:/nxc}"
export RA2_PYTHON="${RA2_PYTHON:-$(command -v python3 || command -v python)}"
NEXVYN_SYSROOT_OUT="$NEXVYN_SYSROOT" "$RA2_PYTHON" \
  "$PORTSTUDIO_SDK/Languages/c/native-kit/sdk/native/sysroot/build.py" sdl2-nexvyn
```

4. Copy the supported `gamemd.exe` from your own Yuri’s Revenge installation to `GamePorts/RedAlert2/game/`. In your Python environment, install `capstone==5.0.7` and `pefile==2024.8.26`. Generate the catalog and lift locally.

```bash
cd GamePorts/RedAlert2
mkdir -p work
"$RA2_PYTHON" "$PCRECOMP/tools/cpp/rtti.py" game/gamemd.exe -o work/rtti.json --seeds work/rtti_seeds.json
"$RA2_PYTHON" "$PCRECOMP/tools/disasm/disasm32.py" game/gamemd.exe -o work/functions.json --seed-functions work/rtti_seeds.json
"$RA2_PYTHON" run_lift.py --all
bash build_nx.sh
```

5. From the Studio root, validate and stage the module. If you built with a candidate SDK, use the same snapshot with `--sdk`.

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py stage GamePorts/RedAlert2 --module GamePorts/RedAlert2/build_nx_studio/ra2.nxvmod
python -X utf8 _PortStudioMain/tools/port_studio.py check store GamePorts/RedAlert2
```

`bash build_nx.sh launcher` builds the launcher object using the same configuration. For a personal package, pass a `--data-root` containing all paths in `port.json` under `localData`. Use `pack local GamePorts/RedAlert2 --data-root "<local-data-root>"`. The App Market submission remains blocked pending the [distribution review](DISTRIBUTION.md) and device acceptance.

## Launcher and controls

The primary action opens the picker when data is missing. The launcher identifies missing files and incompatible executables. The Stable profile preserves the controller settings. Resetting controls preserves video and audio settings. Remapping covers a limited set of RTS actions. The full action map remains to be implemented. Dock transitions and the existing controls need physical Switch validation.

## Verification

| Scenario | Status |
| --- | --- |
| Locale and module validation | SDK checks passed. |
| Supported local `gamemd.exe` | PE timestamp matched `0x3BDF544E`. |
| pcrecomp baseline | The repository patch applied cleanly to the locked upstream commit. |
| Physical Switch | Gameplay, dock transitions, remapping, and release screenshots remain pending. |
| Previously verified personal package | `_RealesedBuilds/game/redalert2/`. Selected archives and supporting files produced a package with 993,062,529 bytes of unpacked data after excluding desktop add-ons and duplicate language backups. |
| Previous technical store candidate | `AppMarket/Store/Games/strategy/redalert2/`. The module and payload passed mechanical checks. Redistribution approval remains pending. |
