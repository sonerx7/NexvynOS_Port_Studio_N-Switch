# Port Studio changelog

## Unreleased

SDK always current:
- `port_studio.py sdk-update` keeps the active SDK on the newest one: a newer public release (official commit) wins; otherwise the newest local OS release build is exported with the OS release tool into a throwaway clone of the public SDK repository and becomes the active SDK as an owner pre-release (`STUDIO_SOURCE.json` says `owner-prerelease` with the OS commit). `doctor --json` reports `sdkFreshness`. The active SDK is now SDK 1.16 / OS 1.4.0.
- Vulkan header skeleton uses the real `nxn_vk.h`; stage/pack only refuse preview headers the active SDK does not ship.

Apps of every kind:
- Script apps (Lua, JavaScript, Python 3) run through `make` (verify with `nxv check`, pack with `nxv pack`, emulator scenario with `--source`); `new-app` writes their `port.json`, `sdk.lock.json`, `memory` and eight-locale store text (`--summary`).
- `new-app emulator` and `new-app decomp`: the kit skeletons build a stand-alone NRO, so Studio makes windowed modules from the game template plus their helper sources (JIT memory on `nxn_jit`).

Testing:
- `shot_grid.py` draws a coordinate grid and a port's tap targets on a screenshot.
- Scenario `setup: "clean"` / `"update"` (with `--previous`) prepares clean-install and update runs automatically.
- `console_run.py` push / sheet / record: send the app to a console, a checklist for the tester, console results from the filled sheet only.
- Motion check ignores the desktop clock and system widgets (a launcher on the desktop counted as motion before); measured on all recorded runs.
- The shared emulator profile lock is taken atomically and runs wait for it instead of failing (two sessions overwrote each other's autorun before).
- `make` records the toolchain and devkitPro portlib versions of the machine in its report.

Platform facts (OS 1.4.0 candidate / SDK 1.16):
- Vulkan counts as released by owner decision (`ownerReleased` in `capabilities.json`; `platform_refresh.py` applies it last). It is on by default; ports check `NXN_CAP_VULKAN` and keep the GL path as the fallback. `assess` now routes Vulkan sources to native Vulkan with a GL fallback.
- The library list names each library's source: Nexvyn sysroot recipe (17), devkitPro portlib (installed versions from the build host) or kit-vendored. brotli is listed as not shipped.
- New entries: compatibility runtimes (PocketPy, Squirrel; TinyCC and miniJVM as on-demand components), script APIs of SDK 1.16 (`input.touches`, idle frame pacing), `fullscreenPause`, the OS performance panel, `native.vulkanOff`, port input rotate and double tap, `nxn_memory_budget_request`. Game Engine packages (gepack) are marked undocumented and not verified.
- Vulkan is released from OS 1.4.0 only: `assess --os` and `doctor --os` (default: the snapshot's OS) send older OS targets to the GL path and say why. The Vulkan template, its header skeleton and `PORT.md` note that `nxn_vk.h` ships from SDK 1.16.

Packages:
- `stage` and `pack` refuse a payload that carries preview-only SDK files (headers and changed file contents of a preview candidate that the active SDK does not ship).

Pipeline:
- `port_studio.py make <port>` runs the existing tools in order (doctor, build or stage, verify, pack, scenario run, automatic shot review) and writes `make_report.md` with each command, exit code and output tail; it stops at the first failure and never reports a gameplay pass. `--workspace` runs everything on a copy (build output and personal data stay behind; `PORT_STUDIO_ROOT` points the port commands at the copy), so the original port is only read.

Emulator:
- Newest OS rule: emulator runs pick the newest Nexvyn OS on the machine (public release, refreshed when GitHub has a newer one, or a checksum-verified local release build) and record the version in the run. A run can no longer fall back to an old 1.3 build while 1.4.0 is available.
- Ryujinx and the OS checkout path are remembered in the git-ignored `_LocalData/studio_local.json`; Ryujinx is also found in the usual install folders.

New apps and port defaults:
- `scaffold.py new-app <lua|js|python3|native-app|game|emulator|decomp|web> <slug>` makes an app from an idea without assess: script runtimes through the SDK's `nxv new --store` (checked and packed with `nxv`), native ones through the port skeleton with the kit `app`/`game` template, web as an HTML5 starter for the OS browser (no packaged web runtime in the public SDK).
- Every new port skeleton gets `loadingHint` and `fullscreenPause` in app.json and a PORT.md note on the OS performance panel. A regression test pins the rest of the scaffold output to the files recorded before this change.

## 0.5.0

Studio becomes an open-ended port pipeline: source folder, assessment, template and libraries, scaffold, build, verification, package, emulator evidence, report. Every platform fact carries a status (released, private-preview, planned) and an evidence level (console, emulator, host, documented); only released items drive a production route.

Assessment:
- `assess` reports a verdict for any source (game, app, emulator, engine, software, web, tool, decomp, library) with file:line evidence, source type, run mode, kit template, libraries, OS settings and APIs, performance tier and profile, a reference port, a rated work list and a separate preview section. Blockers list ways around them; heavy sources get a staged port plan. `--batch` compares many sources.
- Source types are data (`platform/source_types.json`); eight synthetic fixtures cover SDL2, GL, Vulkan, Direct3D, Rust/Python, 2D software, emulator and decomp sources.

Platform facts:
- `platform/capabilities.json` (schema 3) is the single source of platform facts: graphics paths, templates, runtimes, OS settings, limits, kit recipes with versions and test mode, `nxv_native` commands, capability bits, device validation counters.
- `platform_refresh.py` derives these from the SDK snapshot, and optionally a development checkout, shows a diff and writes only with `--write`.

SDK:
- `sync_nexvyn_sdk.py --from-local` compares a development checkout's native kit with the released snapshot. `--stage` writes a preview candidate that build, check and pack refuse.
- `doctor --json` reports the platform facts date, APIs missing from the snapshot, preview candidates and the gcc version against the SDK's `toolchain.json`.

Port creation and checks:
- `scaffold.py` turns an assess report into a port folder: records, CMake from the kit template, eight locale files in the port and store source, app.json (`minNative` 1.1, `memory`, `loadingHint`), experience profile, emulator scenarios and a platform-rules header. A preview template needs `--allow-preview` and comes with a GL fallback.
- New `heavy` experience preset (render scale 0.67, 30 fps); golden hashes prove the other presets are unchanged.
- `verify.py` runs check-win, ABI, exports, check-lib, check-design, app.json fields, locales, package limits, personal-data separation, shaders, size and the update/clean-install scenarios, with a fix per failure.

Emulator evidence:
- `scenario_run.py` follows `port.json` `emulator.scenarios` into real play, takes a screenshot per phase and writes a run folder. `--console-profile` limits the emulator to 4 CPUs at below-normal priority. `emulator_test.py` is unchanged.
- `shot_review.py` checks for missing, blank or frozen shots, an app closed before a gameplay shot, required log lines, hangs, crashes and out-of-memory. It summarises FPS and peak heap, and writes `review.md`, `results.jsonl` (device-ingest line format, `NOT_RUN` until the visual review passes) and `performance_row.md`.

Maintenance:
- `run_tests.py` runs every host test with one command. Hygiene tests keep private OS-source markers and trademark words out of public files.
- `port_studio.py` forwards the new commands (`scaffold`, `verify`, `scenario`, `review`, `refresh`).
- Docs updated: README, AGENTS, playbook (flow table), assessment, experience, release workflow, SDK updates, PORT.md template.

## 0.3.0

- Added FIRST_RUN.md and bootstrap for SDK setup, preparation checks, and port handoff.
- Added SDK locking at init, local candidate selection, and retrieval of explicit public SDK commits.
- Added build for SDK CMake ports and stage for validated custom build outputs.
- Enforced release readiness before public packaging, including actual screenshots for App Market.

## 0.2.0

- Shared instructions for Codex, Gemini CLI, Antigravity, and Claude Code.
- Local SDK diagnostics, staged candidates, and per-port commit pins.
- Port Market 0.2.0 beta with a personal SD catalog and Internet Archive support.
