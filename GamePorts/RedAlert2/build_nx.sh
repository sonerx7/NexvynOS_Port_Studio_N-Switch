#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
STUDIO="$(cd "$ROOT/../.." && pwd)"
export DEVKITPRO="${DEVKITPRO:-/opt/devkitpro}"
export PATH="$DEVKITPRO/tools/bin:$DEVKITPRO/devkitA64/bin:$PATH"

SDK="${PORTSTUDIO_SDK:-$STUDIO/_PortStudioMain/nexvyn_sdk}"
KIT="$SDK/Languages/c/native-kit/sdk/native"
SYSROOT="${NEXVYN_SYSROOT:-}"
RECOMP="${PCRECOMP:-$ROOT/../pcrecomp}"
BUILD="${RA2_BUILD_DIR:-$ROOT/build_nx_studio}"
JOBS="${RA2_BUILD_JOBS:-6}"

if [[ ! -f "$KIT/toolchain/nexvyn-switch.cmake" ]]; then
  printf '%s\n' "Native SDK bulunamadı: $KIT" >&2
  exit 1
fi
if [[ ! -f "$SDK/STUDIO_SOURCE.json" ]]; then
  printf '%s\n' "SDK kaynak kaydı eksik: $SDK/STUDIO_SOURCE.json" >&2
  exit 1
fi
EXPECTED="$(sed -n 's/.*"commit": *"\([0-9a-f]\{40\}\)".*/\1/p' "$ROOT/sdk.lock.json")"
ACTUAL="$(sed -n 's/.*"commit": *"\([0-9a-f]\{40\}\)".*/\1/p' "$SDK/STUDIO_SOURCE.json")"
if [[ -z "$EXPECTED" || "$ACTUAL" != "$EXPECTED" ]]; then
  printf '%s\n' "SDK commit'i eşleşmiyor. PORTSTUDIO_SDK ile $EXPECTED snapshot'ını seçin." >&2
  exit 1
fi
if [[ ! -d "$RECOMP/runtime/win32hle" || ! -d "$RECOMP/runtime/recomp32" ]]; then
  printf '%s\n' "pcrecomp bulunamadı. PCRECOMP yolunu ayarlayın: $RECOMP" >&2
  exit 1
fi
if [[ ! -d "$SYSROOT/windowed/lib" || ! -d "$SYSROOT/windowed/include" ]]; then
  printf '%s\n' "SDL2 windowed sysroot bulunamadı. NEXVYN_SYSROOT yolunu ayarlayın." >&2
  exit 1
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
      printf '%s\n' "Hızlı derleme hedefleri bulunamadı." >&2
      exit 1
    fi
    ninja -C "$BUILD" -j "$JOBS" "${targets[@]}"
    ;;
  *)
    printf '%s\n' "Kullanım: build_nx.sh [launcher|fast]" >&2
    exit 2
    ;;
esac
