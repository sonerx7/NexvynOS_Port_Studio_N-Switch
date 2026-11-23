# Release, personal package, and App Market

Build both channels from the same native module, application ID, code, and manifest version. Nexvyn OS updates packages with the same ID in place. Test save compatibility and transitions between channels and versions.

| Channel | Contents | Output |
| --- | --- | --- |
| Personal | The base port and user-supplied game or app data | `_RealesedBuilds/game/<slug>/<id>-<version>-local.nxvapp` or `_RealesedBuilds/software/<slug>/<id>-<version>-local.nxvapp` |
| App Market | Redistributable code, assets, and launcher. Users select original commercial data from their own installation. | `<port>/AppMarket/Store/<Games\|Apps>/<category>/<slug>/<slug>.nxvapp` |

## Prepare the port records and source bundle

- `PORT.md` records research, pinned upstream and SDK, build steps, and device evidence. `DISTRIBUTION.md` records sources, licenses, redistribution decisions, and user data requirements.
- `app.json` uses a stable reverse-domain ID and a `MAJOR.MINOR.PATCH` version. Add a matching section such as `## 1.2.0` to `CHANGELOG.md` and `KNOWN_ISSUES.md`. Record effects, conditions, workarounds, and verified environments. Follow the SDK’s data migration contract when changing `dataSchema`.
- `AppMarket/Store/<Games|Apps>/<category>/<slug>/` contains `source/`, an English setup and usage `README.md`, localized `store.json`, and numbered PNGs in `screenshots/`.
- `source/` contains only files listed explicitly in `port.json` under `publicFiles`, including `app.json`, the `.nxvmod`, icon, individual locale files, `LICENSE`, and `NOTICE.md`. No globs. Review permissions for the module, upstream code, translations, patches, icon, music, screenshots, and each data group. Technical validation also checks for private destinations, links, keys, commercial game extensions, and nested packages.
- Map needed files with `localData` entries such as `{"from":"installed-data","to":"game"}`. `from` is relative to `--data-root`. `to` is the path the launcher reads in the bundle. A directory mapping includes its entire subtree. Prefer narrow mappings when only a few files are needed. Use `localData: []` for ports that need no additional files. Store personal data outside the repository or under ignored `_LocalData/`.
- The store launcher must open to a useful data selection screen with no commercial data present. Document supported versions and required files. Link to downloads only when the source is legitimate and verified.
- Use `release.status: "blocked"` and concrete `release.reasons` while work remains. After actual usage, device acceptance, and redistribution rights are documented, set `ready`, clear the reasons, and set `release.version` to the reviewed manifest version. `check store` can validate a blocked submission. `pack store` and public archive preparation require release readiness for the same version.

## Capture screenshots and run checks

Capture three to five actual screenshots from the same release in English and crop them to the app. Name them `1.png`, `2.png`, and so on. Include a representative game scene or app result first, followed by the ready launcher or main workflow and a real menu, settings, or controls screen. Exclude desktops, personal paths, accounts, notifications, and debug overlays. Use content cleared for distribution.

When capture is pending, put three to five repeatable scenarios in `store.json`. These support technical validation while capture is pending. The store pack requires real PNGs.

Use [SDK nxvtest](../nexvyn_sdk/Tools/nxvtest/README.md) when an emulator and compatible OS build are available. Add `screenshot`, `expect_screenshot`, `expect_screenshots_differ`, and clean-exit assertions. Inspect the PNGs and keep the emulator test workspace in an ignored path such as `build_nxvtest/`.

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py check store GamePorts/my-game
python -X utf8 _PortStudioMain/tools/port_studio.py pack local GamePorts/my-game --data-root "D:/Games/MyGame"
python -X utf8 _PortStudioMain/tools/port_studio.py pack store GamePorts/my-game
```

The selected SDK validates the source, required locales, native identity, relocations and imports, package and SHA-256 manifest. Native checks need devkitA64. On Windows use `DEVKITPRO_WIN` if devkitPro is installed in a custom location. On other systems use `DEVKITPRO`. The SDK limits packages to 20,000 files and 1 GiB unpacked. Measure early and document anything that exceeds the limit.

The official store builds its package and catalog from the submission source. Run the [publishing guide](../nexvyn_sdk/Publishing/PUBLISHING.md), [store review](../nexvyn_sdk/Publishing/REVIEW.md), and the official OS store checks before a submission. Record device results and official approval independently of local packaging.

## Emulator test (Ryujinx + Nexvyn OS)

1. `python _PortStudioMain/tools/emulator_test.py check` reports Ryujinx, keys and Nexvyn OS. If Ryujinx is missing, install a build, start it once so it creates its keys/firmware folders, then set `RYUJINX_EXE` or pass `--ryujinx`.
2. `python _PortStudioMain/tools/emulator_test.py fetch-os` downloads the newest `NexvynOS.nro` (uses `gh` when installed).
3. `python _PortStudioMain/tools/emulator_test.py run GamePorts/<port> --app-id <id> --module <build>/<name>.nxvmod [--game-dir <data>] [--wait 40]` runs the launcher in an isolated `.emulator_profile/`, saves screenshots and the app log to `<port>/screenshots/`.
3b. `--mode docked|handheld|both` sets the emulator's console mode (Ryujinx `docked_mode`; its default here is docked, 1080p). Run `--mode both` for every launcher, layout or input change: handheld is 720p with touch, docked is 1080p with no touch screen, and each shows different bugs. The result line prints the mode that ran. The emulator does not show real frame pacing, power or thermal behaviour in either mode.
4. Record the result as an emulator check in `PORT.md`. It does not replace a physical Switch test.

## Field notes (from the Red Alert 2 and CS 1.6 runs)

- **Version bump for an in-place update.** Nexvyn OS replaces a package with the same ID only when the version is higher. Change `version` in `app.json` (the port copy and the `AppMarket/.../source/` copy, they must match), add the entry under the same version in `CHANGELOG.md` and `KNOWN_ISSUES.md` (the pack step rejects a version without a `KNOWN_ISSUES.md` section), then stage and pack. Delete the stale `-local.nxvapp` of the older version.
- **`lang/` drift.** `stage`/`build` refuse to run when `lang/*.json` differs from `AppMarket/.../source/lang/`. After editing a locale, copy it to the store source.
- **Local data root layout.** `pack local --data-root` reads each `localData[].from` relative to the root. A `from` may be a folder (`{"from": "cstrike", "to": "game/cstrike"}`), so a whole game directory needs two lines, not thousands. Junctions in the data root are refused: copy the files instead.
- **Limits.** The SDK allows 20,000 files and 1 GiB unpacked. Red Alert 2 plus Yuri's Revenge is 993 MiB with only the base game; bundles such as CnCNet or duplicate language archives do not fit. `pack` prints a note above 500 files, a stronger WARNING above 1,000 files (install may take very long or freeze), and a note near the size limit.
- **Many files freeze the install sheet.** The OS inspector hashes every file on the UI thread. Older builds called `unzLocateFile` per file, which rescans the whole zip (quadratic): a 5,944-file package sat on "Checking the package" for minutes, a 37-file one did not. The fix is in the OS source (`core/nxvpkg.cpp`, one forward pass); it was only syntax-checked, not built or run. Until a build with it is installed, prefer few large files, and test installs of big packages on the OS build you ship to.
- **Emulator runs.** `--module` is the path to the built `.nxvmod`, `--app-id` the reverse-DNS ID (`com.<owner>.<slug>`). Ryujinx runs with `--root-data-dir <Studio>/.emulator_profile`, so your own Ryujinx profile is untouched; to look at what a test installed, start Ryujinx with that flag and `_PortStudioMain/_EmulatorCache/NexvynOS.nro`.
- **Input injection.** `finger <id> down|move|up <x> <y>` takes pixels on a 1280x720 screen, one finger event at a time. A real or injected pinch therefore moves the two-finger centre by about half the distance change per event: do not classify gestures with a distance-to-centre ratio near 2.
- **What an emulator run proves.** With local data the game reached its main menu and the touch log lines appear. It does not prove in-game behaviour, speed or the physical Switch.
- **Named taps.** `--steps` accepts `tap NAME`; NAME comes from `port.json` `emulator.targets.NAME.<handheld|docked>` = `[x, y]` (pixels on the 1280x720 screen). Add `play`, menu buttons and tabs there so scenarios do not hard-code coordinates. The launcher window can open maximized or windowed between runs, so the Play button has had two positions (`play` and `play_maximized` in Red Alert 2); tap both before a long wait.
- **Check the engine before building input plumbing.** Red Alert 2: the pinch to mouse-wheel path worked (log: `touch wheel +120`/`-120`), yet the game ignores the wheel, so no zoom exists. A skirmish run with before/after screenshots settled it in minutes. Run that check first and mark the action `unsupported` in `port.json` (the how-to text then drops it) instead of documenting a gesture that does nothing.
- **Classify multi-finger gestures from net movement.** Finger events arrive one finger at a time, so accumulated absolute distance change makes a parallel two-finger drag look like a pinch. Decide only after both fingers have moved, from the change since touch-down (`main.c`, `g2f` code in Red Alert 2).
- **Stale logs fake passes.** `emulator_test.py` now deletes the app log before each run; an earlier session read a log from a previous run and could not tell whether new lines had arrived.
- **Test deploys what the package ships.** The tool copies every `publicFiles` entry that exists in the port folder (logos, art, locales). Before, `assets/logo.nximg` was missing in emulator runs and looked like a launcher bug.
- **Version bump.** `port_studio.py bump <port> <version>` edits both `app.json` files, the CMake project version and adds the CHANGELOG and KNOWN_ISSUES headings.
