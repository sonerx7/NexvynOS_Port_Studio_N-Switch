#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
STUDIO="$(cd "$ROOT/../.." && pwd)"
export DEVKITPRO="${DEVKITPRO:-/opt/devkitpro}"
export PATH="$DEVKITPRO/tools/bin:$DEVKITPRO/devkitA64/bin:$PATH"

SDK="${PORTSTUDIO_SDK:-$STUDIO/_PortStudioMain/nexvyn_sdk}"
SYSROOT="${NEXVYN_SYSROOT:-}"
RECOMP="${PCRECOMP:-$ROOT/../pcrecomp}"
BUILD="${RA2_BUILD_DIR:-$ROOT/build_nx_studio}"
JOBS="${RA2_BUILD_JOBS:-6}"
PYTHON="${RA2_PYTHON:-$(command -v python3 || command -v python || true)}"

EXPECTED="$(sed -n 's/.*"commit": *"\([0-9a-f]\{40\}\)".*/\1/p' "$ROOT/sdk.lock.json")"
if [[ -z "${PORTSTUDIO_SDK:-}" && -n "$EXPECTED" ]]; then
  CANDIDATE="$STUDIO/_PortStudioMain/_SdkCandidates/$EXPECTED"
  if [[ -f "$CANDIDATE/STUDIO_SOURCE.json" ]] &&
     ! grep -Fq "\"$EXPECTED\"" "$SDK/STUDIO_SOURCE.json" 2>/dev/null; then
    SDK="$CANDIDATE"
  fi
fi
KIT="$SDK/Languages/c/native-kit/sdk/native"
if [[ ! -f "$KIT/toolchain/nexvyn-switch.cmake" ]]; then
  printf '%s\n' "Native SDK not found: $KIT" >&2
  exit 1
fi
if [[ ! -f "$SDK/STUDIO_SOURCE.json" ]]; then
  printf '%s\n' "SDK source record missing: $SDK/STUDIO_SOURCE.json" >&2
  exit 1
fi
ACTUAL="$(sed -n 's/.*"commit": *"\([0-9a-f]\{40\}\)".*/\1/p' "$SDK/STUDIO_SOURCE.json")"
if [[ -z "$EXPECTED" || "$ACTUAL" != "$EXPECTED" ]]; then
  printf '%s\n' "SDK commit mismatch. Set PORTSTUDIO_SDK to snapshot $EXPECTED." >&2
  exit 1
fi
if [[ ! -d "$RECOMP/runtime/win32hle" || ! -d "$RECOMP/runtime/recomp32" ]]; then
  printf '%s\n' "pcrecomp not found. Set PCRECOMP to the prepared checkout: $RECOMP" >&2
  exit 1
fi
RECOMP_COMMIT="$(tr -d '\r\n' < "$ROOT/patches/pcrecomp.commit")"
if [[ "$(git -C "$RECOMP" rev-parse --verify HEAD)" != "$RECOMP_COMMIT" ]] ||
   ! git -C "$RECOMP" diff --no-ext-diff --no-color --full-index --unified=3 \
      --inter-hunk-context=0 --src-prefix=a/ --dst-prefix=b/ HEAD -- runtime tools |
      cmp -s - "$ROOT/patches/pcrecomp-nexvyn.patch" ||
   [[ -n "$(git -C "$RECOMP" ls-files --others --exclude-standard -- runtime tools)" ]]; then
  printf '%s\n' "pcrecomp must match $RECOMP_COMMIT plus the Nexvyn patch. See PORT.md." >&2
  exit 1
fi
if [[ ! -d "$SYSROOT/windowed/lib" || ! -d "$SYSROOT/windowed/include" ]]; then
  printf '%s\n' "Windowed SDL2 sysroot not found. Set NEXVYN_SYSROOT. See PORT.md." >&2
  exit 1
fi
if [[ ! -f "$ROOT/src/recomp/gen/lift_stamp.txt" ]]; then
  printf '%s\n' "The Yuri's Revenge lift is missing. Generate it using PORT.md." >&2
  exit 1
fi
if [[ -z "$PYTHON" ]]; then
  printf '%s\n' "Python is missing from this shell. Set RA2_PYTHON to the interpreter with the lift dependencies." >&2
  exit 1
fi
if ! PCRECOMP="$RECOMP" "$PYTHON" "$ROOT/run_lift.py" --check; then
  printf '%s\n' "The lift is stale or its Python dependencies are missing. Follow the lift steps in PORT.md." >&2
  exit 1
fi
if [[ -f "$BUILD/.port-studio-sdk" && "$(cat "$BUILD/.port-studio-sdk")" != "$EXPECTED" ]]; then
  printf '%s\n' "The build directory uses a different SDK commit. Set RA2_BUILD_DIR to a fresh directory." >&2
  exit 1
fi
if [[ -f "$BUILD/CMakeCache.txt" ]]; then
  CACHED_TOOLCHAIN="$(sed -n 's/^CMAKE_TOOLCHAIN_FILE:[^=]*=//p' "$BUILD/CMakeCache.txt")"
  if [[ ! "$CACHED_TOOLCHAIN" -ef "$KIT/toolchain/nexvyn-switch.cmake" ]]; then
    printf '%s\n' "The build directory uses a different SDK path. Set RA2_BUILD_DIR to a fresh directory." >&2
    exit 1
  fi
fi
if [[ ! -f "$KIT/lib/libnexvyn_window.a" ]]; then
  make -C "$KIT/lib"
fi

cmake -S "$ROOT" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$KIT/toolchain/nexvyn-switch.cmake" \
  -DNEXVYN_KIT="$KIT" \
  -DNEXVYN_WINDOWED=ON \
  -DNEXVYN_SYSROOT="$SYSROOT" \
  -DPCRECOMP="$RECOMP"
printf '%s\n' "$EXPECTED" > "$BUILD/.port-studio-sdk"

case "${1:-}" in
  "")
    cmake --build "$BUILD" --parallel "$JOBS"
    ;;
  launcher)
    ninja -C "$BUILD" -j "$JOBS" CMakeFiles/ra2_windowed_objects.dir/src/nx/launcher.o
    ;;
  fast)
    mapfile -t targets < <(ninja -C "$BUILD" -t targets all |
      awk -F: '/ra2_windowed_objects\.dir\/.*(launcher|nx\/main|imgui_gl_glue|hle_path|bink|gdidc|screen|wsock32|guest_mem|kernel32_ext)\.o:/ {print $1}')
    if [[ ${#targets[@]} -eq 0 ]]; then
      printf '%s\n' "Incremental build targets are missing." >&2
      exit 1
    fi
    ninja -C "$BUILD" -j "$JOBS" "${targets[@]}"
    ;;
  *)
    printf '%s\n' "Usage: build_nx.sh [launcher|fast]" >&2
    exit 2
    ;;
esac
