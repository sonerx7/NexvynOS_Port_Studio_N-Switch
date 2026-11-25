"""SDK snapshot metadata: report, lock file, and problem checks; no studio globals."""

import re
from pathlib import PurePosixPath

from studio_files import read_json


SDK_REPOSITORY = "sonerx7/Nexvyn-OS-NX"
SDK_SOURCE = "STUDIO_SOURCE.json"
SDK_BUILD_FILES = (
    "Languages/c/native-kit/sdk/native/toolchain/nexvyn-switch.cmake",
    "Languages/c/native-kit/sdk/native/templates/game/CMakeLists.txt",
    "Languages/c/native-kit/sdk/native/lib/Makefile",
)


# Tool locations inside an SDK snapshot.
NXV_PATH = PurePosixPath("Tools/nxv/nxv.py")
NATIVE_TOOLS_PATH = PurePosixPath("Languages/c/native-kit/tools")
PACKER_PATH = NATIVE_TOOLS_PATH / "nxvapp_pack.py"
NATIVE_PATH = NATIVE_TOOLS_PATH / "nxv_native/__main__.py"


def sdk_paths(snapshot):
    return (
        snapshot / NXV_PATH,
        snapshot / NATIVE_PATH,
        snapshot / PACKER_PATH,
    )


def sdk_report(snapshot):
    metadata, invalid = {}, []
    for name in ("VERSION.json", SDK_SOURCE):
        path = snapshot / name
        try:
            metadata[name] = read_json(path) if path.is_file() else {}
        except (OSError, ValueError):
            metadata[name] = {}
            invalid.append(name)
    versions, provenance = metadata["VERSION.json"], metadata[SDK_SOURCE]
    return {
        "path": str(snapshot), "versions": versions, "commit": provenance.get("commit"),
        "repository": provenance.get("repository"),
        "prerelease": provenance.get("prerelease"),
        "tools": {str(path.relative_to(snapshot)): path.is_file() for path in sdk_paths(snapshot)},
        "missingSdkFiles": [name for name in SDK_BUILD_FILES if not (snapshot / name).is_file()],
        "invalidSdkMetadata": invalid,
    }


def sdk_pin(port):
    pin = read_json(port / "sdk.lock.json")
    commit = pin.get("commit")
    if not valid_source(pin.get("repository"), commit, {"os": pin.get("os", "prerelease")} if pin.get("repository") == PRERELEASE else None):
        raise ValueError("sdk.lock.json: the official SDK source and a full Git commit ID are required.")
    for name in ("sdk", "native"):
        if not isinstance(pin.get(name), str) or not pin[name].strip():
            raise ValueError(f"sdk.lock.json: {name} version is required.")
    return pin


PRERELEASE = "owner-prerelease"


def valid_source(repository, commit, prerelease=None):
    """Official public SDK commit, or an owner-approved pre-release of an OS release that is not on GitHub yet."""
    if not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        return False
    if repository == SDK_REPOSITORY:
        return True
    return repository == PRERELEASE and isinstance(prerelease, dict) and bool(prerelease.get("os"))


def sdk_problem(report, pin=None):
    versions, commit = report["versions"], report["commit"]
    if report["invalidSdkMetadata"]:
        return "Unreadable SDK metadata: " + ", ".join(report["invalidSdkMetadata"])
    if not versions or report["missingSdkFiles"] or not all(report["tools"].values()):
        return "SDK files are missing. Restore the bundled SDK or retrieve the pinned commit using SDK_UPDATES.md."
    locales = versions.get("requiredLocales")
    if (any(not isinstance(versions.get(key), str) or not versions[key] for key in ("os", "sdk", "native"))
            or not isinstance(locales, list) or not locales
            or any(not isinstance(locale, str) or not re.fullmatch(r"[a-z]{2}(?:-[A-Za-z0-9]+)*", locale) for locale in locales)):
        return "SDK VERSION.json has invalid version or locale metadata."
    if not valid_source(report["repository"], commit, report.get("prerelease")):
        return f"Invalid SDK source record: {SDK_SOURCE}."
    if pin and any(pin[name] != value for name, value in (
        ("commit", commit), ("sdk", versions.get("sdk")), ("native", versions.get("native")),
    )):
        return (
            f"Port requires commit {pin['commit']} (SDK {pin['sdk']} / Native {pin['native']}). "
            "Select the matching snapshot with --sdk or run bootstrap --port <port> --fetch."
        )
    return None
