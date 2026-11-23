# Porting playbook

The target is an integrated AArch64 native application for Nexvyn OS on Nintendo Switch. Start with [FIRST_RUN.md](../../FIRST_RUN.md). For an existing port, run `bootstrap --port <port>` and read its `PORT.md`.

## 1. Research the target and options

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
