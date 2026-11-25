# Nexvyn SDK updates

Nexvyn OS, the general SDK, and the Native SDK have separate versions. Use the same snapshot to build, validate, and package a port. Record the SDK commit and versions in `sdk.lock.json` and the build evidence in `PORT.md`.

## Check for updates

```powershell
python -X utf8 _PortStudioMain/tools/port_studio.py updates --port GamePorts/<port>
```

Read-only. It compares this checkout's Nexvyn OS version with the newest public release (pre-releases are labelled), prints the SDK and Native versions, and, when `port.json` has `"updates": {"archiveItem": "<item>"}` (or `--archive-item`), compares the port's `release.version` with the newest `<slug>-<version>.nxvapp` on that Internet Archive item. It downloads nothing. To take an SDK update, continue below. A launcher that checks for updates by itself is not built yet: it needs the OS network API and a decision where the version list is published.

## Preview features from a local development checkout

Only the official public repository can become the active SDK. To see what an unreleased OS build adds, compare a local development checkout:

```powershell
python -X utf8 _PortStudioMain/tools/sync_nexvyn_sdk.py --from-local "<os-checkout>"          # read-only report
python -X utf8 _PortStudioMain/tools/sync_nexvyn_sdk.py --from-local "<os-checkout>" --stage  # preview candidate
```

- **Report (read-only):** for each kit folder (include, lib, loader, sysroot, compat, templates, toolchain) it lists the files that are identical, differ only in comments, changed, new or missing, plus the new ABI functions. It reads tracked files at the checkout's HEAD only. Prebuilt libraries, build output, tests, ports, canaries and documentation are never compared.
- **`--stage`:** writes `_SdkCandidates/preview-<commit>/` (git-ignored). This is the released snapshot plus the changed public-kit files: headers, templates, toolchain files, sysroot recipes and patches, compat sources, loader. Its `STUDIO_SOURCE.json` has `"status": "private-preview"`, so `build`, `check` and `pack` refuse it. Use it only to read headers and plan. The checkout path is not written anywhere.
- **ABI rule:** a checkout that removes an ABI v1 function is refused (ABI v1 is add-only).

APIs that exist only in development show up in `doctor --json` under `platformFacts.missingInSnapshot`, and preview candidates under `previewCandidates`. `doctor` also compares the installed devkitA64 gcc with the snapshot's `toolchain.json` (`toolchainVersions`).

### When a preview feature ships publicly

1. Run `updates` to see the new public release.
2. Run `sync_nexvyn_sdk.py --fetch <commit>` (or `--from-checkout`).
3. Run `doctor --json --sdk <candidate>`. `missingInSnapshot` should shrink.
4. Run all tests.
5. Run `platform_refresh.py`, then `--write`. API, template, recipe and command statuses move from `private-preview` to `released` by themselves once the snapshot declares them. Review the hand-written facts ([port assessment](PORT_ASSESSMENT.md#updating-the-facts)).
6. Delete the old `preview-*` candidate.

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

## Always the newest SDK

Run `python _PortStudioMain/tools/port_studio.py sdk-update` (or check with `sync_nexvyn_sdk.py --auto --check`). A newer public release wins and is fetched by its official commit. When the newest build is a local OS release (`build/release-<version>/` in the OS development checkout, path in the git-ignored `_LocalData/studio_local.json` as `osCheckout`, with `publicCheckout` for a clone of the public SDK repository), its SDK is exported by the OS release tool and becomes the active SDK as an owner pre-release. Its `STUDIO_SOURCE.json` names the OS commit and `"repository": "owner-prerelease"`; replace it with the official commit once the release is on GitHub. `doctor --json` reports `sdkFreshness`. Earlier snapshots stay in `_SdkBackups/`.

