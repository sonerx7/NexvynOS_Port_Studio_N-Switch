# Start here

New contributors and coding agents start here. Run commands from the repository root. You need Python 3.10+, Git, CMake, and devkitPro with the `switch-dev` package for Switch builds. Install any additional devkitPro packages listed in the port's `PORT.md`. On Windows, Studio uses devkitPro MSYS2. Set `DEVKITPRO_WIN` for a custom installation and `DKP_BASH` if Bash is in a separate location. On Linux, set `DEVKITPRO` and put the build tools on `PATH`. See the [SDK Native Kit installation guide](_PortStudioMain/nexvyn_sdk/Guides/NATIVE_KIT.md#install).

## 1. Check your environment

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py doctor --json
python -X utf8 _PortStudioMain/tools/port_studio.py bootstrap
```

A fresh clone includes the public SDK. `doctor` reports the SDK version, source commit, and tools. `bootstrap` exits with an error if required build inputs are missing. Generated package files can be missing until the port is built and staged.

For an existing port, pass its path:

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py bootstrap --port GamePorts/cs16 --fetch
python -X utf8 _PortStudioMain/tools/port_studio.py doctor --json --port GamePorts/RedAlert2
```

`--fetch` retrieves the exact commit from the port’s `sdk.lock.json` when the matching SDK is unavailable locally. It prepares a candidate alongside the default SDK. Use the [SDK update guide](_PortStudioMain/docs/SDK_UPDATES.md) to import a clean local checkout, try a newer commit, or promote an approved candidate. If a build dependency is missing, you can still read the port record, inspect the source, and work on issues that do not depend on that tool.

## 2. Choose a port

| Task | Next step |
| --- | --- |
| Counter-Strike 1.6 | Read the [port record](GamePorts/cs16/PORT.md). Use `build GamePorts/cs16` to compile and stage the launcher preview. The engine integration is pending. |
| Red Alert 2 / Yuri’s Revenge | Use the [port record](GamePorts/RedAlert2/PORT.md#build-from-a-fresh-checkout) to prepare pcrecomp, the generated lift, and the windowed SDL2 sysroot. In the shell that has `PCRECOMP` and `NEXVYN_SYSROOT` set, run `bootstrap --port GamePorts/RedAlert2` before building. |
| New game or application | Create the port record with `init`, then follow the [porting playbook](_PortStudioMain/docs/INSTANT_PORT_PLAYBOOK.md). |

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py init game my-game strategy
python -X utf8 _PortStudioMain/tools/port_studio.py init software my-tool utilities
```

`init` writes the SDK lock, release records, and store structure. Identify the supported product version and legitimate data source. Record upstream commits, licenses, Switch constraints, and the engine decision in `PORT.md`. Verify the riskiest assumption with a native prototype. Then deliver the core gameplay or application workflow, port-specific controls, localization, and runtime tests.

## 3. Verify and hand off

1. Read `sdkProblem`, `buildInputsMissing`, `missingPackageFiles`, and `release` in `doctor --json --port <port>`. A fresh clone lacks the generated `.nxvmod` until you build it.
2. For an SDK CMake port, run `build <port>`. For a custom build, follow its `PORT.md` and run `stage <port> --module <output>`.
3. Run `check store <port>` for technical validation. Follow the [release workflow](_PortStudioMain/docs/RELEASE_WORKFLOW.md) for the personal package, distribution review, screenshots, and runtime tests. Change `release.status` to `ready` and set `release.version` to the reviewed version once the requested experience, device acceptance, and distribution rights are documented.
4. Report SDK and upstream commits, package paths, checks that passed, and remaining blockers. Record whether the test ran on the host, in an emulator, or on a physical Switch.
