#!/usr/bin/env python3
"""Nexvyn Port Studio setup, verification, and local packaging."""

import argparse
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile
from zlib import crc32


ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "_PortStudioMain"
SDK = STUDIO / "nexvyn_sdk"
STUDIO_VERSION = "0.3.0"
SDK_REPOSITORY = "sonerx7/Nexvyn-OS-NX"
SDK_SOURCE = "STUDIO_SOURCE.json"
NXV = SDK / "Tools/nxv/nxv.py"
NATIVE_TOOLS = SDK / "Languages/c/native-kit/tools"
PACKER = NATIVE_TOOLS / "nxvapp_pack.py"
NATIVE = NATIVE_TOOLS / "nxv_native/__main__.py"
SDK_BUILD_FILES = (
    "Languages/c/native-kit/sdk/native/toolchain/nexvyn-switch.cmake",
    "Languages/c/native-kit/sdk/native/templates/game/CMakeLists.txt",
    "Languages/c/native-kit/sdk/native/lib/Makefile",
)
PORT_TYPES = {"GamePorts": ("game", "Games"), "SoftwarePorts": ("software", "Apps")}
STORE_CATEGORIES = {
    "Games": {"action", "arcade", "board", "cards", "casual", "puzzle", "racing", "sports", "strategy", "word"},
    "Apps": {"productivity", "utilities", "media", "internet", "developer", "system", "switch", "other"},
}
VERSION = r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}"
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
APP_ID = r"[a-z][a-z0-9-]*(?:\.[a-z0-9][a-z0-9_-]*){2,}"
RELEASE_ROOT = "_RealesedBuilds"
PRIVATE_SUFFIXES = {
    ".exe", ".dll", ".msi", ".zip", ".rar", ".7z", ".tar", ".gz", ".xz",
    ".iso", ".rom", ".nsp", ".xci", ".nxvapp", ".pem", ".key", ".pfx", ".p12",
    ".csf", ".mix", ".mpq", ".wad", ".pak", ".vpk", ".bsp", ".bik", ".smk",
}
PRIVATE_DIRS = {"_localdata", "userdata", "private", "saves"}
FORBIDDEN_DIRS = {"__pycache__", "dist", "appmarket", "_realesedbuilds", "build"}
FORBIDDEN_NAMES = {"manifest.sha256", "manifest.sig", "id_rsa", "id_ed25519", "desktop.ini", "thumbs.db"}


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON nesnesi bekleniyor.")
    return data


def relative_path(value):
    if not isinstance(value, str):
        raise ValueError("File path must be a string.")
    parts = value.split("/")
    for part in parts:
        if (
            not part or part.startswith(".") or part.endswith((" ", "."))
            or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
            or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL"}
            or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", part.split(".")[0].upper())
        ):
            raise ValueError(f"Not a safe relative package path: {value!r}")
    return PurePosixPath(value)


def check_path(path, *, missing_ok=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return
        raise
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"Links and junctions are not allowed: {path}")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ValueError(f"Expected a regular file or folder: {path}")


def under(base, rel, *, missing_ok=False):
    current = base
    for part in rel.parts:
        current /= part
        check_path(current, missing_ok=missing_ok)
    return current


def port_path(value):
    raw = Path(os.path.abspath(value))
    if raw.parent.parent != ROOT or raw.parent.name not in PORT_TYPES:
        raise ValueError("Select a port directly under GamePorts or SoftwarePorts.")
    check_path(raw.parent)
    check_path(raw)
    if not raw.is_dir():
        raise ValueError(f"Port folder not found: {raw}")
    return raw


def list_files(base, relative=None):
    directory = base if relative is None else base / relative
    for item in sorted(directory.iterdir()):
        rel = relative_path(item.name) if relative is None else relative / relative_path(item.name)
        check_path(item)
        if item.is_dir():
            yield from list_files(base, rel)
        else:
            yield rel


def check_payload_name(path, *, public):
    names = {part.casefold() for part in path.parts}
    suffix = path.suffix.casefold()
    if names & (FORBIDDEN_DIRS | FORBIDDEN_NAMES) or suffix in {".pem", ".key", ".pfx", ".p12", ".nxvapp"}:
        raise ValueError(f"Cannot be used as a package entry: {path}")
    if public and (names & PRIVATE_DIRS or suffix in PRIVATE_SUFFIXES):
        raise ValueError(f"Cannot be added to the Store source: {path}")


def unique_paths(paths):
    seen = {}
    files = set()
    for path in paths:
        folded = path.as_posix().casefold()
        if folded in files:
            raise ValueError(f"Paket yolu yineleniyor: {path}")
        files.add(folded)
        for item in (*path.parents, path):
            key = item.as_posix().casefold()
            if seen.setdefault(key, item) != item:
                raise ValueError(f"Case collision in package paths: {item}")
    for path in paths:
        if any(parent.as_posix().casefold() in files for parent in path.parents):
            raise ValueError(f"File/folder collision in package path: {path}")


def copy_files(entries, destination):
    for rel, source in entries.items():
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def write_atomic(target, content):
    check_path(target, missing_ok=True)
    with tempfile.TemporaryDirectory(prefix=".port-studio-", dir=target.parent) as work:
        candidate = Path(work) / target.name
        candidate.write_text(content, encoding="utf-8", newline="\n")
        os.replace(candidate, target)


def sdk_call(tool, *args):
    if not tool.is_file():
        raise ValueError(f"Local public SDK tool is missing: {tool}")
    env = None
    if os.name != "nt" and "DEVKITPRO" not in os.environ:
        env = {**os.environ, "DEVKITPRO": str(devkit_path())}
    elif os.name == "nt" and "DEVKITPRO_WIN" in os.environ:
        bash = devkit_path() / "msys2/usr/bin/bash.exe"
        if bash.is_file() and "DKP_BASH" not in os.environ:
            env = {**os.environ, "DKP_BASH": str(bash)}
    result = subprocess.run([sys.executable, "-B", str(tool), *map(str, args)], env=env)
    if result.returncode:
        raise ValueError(f"SDK check failed: {tool.name} (exit {result.returncode})")


def sdk_paths(snapshot):
    return (
        snapshot / NXV.relative_to(SDK),
        snapshot / NATIVE.relative_to(SDK),
        snapshot / PACKER.relative_to(SDK),
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
        "tools": {str(path.relative_to(snapshot)): path.is_file() for path in sdk_paths(snapshot)},
        "missingSdkFiles": [name for name in SDK_BUILD_FILES if not (snapshot / name).is_file()],
        "invalidSdkMetadata": invalid,
    }


def sdk_pin(port):
    pin = read_json(port / "sdk.lock.json")
    commit = pin.get("commit")
    if pin.get("repository") != SDK_REPOSITORY or not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("sdk.lock.json: the official SDK source and a full Git commit ID are required.")
    for name in ("sdk", "native"):
        if not isinstance(pin.get(name), str) or not pin[name].strip():
            raise ValueError(f"sdk.lock.json: {name} version is required.")
    return pin


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
    if report["repository"] != SDK_REPOSITORY or not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        return f"Invalid SDK source record: {SDK_SOURCE}."
    if pin and any(pin[name] != value for name, value in (
        ("commit", commit), ("sdk", versions.get("sdk")), ("native", versions.get("native")),
    )):
        return (
            f"Port requires commit {pin['commit']} (SDK {pin['sdk']} / Native {pin['native']}). "
            "Select the matching snapshot with --sdk or run bootstrap --port <port> --fetch."
        )
    return None


def select_sdk(override=None, pin=None):
    if override:
        return override.resolve()
    if pin and sdk_problem(sdk_report(SDK), pin):
        candidate = STUDIO / "_SdkCandidates" / pin["commit"]
        if candidate.is_dir():
            return candidate
    return SDK


def devkit_path():
    if os.name == "nt":
        return Path(os.environ.get("DEVKITPRO_WIN", "C:/devkitPro"))
    return Path(os.environ.get("DEVKITPRO", "/opt/devkitpro"))


def doctor_report(port, snapshot, pin, checkout=None):
    report = sdk_report(snapshot)
    report["sdkProblem"] = sdk_problem(report, pin)
    report["studioVersion"] = STUDIO_VERSION
    import experience
    report["experienceSchema"] = experience.CURRENT_SCHEMA
    if port is not None and (port / "port.json").is_file():
        block = json.loads((port / "port.json").read_text(encoding="utf-8-sig")).get("experience")
        report["portExperience"] = None if block is None else {"schema": block.get("schema"), "profile": block.get("profile")}
    if checkout:
        report["upstreamVersions"] = read_json(checkout / "SDK/VERSION.json")
        head = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True,
        )
        report["upstreamCommit"] = head.stdout.strip()
        report["matchesUpstreamCommit"] = (
            report["commit"] == report["upstreamCommit"] if report["commit"] else None
        )
    if port:
        report["port"] = str(port.relative_to(ROOT))
        report["portSdkCommit"] = pin["commit"] if pin else None
        report["portConfigured"] = (port / "port.json").is_file()
        if report["portConfigured"]:
            slug, category, paths, _ = config_for(port)
            source = store_item(port, slug, category) / "source"
            report["missingPackageFiles"] = [rel.as_posix() for rel in paths if not (source / rel).is_file()]
            report["release"] = release_status(port)
            report["buildInputsMissing"] = missing_build_inputs(port)
    windows = os.name == "nt"
    devkit = devkit_path()
    report["toolchain"] = {
        name: shutil.which(name) for name in ("git", "cmake", "ninja")
    }
    report["toolchain"]["cmake"] = report["toolchain"]["cmake"] or (
        str(devkit / "msys2/usr/bin/cmake.exe") if windows and (devkit / "msys2/usr/bin/cmake.exe").is_file() else None
    )
    report["toolchain"]["devkitA64"] = (
        devkit / "devkitA64/bin" / ("aarch64-none-elf-gcc.exe" if windows else "aarch64-none-elf-gcc")
    ).is_file()
    if windows:
        bash = Path(os.environ.get("DKP_BASH", str(devkit / "msys2/usr/bin/bash.exe")))
        report["toolchain"]["devkitBash"] = str(bash) if bash.is_file() else None
    else:
        report["toolchain"]["make"] = shutil.which("make")
        report["toolchain"]["sh"] = shutil.which("sh")
    return report


def doctor(args):
    port = port_path(args.port) if args.port else None
    pin = sdk_pin(port) if port and (port / "sdk.lock.json").is_file() else None
    report = doctor_report(port, select_sdk(args.sdk, pin), pin, args.upstream)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["sdkProblem"] else 0


def environment_warnings(port):
    """Non-fatal findings that cost previous ports hours. Each line says what to do."""
    notes = []
    if os.name == "nt" and len(str(STUDIO)) > 60 and not os.environ.get("NEXVYN_SYSROOT_CACHE"):
        notes.append("Long Studio path (" + str(len(str(STUDIO))) + " characters): sysroot builds can fail with "
                     "'opening dependency file ... No such file'. Set NEXVYN_SYSROOT_CACHE=C:/nxc before building the sysroot.")
    if not (os.environ.get("RYUJINX_EXE") or shutil.which("Ryujinx") or shutil.which("Ryujinx.exe")):
        notes.append("Ryujinx not found: emulator tests need it. Run emulator_test.py check for setup steps.")
    if port is not None:
        try:
            import experience
            block = read_json(port / "port.json").get("experience")
            if block is None:
                notes.append("port.json has no experience block. Run: port_studio.py analyze <data-or-source-dir>, "
                             "then experience init " + port.name + " <profile>.")
            else:
                problems = experience.validate(experience.resolve({"experience": block}))
                notes.extend("experience: " + problem for problem in problems)
        except (ValueError, OSError) as error:
            notes.append(f"experience: {error}")
    return notes


def bootstrap(args):
    port = port_path(args.port) if args.port else None
    pin = sdk_pin(port) if port and (port / "sdk.lock.json").is_file() else None
    snapshot = select_sdk(args.sdk, pin)
    if args.fetch and sdk_problem(sdk_report(snapshot), pin):
        if not pin:
            raise ValueError("--fetch needs a --port with an SDK lock. See SDK_UPDATES.md to fetch an explicit commit.")
        sync_tool = STUDIO / "tools/sync_nexvyn_sdk.py"
        result = subprocess.run([sys.executable, str(sync_tool), "--fetch", pin["commit"]])
        if result.returncode:
            raise ValueError("Unable to fetch the pinned SDK. See SDK_UPDATES.md for the local checkout method.")
        snapshot = select_sdk(pin=pin)
    report = doctor_report(port, snapshot, pin)
    problem = report["sdkProblem"]
    if problem:
        raise ValueError(problem)
    versions = report["versions"]
    print(f"SDK {versions['sdk']} / Native {versions['native']} / OS {versions['os']}")
    print(f"SDK commit {report['commit']} ({snapshot})")
    required_tools = ("git", "cmake", "devkitA64") + (("devkitBash",) if os.name == "nt" else ("make", "sh"))
    missing = [name for name in required_tools if not report["toolchain"][name]]
    missing.extend(report.get("buildInputsMissing", []))
    if report.get("missingPackageFiles"):
        print("Missing package files: " + ", ".join(report["missingPackageFiles"]))
    if report.get("release", {}).get("status") == "blocked":
        print("Release blocked: " + " ".join(report["release"]["reasons"]))
    for note in environment_warnings(port):
        print("Warning: " + note)
    if missing:
        raise ValueError("Missing build prerequisites: " + ", ".join(missing)
                         + ". See FIRST_RUN.md and the port's PORT.md.")
    print("Environment check passed. Continue with FIRST_RUN.md.")
    return 0


def config_for(port):
    config = read_json(under(port, PurePosixPath("port.json")))
    slug = config.get("slug")
    category = config.get("storeCategory")
    public_files = config.get("publicFiles")
    data = config.get("localData")
    if not isinstance(slug, str) or not re.fullmatch(SLUG, slug):
        raise ValueError("port.json: slug must consist of lowercase letters, digits and hyphens.")
    store_type = PORT_TYPES[port.parent.name][1]
    if not isinstance(category, str) or category not in STORE_CATEGORIES[store_type]:
        raise ValueError(f"port.json: storeCategory options: {', '.join(sorted(STORE_CATEGORIES[store_type]))}")
    if not isinstance(public_files, list) or not public_files or not isinstance(data, list):
        raise ValueError("port.json: publicFiles must be a non-empty list and localData must be a list.")
    mappings = []
    for mapping in data:
        if not isinstance(mapping, dict) or set(mapping) != {"from", "to"}:
            raise ValueError("localData entries must contain from and to fields.")
        origin, target = relative_path(mapping["from"]), relative_path(mapping["to"])
        check_payload_name(target, public=False)
        mappings.append((origin, target))
    return slug, category, [relative_path(path) for path in public_files], mappings


def store_item(port, slug, category):
    store_type = PORT_TYPES[port.parent.name][1]
    return under(port, relative_path(f"AppMarket/Store/{store_type}/{category}/{slug}"))


def release_status(port):
    release = read_json(port / "port.json").get("release")
    if release is None:
        return {"status": "blocked", "reasons": ["Release approval is missing from port.json."]}
    if not isinstance(release, dict) or release.get("status") not in ("blocked", "ready"):
        raise ValueError("port.json: release.status must be blocked or ready.")
    reasons = release.get("reasons")
    if not isinstance(reasons, list) or any(not isinstance(reason, str) or not reason.strip() for reason in reasons):
        raise ValueError("port.json: release.reasons must be a list of strings.")
    if bool(reasons) != (release["status"] == "blocked"):
        raise ValueError("port.json: blocked needs at least one reason, ready needs an empty list.")
    version = release.get("version")
    if release["status"] == "ready" and (not isinstance(version, str) or not re.fullmatch(VERSION, version)):
        raise ValueError("port.json: a ready release requires release.version in MAJOR.MINOR.PATCH format.")
    return release


def require_release(port, version=None):
    release = release_status(port)
    if release["status"] != "ready":
        raise ValueError("Distribution blocked: " + " ".join(release["reasons"]))
    if version is not None and release["version"] != version:
        raise ValueError(f"Release review covered {release['version']}. Review version {version} before distribution.")


def build_config(port):
    build = read_json(port / "port.json").get("build", {})
    if (not isinstance(build, dict) or build.get("driver") not in (None, "sdk", "manual")
            or any(not isinstance(build.get(key, []), list) for key in ("files", "devkitFiles"))
            or not isinstance(build.get("environment", {}), dict)
            or any(not isinstance(files, list) for files in build.get("environment", {}).values())):
        raise ValueError("Invalid build configuration in port.json. See FIRST_RUN.md.")
    return build


def missing_build_inputs(port):
    build = build_config(port)
    missing = []
    for name in build.get("files", []):
        if not (port / relative_path(name)).is_file():
            missing.append(name)
    for variable, files in build.get("environment", {}).items():
        root = os.environ.get(variable)
        for name in files:
            if not root or not (Path(root) / relative_path(name)).exists():
                missing.append(f"{variable}/{name}")
    for name in build.get("devkitFiles", []):
        if not (devkit_path() / relative_path(name)).is_file():
            missing.append(f"devkitPro/{name}")
    return missing


def release_documents(port, version):
    for name in ("CHANGELOG.md", "KNOWN_ISSUES.md"):
        path = under(port, PurePosixPath(name))
        section = re.search(
            rf"^## (?:\[{re.escape(version)}\]|{re.escape(version)})(?=\s|$)[^\n]*\n(.*?)(?=^## |\Z)",
            path.read_text(encoding="utf-8-sig"), re.MULTILINE | re.DOTALL,
        )
        content = section.group(1).strip() if section else ""
        if not content or "<!--" in content:
            raise ValueError(f"{name}: ## {version} section with a release record is required.")
    for name in ("PORT.md", "DISTRIBUTION.md"):
        path = under(port, PurePosixPath(name))
        content = path.read_text(encoding="utf-8-sig")
        if not content.strip() or "<!-- PORT_STUDIO_TEMPLATE -->" in content:
            raise ValueError(f"{name}: complete the port's records and remove the template marker.")


def check_source_copies(port, entries):
    for rel, staged in entries.items():
        if rel.suffix == ".nxvmod":
            continue
        original = port / rel
        if original.is_file() and staged.read_bytes() != original.read_bytes():
            if rel.suffix in {".md", ".json", ".txt"} and (
                staged.read_text(encoding="utf-8-sig") == original.read_text(encoding="utf-8-sig")
            ):
                continue
            raise ValueError(f"Port and App Market source differ at {rel}. Synchronize the two files.")


def public_source(port, slug, category, paths, mappings):
    store_type = PORT_TYPES[port.parent.name][1]
    item = store_item(port, slug, category)
    source = under(item, PurePosixPath("source"))
    unique_paths(paths)
    for rel in paths:
        check_payload_name(rel, public=True)
        for _, target in mappings:
            public = rel.as_posix().casefold()
            private = target.as_posix().casefold()
            if public == private or public.startswith(private + "/") or private.startswith(public + "/"):
                raise ValueError(f"Store entry collides with a personal-data target: {rel}")
    actual = set(list_files(source))
    missing = set(paths) - actual
    extra = actual - set(paths)
    if missing or extra:
        changes = [*(f"missing: {p}" for p in sorted(missing)), *(f"not listed: {p}" for p in sorted(extra))]
        if any(path.suffix == ".nxvmod" for path in missing):
            changes.append("Native modules are generated. Follow the build and stage steps in PORT.md.")
        raise ValueError("The Store source must match the publicFiles list exactly:\n  " + "\n  ".join(changes))
    entries = {rel: source / rel for rel in paths}
    check_source_copies(port, entries)
    for notice in ("LICENSE", "NOTICE.md"):
        rel = PurePosixPath(notice)
        if rel not in entries or not entries[rel].read_text(encoding="utf-8-sig").strip():
            raise ValueError(f"A non-empty {notice} is required in the Store source.")
    manifest = read_json(under(source, PurePosixPath("app.json")))
    app_id, version = manifest.get("id"), manifest.get("version")
    if not isinstance(app_id, str) or len(app_id) > 128 or not re.fullmatch(APP_ID, app_id):
        raise ValueError("app.json: a permanent lowercase app ID is required (com.owner.port).")
    if not isinstance(version, str) or not re.fullmatch(VERSION, version):
        raise ValueError("app.json: version must be in MAJOR.MINOR.PATCH format.")
    if manifest.get("runtime") != "native" or manifest.get("mode") not in {"window", "fullscreen"}:
        raise ValueError("A Studio package must be an integrated native module running in window or fullscreen mode.")
    main = relative_path(manifest.get("main"))
    icon = relative_path(manifest.get("icon", "icon.png"))
    if main.suffix != ".nxvmod" or main not in entries or icon not in entries:
        raise ValueError("app.json: main (.nxvmod) and icon must be in the Store source list.")
    if store_type == "Games" and (manifest.get("category") != "games" or manifest.get("gamepad") is not True):
        raise ValueError('Oyun manifestinde "category": "games" ve "gamepad": true gerekli.')
    release_documents(port, version)
    return item, source, entries, main, app_id, version


def port_sdk(port, override):
    pin = sdk_pin(port)
    snapshot = select_sdk(override, pin)
    problem = sdk_problem(sdk_report(snapshot), pin)
    if problem:
        raise ValueError(problem)
    return snapshot


def check_manifest_sdk(sdk, manifest):
    versions = sdk_report(sdk)["versions"]
    for field, version in (("targetSdk", versions["sdk"]), ("targetNative", versions["native"])):
        if manifest.get(field) != version:
            raise ValueError(f"app.json: {field} must match the locked SDK ({version}).")


def build_or_stage(args):
    port = port_path(args.port)
    snapshot = port_sdk(port, args.sdk)
    nxv, native, _ = sdk_paths(snapshot)
    slug, category, paths, _ = config_for(port)
    source = under(store_item(port, slug, category), PurePosixPath("source"))
    manifest = read_json(under(source, PurePosixPath("app.json")))
    check_manifest_sdk(snapshot, manifest)
    main = relative_path(manifest.get("main"))
    if main.suffix != ".nxvmod" or main not in paths:
        raise ValueError("app.json: main (.nxvmod) must be in the publicFiles list.")
    entries = {rel: under(source, rel) for rel in paths if rel != main}
    check_source_copies(port, entries)
    module = args.module if args.action == "stage" else port / "build" / main
    if args.action == "build":
        if build_config(port).get("driver") != "sdk":
            raise ValueError("Use the custom build command in PORT.md, then run stage --module.")
        missing = missing_build_inputs(port)
        if missing:
            raise ValueError("Missing build prerequisites: " + ", ".join(missing))
        cache = port / "build/CMakeCache.txt"
        build_sdk = cache.with_name(".port-studio-sdk")
        commit = sdk_report(snapshot)["commit"]
        if build_sdk.is_file() and build_sdk.read_text(encoding="utf-8").strip() != commit:
            raise ValueError("build/ uses a different SDK commit. Move it aside and run the build again.")
        if cache.is_file():
            toolchain = snapshot / NATIVE_TOOLS.parent.relative_to(SDK) / "sdk/native/toolchain/nexvyn-switch.cmake"
            expected = toolchain.as_posix()
            allowed = {expected}
            if os.name == "nt" and toolchain.drive.endswith(":"):
                allowed = {expected.casefold(), f"/{expected[0].lower()}{expected[2:]}".casefold()}
            for line in cache.read_text(encoding="utf-8").splitlines():
                if line.startswith("CMAKE_TOOLCHAIN_FILE:"):
                    recorded = line.partition("=")[2].replace("\\", "/")
                    break
            else:
                recorded = ""
            if (recorded.casefold() if os.name == "nt" else recorded) not in allowed:
                raise ValueError("build/ uses a different SDK. Move it aside and run the build again.")
        sdk_call(native, "build", port)
        write_atomic(build_sdk, commit + "\n")
    if not module.is_file():
        raise ValueError(f"Native module not found: {module}")
    target = under(source, main, missing_ok=True)
    with tempfile.TemporaryDirectory(prefix=".port-studio-", dir=source.parent) as work:
        stage = Path(work) / "bundle"
        entries[main] = module
        copy_files(entries, stage)
        sdk_call(nxv, "check", stage)
        sdk_call(native, "check-win", stage / main)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage / main, target)
    print(f"Validated and staged module: {target.relative_to(ROOT)}")


def local_entries(root, mappings, public_paths):
    if bool(mappings) != bool(root):
        raise ValueError("--data-root is required when localData mappings exist. If no data is needed, leave both empty.")
    if not mappings:
        return {}
    base = Path(os.path.abspath(root))
    if not base.is_dir():
        raise ValueError(f"Local data folder not found: {base}")
    for ancestor in (*reversed(base.parents), base):
        check_path(ancestor)
    entries = {}
    destinations = list(public_paths)
    for origin, dest in mappings:
        source = under(base, origin)
        children = list(list_files(source)) if source.is_dir() else [None]
        if not children:
            raise ValueError(f"Local data folder is empty: {origin}")
        for child in children:
            target = dest if child is None else dest / child
            check_payload_name(origin if child is None else origin / child, public=False)
            check_payload_name(target, public=False)
            destinations.append(target)
            entries[target] = source if child is None else source / child
        count = 1 if child is None else len(children)
        size = sum(f.stat().st_size for f in ([source] if child is None else (source / c for c in children)))
        print(f"  local data: {origin} -> {dest}: {count:,} file(s), {size / (1 << 20):,.1f} MiB", file=sys.stderr)
    unique_paths(destinations)
    return entries


def store_metadata(item, slug, *, require_screenshots=False):
    required = {"source", "README.md", "store.json"}
    optional = {"screenshots", "icon.png", f"{slug}.nxvapp"}
    screenshot_names = set()
    for entry in item.iterdir():
        check_path(entry)
        if entry.name not in required | optional:
            raise ValueError(f"Unexpected entry in the Store submission folder: {entry.name}")
        if entry.name == "screenshots":
            for screenshot in list_files(entry):
                if len(screenshot.parts) != 1 or screenshot.suffix != ".png":
                    raise ValueError(f"Store screenshot must be a PNG file: {screenshot}")
                check_screenshot(entry / screenshot)
                screenshot_names.add(screenshot.name)
        elif entry.name != "source" and not entry.is_file():
            raise ValueError(f"Store entry must be a file: {entry.name}")
    for name in ("README.md", "store.json"):
        path = under(item, PurePosixPath(name))
        content = path.read_text(encoding="utf-8-sig")
        if not content.strip() or "PORT_STUDIO_TEMPLATE" in content:
            raise ValueError(f"Store information must be completed: {name}")
    metadata = read_json(item / "store.json")
    if metadata.get("kind") != "port":
        raise ValueError('The Store record requires "kind": "port".')
    shots = metadata.get("shots")
    if require_screenshots and (
        not 3 <= len(screenshot_names) <= 5
        or screenshot_names != {f"{index}.png" for index in range(1, len(screenshot_names) + 1)}
    ):
        raise ValueError("A Store package requires 3-5 consecutive real screenshots starting with 1.png.")
    if len(screenshot_names) < 3 and (
        not isinstance(shots, list) or not 3 <= len(shots) <= 5 or any(not shot for shot in shots)
    ):
        raise ValueError("The Store requires at least three screenshots or 3-5 SDK capture scenarios.")


def check_screenshot(path):
    error = ValueError(f"Invalid store screenshot: {path.name}")
    with path.open("rb") as image:
        if image.read(8) != b"\x89PNG\r\n\x1a\n":
            raise error
        header = image.read(25)
        if len(header) != 25 or header[:8] != b"\x00\x00\x00\rIHDR":
            raise error
        width, height = struct.unpack_from(">II", header, 8)
        if not width or not height or crc32(header[4:-4]) != int.from_bytes(header[-4:], "big"):
            raise error
        has_data = False
        while chunk := image.read(8):
            if len(chunk) != 8:
                raise error
            length, kind = struct.unpack(">I4s", chunk)
            checksum = crc32(kind)
            remaining = length
            while remaining:
                block = image.read(min(remaining, 1024 * 1024))
                if not block:
                    raise error
                checksum = crc32(block, checksum)
                remaining -= len(block)
            expected = image.read(4)
            if len(expected) != 4 or checksum != int.from_bytes(expected, "big"):
                raise error
            if kind == b"IDAT" and length:
                has_data = True
            if kind == b"IEND":
                if length == 0 and has_data and image.read(1) == b"":
                    return
                break
    raise error


def check_package_limits(files, label):
    if len(files) > 20_000 or sum(entry.file_size for entry in files) > 1 << 30:
        raise ValueError(f"{label}: exceeds the Nexvyn OS limits of 20,000 files or 1 GiB unpacked.")
    size = sum(entry.file_size for entry in files)
    count = len(files)
    if count > 1000:
        print(f"WARNING: {label} has {count:,} files. Installing it may take very long and the Nexvyn OS install "
              "sheet can freeze on \"Checking the package\" (older OS builds rescan the zip for every file; a 5,944-file "
              "package sat there for minutes, a 37-file one did not). Merge or drop files, or let the player pick "
              "the data folder instead of bundling it. Test the install on the OS build you ship to.", file=sys.stderr)
    elif count > 500:
        print(f"Note: {label} has {count:,} files. Install checks slow down as the count grows; above 1,000 files the "
              "install sheet can appear frozen. Prefer fewer, larger files.", file=sys.stderr)
    if size > 0.9 * (1 << 30):
        print(f"Note: {label} unpacks to {size / (1 << 20):,.0f} MiB, close to the 1 GiB limit. Drop optional data first.",
              file=sys.stderr)


def prepare(args):
    port = port_path(args.port)
    snapshot = port_sdk(port, args.sdk)
    nxv, native, packer = sdk_paths(snapshot)
    if args.channel == "store" and args.action == "pack":
        require_release(port)
    slug, category, paths, mappings = config_for(port)
    item, source, entries, main, app_id, version = public_source(port, slug, category, paths, mappings)
    check_manifest_sdk(snapshot, read_json(source / "app.json"))
    if args.channel == "store":
        if getattr(args, "data_root", None):
            raise ValueError("--data-root cannot be used with a Store package.")
        if args.action == "pack":
            require_release(port, version)
        store_metadata(item, slug, require_screenshots=args.action == "pack")
    if args.action == "check":
        sdk_call(nxv, "check", item if args.channel == "store" else source)
        sdk_call(native, "check-win", source / main)
        print(f"Source validation passed: {app_id} {version} ({args.channel})")
        return

    if args.channel == "local":
        personal = local_entries(args.data_root, mappings, entries)
        port_type = PORT_TYPES[port.parent.name][0]
        output_dir = under(ROOT, relative_path(f"{RELEASE_ROOT}/{port_type}/{slug}"), missing_ok=True)
        output = output_dir / f"{app_id}-{version}-local.nxvapp"
    else:
        personal = {}
        output_dir = item
        output = item / f"{slug}.nxvapp"
    # Verify a completed candidate before replacing an earlier build.
    output_dir.mkdir(parents=True, exist_ok=True)
    check_path(output, missing_ok=True)
    with tempfile.TemporaryDirectory(prefix=".port-studio-", dir=output_dir) as work:
        temp = Path(work)
        stage = temp / ("source" if args.channel == "store" else "bundle")
        candidate = Path(work) / "candidate.nxvapp"
        copy_files(entries, stage)
        if args.channel == "store":
            for metadata in ("store.json", "README.md"):
                shutil.copyfile(item / metadata, temp / metadata)
            if (item / "screenshots").is_dir():
                shutil.copytree(item / "screenshots", temp / "screenshots")
        sdk_call(nxv, "check", stage)
        sdk_call(native, "check-win", stage / main)
        copy_files(personal, stage)
        sdk_call(packer, stage, "-o", candidate)
        sdk_call(packer, "--verify", candidate)
        with ZipFile(candidate) as package:
            check_package_limits(package.infolist(), output.name)
        os.replace(candidate, output)
    print(f"Package ready: {output.relative_to(ROOT)}")


def init_port(args):
    name = relative_path(args.slug)
    if len(name.parts) != 1 or not re.fullmatch(SLUG, args.slug):
        raise ValueError("Port name must consist of lowercase letters, digits and hyphens.")
    port_type = "GamePorts" if args.kind == "game" else "SoftwarePorts"
    store_type = PORT_TYPES[port_type][1]
    if args.category not in STORE_CATEGORIES[store_type]:
        raise ValueError(f"Store categories: {', '.join(sorted(STORE_CATEGORIES[store_type]))}")
    parent = ROOT / port_type
    check_path(parent)
    report = sdk_report(select_sdk(args.sdk))
    problem = sdk_problem(report)
    if problem:
        raise ValueError(problem)
    port = parent / name
    port.mkdir()
    templates = STUDIO / "templates"
    for filename in ("PORT.md", "DISTRIBUTION.md", "CHANGELOG.md", "KNOWN_ISSUES.md"):
        shutil.copyfile(templates / filename, port / filename)
    config = {
        "slug": args.slug,
        "storeCategory": args.category,
        "publicFiles": ["app.json", f"{args.slug}.nxvmod", "icon.png", "LICENSE", "NOTICE.md"]
        + [f"lang/{locale}.json" for locale in report["versions"]["requiredLocales"]],
        "localData": [],
        "release": {"status": "blocked", "reasons": ["Feasibility and release acceptance are pending."]},
    }
    (port / "port.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    pin = {"repository": report["repository"], "commit": report["commit"]}
    pin.update({name: report["versions"][name] for name in ("sdk", "native")})
    (port / "sdk.lock.json").write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    item = port / "AppMarket" / "Store" / store_type / args.category / args.slug
    (item / "source").mkdir(parents=True)
    shutil.copyfile(templates / "STORE_README.md", item / "README.md")
    shutil.copyfile(templates / "store.json", item / "store.json")
    print(f"Port record created: {port.relative_to(ROOT)}/PORT.md")


def main():
    # These commands own their options (including --port), so hand them the rest unparsed.
    if len(sys.argv) > 1 and sys.argv[1] in ("updates", "analyze", "experience", "bump"):
        module = __import__(sys.argv[1])
        return module.main(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"Nexvyn Port Studio {STUDIO_VERSION}")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="Create feasibility and release records for a new port.")
    init.add_argument("kind", choices=("game", "software"))
    init.add_argument("slug")
    init.add_argument("category")
    init.add_argument("--sdk", type=Path)
    status = sub.add_parser("doctor", help="Report SDK, toolchain, and optional port status.")
    status.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    status.add_argument("--port")
    status.add_argument("--sdk", type=Path)
    status.add_argument("--upstream", type=Path, help="Local public OS checkout to compare.")
    setup = sub.add_parser("bootstrap", help="Verify the SDK and native build prerequisites.")
    setup.add_argument("--port")
    setup_source = setup.add_mutually_exclusive_group()
    setup_source.add_argument("--sdk", type=Path)
    setup_source.add_argument("--fetch", action="store_true", help="Retrieve the port's exact SDK commit if missing.")
    for action in ("build", "stage"):
        command = sub.add_parser(action, help={
            "build": "Build and stage an SDK CMake port.",
            "stage": "Validate and stage a custom build output.",
        }[action])
        command.add_argument("port")
        command.add_argument("--sdk", type=Path)
        if action == "stage":
            command.add_argument("--module", type=Path, required=True)
    up = sub.add_parser("updates", help="Check Nexvyn OS releases and a port's Internet Archive item (see updates.py).")
    up.add_argument("up_args", nargs=argparse.REMAINDER)
    an = sub.add_parser("analyze", help="Suggest an experience profile from a game or source folder (see analyze.py).")
    an.add_argument("an_args", nargs=argparse.REMAINDER)
    xp = sub.add_parser("experience", help="Input modes, gestures, performance profiles (see experience.py).")
    xp.add_argument("xp_args", nargs=argparse.REMAINDER)
    for action in ("check", "pack"):
        command = sub.add_parser(action)
        command.add_argument("channel", choices=("local", "store"))
        command.add_argument("port")
        command.add_argument("--sdk", type=Path)
        if action == "pack":
            command.add_argument("--data-root", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "init":
            init_port(args)
        elif args.action == "doctor":
            return doctor(args)
        elif args.action == "bootstrap":
            return bootstrap(args)
        elif args.action == "updates":
            import updates
            return updates.main(args.up_args)
        elif args.action == "analyze":
            import analyze
            return analyze.main(args.an_args)
        elif args.action == "experience":
            import experience
            return experience.main(args.xp_args)
        elif args.action in ("build", "stage"):
            build_or_stage(args)
        else:
            prepare(args)
    except (BadZipFile, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
