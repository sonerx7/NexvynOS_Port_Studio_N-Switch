#!/usr/bin/env bash
# One command from a fresh clone to build_nx_studio/ra2.nxvmod.
# Needs: your own game/gamemd.exe, devkitPro, Python with capstone==5.0.7 and pefile==2024.8.26.
# Safe to rerun: each step is skipped when its result already exists and matches the lock files.
# Usage (Studio root, Bash; on Windows use devkitPro MSYS2 bash):  bash GamePorts/RedAlert2/build_all.sh
set -euo pipefail
STUDIO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="$STUDIO/GamePorts/RedAlert2"
export PORTSTUDIO_SDK="${PORTSTUDIO_SDK:-$STUDIO/_PortStudioMain/nexvyn_sdk}"
export PCRECOMP="${PCRECOMP:-$STUDIO/_LocalData/pcrecomp}"
export NEXVYN_SYSROOT="${NEXVYN_SYSROOT:-$STUDIO/_LocalData/ra2-sysroot}"
export NEXVYN_SYSROOT_CACHE="${NEXVYN_SYSROOT_CACHE:-C:/nxc}"   # short path: long ones break the SDL2 build on Windows
export RA2_PYTHON="${RA2_PYTHON:-$(command -v python3 || command -v python)}"
step() { printf '\n[%s] %s\n' "$1" "$2"; }

step 1/5 "Check the game file"
[[ -f "$PORT/game/gamemd.exe" ]] || { echo "Missing $PORT/game/gamemd.exe: copy it from your own Yuri's Revenge install." >&2; exit 1; }

step 2/5 "pcrecomp at the locked commit with the Nexvyn patch"
lock="$(tr -d '\r\n' < "$PORT/patches/pcrecomp.commit")"
[[ -d "$PCRECOMP/.git" ]] || git clone https://github.com/sp00nznet/pcrecomp.git "$PCRECOMP"
git -C "$PCRECOMP" checkout -q --detach "$lock"
if git -C "$PCRECOMP" apply --check "$PORT/patches/pcrecomp-nexvyn.patch" 2>/dev/null; then
  git -C "$PCRECOMP" apply "$PORT/patches/pcrecomp-nexvyn.patch"
elif ! git -C "$PCRECOMP" apply --check --reverse "$PORT/patches/pcrecomp-nexvyn.patch" 2>/dev/null; then
  echo "pcrecomp has local changes that block the patch. Use a clean checkout." >&2; exit 1
fi

step 3/5 "SDL2 sysroot from the locked SDK"
if [[ ! -f "$NEXVYN_SYSROOT/windowed/lib/libSDL2.a" ]]; then
  NEXVYN_SYSROOT_OUT="$NEXVYN_SYSROOT" "$RA2_PYTHON" \
    "$PORTSTUDIO_SDK/Languages/c/native-kit/sdk/native/sysroot/build.py" sdl2-nexvyn
fi

step 4/5 "Catalog and lift (the longest CPU step)"
cd "$PORT"; mkdir -p work
[[ -f work/rtti.json ]] || "$RA2_PYTHON" "$PCRECOMP/tools/cpp/rtti.py" game/gamemd.exe -o work/rtti.json --seeds work/rtti_seeds.json
[[ -f work/functions.json ]] || "$RA2_PYTHON" "$PCRECOMP/tools/disasm/disasm32.py" game/gamemd.exe -o work/functions.json --seed-functions work/rtti_seeds.json
"$RA2_PYTHON" run_lift.py --all

step 5/5 "Native build"
bash build_nx.sh
echo; echo "Done: $PORT/build_nx_studio/ra2.nxvmod"
echo "Next: python -X utf8 _PortStudioMain/tools/port_studio.py stage GamePorts/RedAlert2 --module GamePorts/RedAlert2/build_nx_studio/ra2.nxvmod"
