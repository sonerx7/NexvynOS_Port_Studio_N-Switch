# Port record

<!-- PORT_STUDIO_TEMPLATE -->

## Target

- Product, source platform, and version
- Primary workflow on Switch
- Supported data versions and required files

## Research and feasibility

| Source and revision | Evidence | Effect on the decision |
| --- | --- | --- |
| | | |

- Evaluated engines, source options, and alternatives
- AArch64, ABI/import, graphics, memory, audio, storage, input, DRM, and network requirements
- `assess` report: date, platform facts date, verdict, and which lines were confirmed or refuted in the source
- Graphics route (GL 4.3 core / GLES 3.2, optional Vulkan with a GL fallback, or a CPU surface) and why
  (Vulkan needs OS 1.4.0 / SDK 1.16 or later; on older OS targets use the GL path)
- Performance plan: tier, starting render scale and fps cap per mode, threads and cores, memory need (`app.json` `memory`)
- Prototype evidence and decision (viable, limited, or blocked)
- Upstream and SDK commits, compiler, build command, minimum and target OS/SDK, and ABI

## Launcher, settings, and controls

| Action or setting | Gamepad | Touch | Keyboard/mouse | Default, transitions, and persistence |
| --- | --- | --- | --- | --- |
| | | | | |

- Data selection, errors, and first launch
- Handheld and dock measurements, automatic profile, and transition conditions

## Verification

Mark each result with its level: host, emulator, or console.

| Scenario | Environment, OS, package, and data | Result and evidence |
| --- | --- | --- |
| First launch and missing/incompatible data | | |
| Gameplay or primary application task | | |
| Dock, handheld, and window transition | | |
| Input devices, remapping, and disconnect | | |
| Suspend, close, and update | | |
| Localization and real store screenshots | | |
