# Nexvyn SDK updates

Nexvyn OS, the general SDK, and the Native SDK have separate versions. Use the same snapshot to build, validate, and package a port. Record the SDK commit and versions in `sdk.lock.json` and the build evidence in `PORT.md`.

## Check for updates

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py updates --port GamePorts/<port>
```

Read-only. It compares this checkout's Nexvyn OS version with the newest public release (pre-releases are labelled), prints the SDK and Native versions, and, when `port.json` has `"updates": {"archiveItem": "<item>"}` (or `--archive-item`), compares the port's `release.version` with the newest `<slug>-<version>.nxvapp` on that Internet Archive item. It downloads nothing. To take an SDK update, continue below. A launcher that checks for updates by itself is not built yet: it needs the OS network API and a decision where the version list is published.

## Fresh clone or missing snapshot

The repository includes a ready-to-use public SDK. For an existing port with an unavailable locked snapshot, run `bootstrap --port <port> --fetch`. To retrieve an explicit update candidate:

```powershell
python -X utf8 _PortStudioMain/tools/sync_nexvyn_sdk.py --fetch <40-character-commit>
python -X utf8 _PortStudioMain/tools/port_studio.py doctor --json --sdk "_PortStudioMain/_SdkCandidates/<commit>"
```

The downloader fetches the fixed commit from the [official public repository](https://github.com/sonerx7/Nexvyn-OS-NX) and extracts its SDK to `_SdkCandidates/<commit>`. When the default SDK differs from a port’s lock, Studio looks for a matching local candidate. You can also select one with `--sdk <snapshot>`.

## Import from a local checkout

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py doctor --json --upstream "<Nexvyn-OS-NX checkout>"
python -X utf8 _PortStudioMain/tools/sync_nexvyn_sdk.py --from-checkout "<clean public checkout>" --stage
python -X utf8 _PortStudioMain/tools/port_studio.py doctor --json --sdk "<candidate snapshot>"
```

The checkout’s origin must point to the official SDK repository. `doctor --upstream` compares local metadata without using the network. `--record-active` checks the SDK files against the checkout before writing the source record. Two commits can share version numbers while having different contents.

## Verify and promote an update

1. Look at the candidate with `doctor`. Review SDK/ABI changes and identify the port changes and device tests they require.
2. Adjust the port’s SDK lock in an isolated copy. Verify the manifest’s minimum and target versions against the SDK compatibility contract. For a new port, `init --sdk "<candidate>"` writes the lock.
3. Run a clean native build, `check-win`, locale validation, and personal package checks. Test the target OS on a device. For a release-ready port, also verify its store package. Build companion dependencies such as the windowed SDL2 sysroot from the same SDK.
4. Record the results in `PORT.md` and the release notes. To replace the repository’s default snapshot, run `sync_nexvyn_sdk.py --from-checkout "<tested checkout>"`. The previous snapshot is backed up under `_SdkBackups/`. Keep the candidate or use `--sdk "<backup>"` for ports pinned to the previous commit.
5. Review `git status --short --untracked-files=all` before sharing the updated SDK. If Git ignores an upstream template or official sample archive, scope the ignore exception to the affected SDK path.
