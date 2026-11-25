# Porting playbook

The target is an integrated AArch64 native application for Nexvyn OS on the console. Start with [FIRST_RUN.md](../../FIRST_RUN.md). For an existing port, run `bootstrap --port <port>` and read its `PORT.md`.

## The flow in one view

| Step | Command | Output |
| --- | --- | --- |
| 1. Measure | `port_studio.py assess <source> --out _LocalData/<slug>_assessment.md --json` | verdict, source type, run mode, template, libraries, OS settings, tier, work list |
| 2. Scaffold | `scaffold.py game\|software <slug> <category> --from-assess <report.json>` | port folder: PORT.md, port.json (experience + emulator scenarios), CMake, lang/ x8, rules header |
| 3. Build | `port_studio.py build <port>` (SDK CMake) or `stage <port> --module <file>` | `.nxvmod` staged in the store source |
| 4. Verify | `verify.py <port>` | one table: imports, ABI, app.json, locales, limits, shaders, size, update/clean-install scenarios |
| 5. Package | `port_studio.py pack local\|store <port>` | personal and store `.nxvapp` (store unsigned) |
| 6. Emulator evidence | `scenario_run.py <port> ... [--console-profile]`, then the visual review and `shot_review.py <run> --check` | run folder with shots, review.md, results.jsonl, performance_row.md |
| 7. Report | handoff in PORT.md | approach, commits, packages, tests by environment (host / emulator / console), known issues |

`port_studio.py make <port> [--module FILE] [--data-root DIR] [--workspace DIR] [--mode both]` runs these existing tools in order (doctor, build, verify, pack, scenario run, automatic shot check) and writes `make_report.md`. It adds no checks of its own and never reports a gameplay pass. The visual review (open every screenshot, fill `review.md`, then `shot_review.py <run> --check`) stays manual.

For an app from an idea, with no assess: `scaffold.py new-app <lua|js|python3|native-app|game|web> <slug>`. Script runtimes go through the SDK's `nxv new --store`. Native ones use the port skeleton with the kit `app` or `game` template. `web` is an HTML5 starter for the OS browser.

A step never claims more than its evidence: assess and verify are host checks; scenario runs are emulator checks; console rows stay `NOT_RUN` until a run on the console.

### Graphics: Vulkan

Vulkan counts as released from OS 1.4.0 (owner decision, `ownerReleased` in `platform/capabilities.json`). It is on by default. Check `NXN_CAP_VULKAN` at start and keep the GL path as the fallback. For an OS 1.4.0 target, `assess` routes Vulkan sources to native Vulkan with a GL fallback. `assess --os` and `doctor --os` (default: the snapshot's OS) send older OS targets to the GL path and say why. `nxn_vk.h` ships with SDK 1.16. Not tested on a device here.

New port skeletons get `loadingHint` and `fullscreenPause` in `app.json` and a `PORT.md` note on the OS performance panel (Ctrl+Alt+P). See [port experience](PORT_EXPERIENCE.md).

## 1. Research the target and options

Start with `port_studio.py assess <source-or-game-dir>` ([port assessment](PORT_ASSESSMENT.md)). It gives the verdict, the graphics route, the kit libraries, and a performance tier with its evidence level. Confirm every line in the source before you rely on it.

Identify the product, exact version and variants, original platform, expected workflow, and supported user data. Use an existing port directory if one exists. To create one, run `init game <slug> <category>` or `init software <slug> <category>`. See the [SDK publishing guide](../nexvyn_sdk/Publishing/PUBLISHING.md) for categories.

Use primary sources such as upstream repositories, licenses, release notes, build documentation, upstream ports, and SDK examples. In `PORT.md`, record each source URL, pinned revision, and evidence. Explain how users obtain the supported data from their own installation.

| Approach | Evidence required |
| --- | --- |
| Upstream source or open engine | License, supported data versions, buildable AArch64 dependencies, graphics, audio |
| Compatible reimplementation or static recompilation | Exact input version, portable runtime, feasibility prototype for key features and imports, redistribution basis |
| Compatibility layer or emulation | SDK support, measured performance, rights, user expectations |

Check graphics extensions, CPU, threads, memory, input, audio, storage, network/TLS, DRM and external services. Document the impact of gaps. Mark feasibility as viable, limited, or blocked and explain why. Prototype uncertain rendering, imports, or data loading. Preserve DRM and license checks.

## 2. Pin the SDK and deliver the core workflow

- Read the [SDK native port](../nexvyn_sdk/Guides/PORT_AND_LAUNCHER.md), [input](../nexvyn_sdk/Guides/INPUT_CONTRACT.md), [compatibility](../nexvyn_sdk/Guides/COMPATIBILITY.md), [quality](../nexvyn_sdk/Guides/PRODUCT_QUALITY.md), and [localization](../nexvyn_sdk/Guides/LOCALIZATION_CONTRACT.md) documents.
- Use [the Switch cross-compilation guide](CROSS_COMPILATION_CHEATSHEET.md) for the first build. Record the upstream commit, SDK snapshot, compiler version, build command, native ABI, and minimum and target SDK/OS versions. Use configurable paths. Track source and permissions in `DISTRIBUTION.md`.
- The first working slice should load data, run a real scene or primary application task, release its resources, and return to the desktop. Check actual imports and available capabilities. Explain any limited feature and implement a fallback where possible.
- Stage user data separately from the store payload. Use the user-selected data directory and state exactly which versions and files are supported. Save profiles and game saves in the app’s persistent data area.

## 3. Complete the port-specific experience

Apply the [launcher standard](PORT_LAUNCHER_STANDARD.md). Start with meaningful actions and settings the engine actually applies. Test defaults, handheld and dock profiles, controls, remapping, data selection, and persistence as one workflow.

## 4. Test and record evidence

| Scenario | What to verify |
| --- | --- |
| First launch, missing or incompatible data, reselect, cancel | Version check, actionable errors, safe return to the menu or desktop |
| Real gameplay or primary application task | Load time, frame time under load, peak memory, audio and graphics |
| Handheld → dock → handheld and live resize | Resolution, render scale, aspect ratio, touch mapping, session continuity |
| Gamepad, touch, keyboard and mouse, remapping | Menu and real usage, input changes, focus loss, stuck input, persistence |
| Suspend and resume, reopen, update | Audio and capture cleanup, saved data, long-running resource use |
| Localization | All SDK locales, long strings, CJK layout, visible errors |

Write the environment, OS and package version, data variant, and result in `PORT.md`. Record host checks, emulator observations, and physical Switch observations with their environments. Keep unavailable tests pending.

## 5. Prepare the two packages

Use the [release workflow](RELEASE_WORKFLOW.md) for the personal package, store bundle, release records and real screenshots, and read its "Field notes" first (package file-count and size limits, version bump, emulator taps, checking that the game reacts to a gesture before building it). Hand off output paths, passing checks, and known issues.
