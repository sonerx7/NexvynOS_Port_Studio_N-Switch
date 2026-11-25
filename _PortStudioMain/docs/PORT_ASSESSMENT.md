# Port assessment

Answer "can this be ported, and how well will it run?" before any build work.

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py assess <source-or-game-dir> --name <title> --out _LocalData/<slug>_assessment.md
python -X utf8 _PortStudioMain/tools/port_studio.py assess <dir> --json            # schemaVersion 2, same data as the Markdown
python -X utf8 _PortStudioMain/tools/port_studio.py assess <folder-of-sources> --batch   # one comparison row per subfolder
```

The tool reads source, build and licence files, executable import strings, file names and the size of a game data folder. It never runs code or uses the network. A large tree takes about 20 s. Every finding names its evidence as `file:line`.

## What the report gives

| Section | Content |
| --- | --- |
| Verdict | `viable`: no blocker or limit found. `limited`: works with the named work or reduced scope. `blocked`: a hard blocker, with the reason and the ways around it (replace, write a library, port a runtime, rewrite piecewise, pick a better runtime). `unknown`: nothing readable. Neither "possible" nor "impossible" is claimed without evidence. |
| Source type | game, app, emulator, engine, software, web, tool, decomp or library, with score and evidence. The rules are data in [`platform/source_types.json`](../platform/source_types.json): a new type is one data edit. |
| Detections | Languages (tool/test/vendored code counted separately), build systems, licence (`unknown` when not recognised), engines, graphics API, audio, input, network/TLS, DRM, x86 SIMD, 32-bit pointer casts, JIT, dlopen, fork/exec, fixed mappings, thread-creation sites against the two worker cores, large allocations, texture formats, data size and file count against the package limits |
| Recommendation | Run mode (native windowed SDL2/GL, NexGFX, CPU surface, or a script/web/Java/Game Engine runtime), kit template, libraries ready or to build, OS settings (`memory`, `loadingHint`, `minNative 1.1`, `liveResize`, `windowedLibs`/`windowedJit` when relevant), OS APIs, performance tier and experience profile (`heavy` for tier 4), and a reference port. Only `released` items appear here. |
| Preview options | Preview libraries, APIs and settings (and Vulkan for a target OS older than 1.4.0), each marked `private-preview`: never the only path |
| Work list | Each task rated easy, medium or hard with a rough duration (an estimate) |
| Staged plan | For heavy sources (tier 4, more than 2000 native files, or heavy applications): core, graphics, audio, input, save, localization, package. Each stage has an acceptance criterion, a duration and a risk. |
| Performance | The tier, the evidence level behind it, the starting render scale and fps cap, and the rules that apply |

Code under `tools/`, `tests/`, `third_party/`, `vendor/` and similar folders is listed separately and does not change the verdict. Risk patterns count only in compiled languages. Detection is pattern-based: a match inside a comment still counts, so confirm each line.

Next steps after the report: `scaffold.py` turns the JSON report into a port folder, and `verify.py` checks the build (see the [playbook flow](INSTANT_PORT_PLAYBOOK.md#the-flow-in-one-view)).

## How to use the verdict

- Paste the report into `PORT.md` under **Research and feasibility** and confirm each line in the source. The scan is a hint list, not proof.
- `limited` or `unknown`: build the one-frame prototype the report names before you promise anything.
- `blocked`: record the blocker evidence and test the narrowest workaround first.
- Performance lines are **estimates**. Replace them with emulator measurements (`scenario_run.py`, both modes), and later with console numbers, each with its environment.
- Presets start docked at render scale 1.0 at 1080p. For tier 3-4 games, start docked at the report's scale (0.5-0.67) and record the change in `port.json` `experience.performance`.

## Platform facts

[`platform/capabilities.json`](../platform/capabilities.json) holds every platform fact the report uses. Each fact carries:

- a status: `released` (in the public SDK Studio builds against), `private-preview` (announced, not in a public release) or `planned`;
- an evidence level: `console`, `emulator`, `host` or `documented`.

Only `released` facts drive a production route. Preview items appear in their own report lines. The rules live in `tools/assess.py`; the facts stay in the JSON.

The facts as of 2026-11-25 (SDK 1.16, OS 1.4.0):

- **GL path:** GL 4.3 core / GLES 3.2 is the released default and has console evidence.
- **Vulkan 1.3:** released from OS 1.4.0 (owner decision, `ownerReleased` in `capabilities.json`), on by default when the driver check at start passes. Older OS builds have no Vulkan: `assess --os` (default: the SDK snapshot's OS) sends them to the GL path. `nxn_vk.h` ships with SDK 1.16. Check `NXN_CAP_VULKAN` and always keep the GL fallback. Vulkan cannot be judged in the emulator (NVK compute is wrong in Ryujinx).
- **Memory budget and worker core hint:** private-preview.
- **CPU, RAM and code memory:** apps get the main thread plus up to two worker cores (1 and 2; core 0 runs the shell, core 3 the system) and share 4 GiB with the OS, with no per-app guarantee. The kernel has 10 code-memory objects system-wide; each module takes 2 and each JIT buffer takes 1.
- **Console evidence:** frame rates are from OS 1.2.2 on the GL path only. JIT, the fault handler, guard pages and the RAM limits have no console run yet.

## Updating the facts

When a public Nexvyn OS release adds or changes something:

1. Read its release notes and the public SDK documentation.
2. Run `platform_refresh.py` (add `--from-local <os-checkout>` to mark what a development build adds as preview). It derives the source, versions, templates, `nxv_native` commands, kit recipes, API status, capability bits and device counters, and prints a diff. Apply it with `--write`. Then edit the hand-written facts in `platform/capabilities.json`: the value, its `status` and evidence level, `asOf` and `source`. Add new APIs to `newApis`. When a preview item ships publicly, change its status to `released`.
3. Add or adjust a rule in `assess.py` only when a new kind of decision is needed, and add a test in `test_assess.py`.
4. Run `python -m unittest discover -s _PortStudioMain/tools -p "test_*.py"`.

`doctor --json` reports `platformFacts`: the date of the facts and the APIs that are missing from the SDK snapshot.
