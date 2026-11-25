#!/usr/bin/env python3
"""Update the SDK snapshot from an authorized local public checkout."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

from port_studio import (
    SDK, SDK_BUILD_FILES, SDK_REPOSITORY, SDK_SOURCE, STUDIO, check_path, read_json, sdk_paths,
    sdk_problem, sdk_report, under, write_atomic,
)


REQUIRED = (
    "README.md", "VERSION.json", "Tools/nxv/nxv.py",
    "Guides/PORT_AND_LAUNCHER.md", "Publishing/PUBLISHING.md",
    "Languages/c/native-kit/tools/nxvapp_pack.py", "Languages/c/native-kit/tools/nxwin_imports.py",
    "Languages/c/native-kit/tools/nxv_native/__main__.py",
    *SDK_BUILD_FILES,
)


def git(checkout, *args):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], encoding="utf-8", errors="replace"
    ).strip()


def rename_snapshot(source, target):
    # Windows filesystem observers may briefly hold a handle after SDK verification.
    for delay in (0.1, 0.2, 0.4, 0.8, 1.6):
        try:
            source.rename(target)
            return
        except PermissionError:
            if os.name != "nt":
                raise
            time.sleep(delay)
    source.rename(target)


def sync(checkout, *, stage=False, record_active=False, verify_tools=True):
    checkout = checkout.resolve(strict=True)
    source = under(checkout, PurePosixPath("SDK"))
    if source.is_relative_to(STUDIO) or STUDIO.is_relative_to(source):
        raise ValueError("Select a clean Nexvyn OS checkout outside Studio.")
    commit = git(checkout, "rev-parse", "--verify", "HEAD")
    origin = git(checkout, "config", "--get", "remote.origin.url")
    if origin.removesuffix(".git").casefold() not in {
        f"https://github.com/{SDK_REPOSITORY}".casefold(),
        f"git@github.com:{SDK_REPOSITORY}".casefold(),
        f"ssh://git@github.com/{SDK_REPOSITORY}".casefold(),
    }:
        raise ValueError(f"The source checkout's origin must be the official {SDK_REPOSITORY} repository.")
    if git(checkout, "status", "--porcelain", "--untracked-files=all", "--", "SDK"):
        raise ValueError("The source checkout's SDK tree has local changes.")
    for name in REQUIRED:
        if not under(source, PurePosixPath(name)).is_file():
            raise ValueError(f"Source SDK file is missing: {name}")
    versions = read_json(source / "VERSION.json")
    for name in ("os", "sdk", "native"):
        if not isinstance(versions.get(name), str) or not versions[name].strip():
            raise ValueError(f"SDK VERSION.json field is missing: {name}")
    # Take the SDK files tracked in Git. Ignored local files do not leak into the snapshot.
    tracked = git(checkout, "ls-files", "-z", "--", "SDK").split("\0")
    relative = [PurePosixPath(name).relative_to("SDK") for name in tracked if name]
    if not relative or any(not under(source, name).is_file() for name in relative):
        raise ValueError("The SDK tree has a Git entry that is missing or not a regular file.")
    provenance = json.dumps({"repository": SDK_REPOSITORY, "commit": commit}, indent=2) + "\n"
    lock = STUDIO / "_temp_sdk_sync.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError(f"Another SDK update is running or a stale lock remains: {lock}") from None
    try:
        check_path(SDK, missing_ok=True)
        if record_active:
            if not SDK.is_dir():
                raise ValueError("There is no active SDK snapshot.")
            for name in relative:
                active = under(SDK, name).read_bytes()
                upstream = (source / name).read_bytes()
                if active != upstream and (
                    (name.suffix not in {".md", ".json", ".py", ".txt", ".h", ".c", ".cpp", ".cmake"})
                    or active.replace(b"\r\n", b"\n") != upstream.replace(b"\r\n", b"\n")
                ):
                    raise ValueError(f"The active SDK does not match the source: {name}")
            if (git(checkout, "rev-parse", "--verify", "HEAD") != commit
                    or git(checkout, "status", "--porcelain", "--untracked-files=all", "--", "SDK")):
                raise ValueError("The SDK checkout changed during verification.")
            write_atomic(SDK / SDK_SOURCE, provenance)
            print(f"Active SDK content verified against source commit {commit}.")
            return
        with tempfile.TemporaryDirectory(prefix="_temp_sdk_sync_", dir=STUDIO) as scratch:
            candidate = Path(scratch) / "sdk"
            for name in relative:
                target = candidate / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, target)
            if (git(checkout, "rev-parse", "--verify", "HEAD") != commit
                    or git(checkout, "status", "--porcelain", "--untracked-files=all", "--", "SDK")):
                raise ValueError("The SDK checkout changed during copying.")
            (candidate / SDK_SOURCE).write_text(provenance, encoding="utf-8")
            problem = sdk_problem(sdk_report(candidate))
            if problem:
                raise ValueError(problem)
            if verify_tools:
                for tool in sdk_paths(candidate):
                    subprocess.run([sys.executable, "-B", str(tool), "--help"], check=True, stdout=subprocess.DEVNULL)
            if stage:
                candidates = STUDIO / "_SdkCandidates"
                check_path(candidates, missing_ok=True)
                candidates.mkdir(exist_ok=True)
                target = candidates / commit
                check_path(target, missing_ok=True)
                if target.exists():
                    if (target / SDK_SOURCE).is_file() and all(
                        under(target, name, missing_ok=True).is_file()
                        and (target / name).read_bytes() == (candidate / name).read_bytes()
                        for name in relative
                    ) and (target / SDK_SOURCE).read_text(encoding="utf-8") == provenance:
                        print(f"SDK candidate is already ready: {target}")
                        return
                    raise ValueError(f"The existing candidate does not match the source. Inspect and archive it: {target}")
                rename_snapshot(candidate, target)
                print(f"SDK candidate ready: {target}")
                return
            install_candidate(candidate)
    finally:
        lock.rmdir()
    print(f"Fetched SDK {versions['sdk']} / Native {versions['native']}. Source commit {commit}.")


def install_candidate(candidate):
    """Make a checked candidate the active SDK; the previous one is kept in _SdkBackups."""
    backup = None
    if SDK.exists():
        backups = STUDIO / "_SdkBackups"
        check_path(backups, missing_ok=True)
        backups.mkdir(exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix="sdk-", dir=backups)) / SDK.name
        rename_snapshot(SDK, backup)
    try:
        rename_snapshot(candidate, SDK)
    except OSError:
        if backup is not None:
            rename_snapshot(backup, SDK)
        raise
    if backup is not None:
        print(f"Previous SDK kept: {backup}")


def version_key(text):
    numbers = [int(n) for n in re.findall(r"\d+", str(text or "").lstrip("v").split("-")[0])[:3]]
    return (*(numbers + [0] * (3 - len(numbers))), 0 if "-" in str(text or "") else 1)


def newest_os_release(os_checkout):
    """(version, folder) of the newest build/release-<version>/ in the OS development checkout, or (None, None)."""
    folders = [p for p in Path(os_checkout).glob("build/release-*") if (p / "NexvynOS.nro").is_file()]
    if not folders:
        return None, None
    best = max(folders, key=lambda p: version_key(p.name[len("release-"):]))
    return best.name[len("release-"):], best


def sync_os_release(os_checkout, public_checkout):
    """Owner-approved pre-release: the OS's own release export (tools/release.py sync_sdk, with its public-text filter)
    runs into a throwaway clone of the public SDK repository; the result becomes the active SDK. The source record says
    `owner-prerelease` with the OS commit, never an official commit. Replace it with --fetch once the release is public."""
    os_checkout = Path(os_checkout).resolve(strict=True)
    public_checkout = Path(public_checkout).resolve(strict=True)
    version, _ = newest_os_release(os_checkout)
    if not version:
        raise ValueError("The OS checkout has no build/release-<version>/NexvynOS.nro.")
    os_commit = git(os_checkout, "rev-parse", "--verify", "HEAD")
    base = git(public_checkout, "rev-parse", "--verify", "HEAD")
    with tempfile.TemporaryDirectory(prefix="_temp_sdk_prerelease_", dir=STUDIO) as scratch:
        clone = Path(scratch) / "public"
        subprocess.run(["git", "clone", "--quiet", str(public_checkout), str(clone)], check=True)
        script = ("import sys, json; sys.path.insert(0, 'tools'); import release; release.sync_sdk(); "
                  "print(json.dumps(release.leak_check()))")
        out = subprocess.run([sys.executable, "-X", "utf8", "-c", script], cwd=os_checkout, capture_output=True, text=True,
                             encoding="utf-8", env={**os.environ, "RELEASE_REPO": str(clone)})
        if out.returncode != 0:
            raise ValueError("The OS release export failed: " + (out.stderr or out.stdout).strip()[-400:])
        problems = [p for p in json.loads(out.stdout.strip().splitlines()[-1]) if "SDK/" in p]
        if problems:
            raise ValueError("The exported SDK has private content: " + "; ".join(problems[:5]))
        source = clone / "SDK"
        versions = read_json(source / "VERSION.json")
        if versions.get("os") != version:
            raise ValueError(f"Exported SDK says OS {versions.get('os')}, the release build is {version}.")
        candidate = Path(scratch) / "sdk"
        for path in sorted(source.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                target = candidate / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        provenance = {"repository": "owner-prerelease", "commit": os_commit,
                      "prerelease": {"os": version, "sdk": versions.get("sdk"), "publicBase": base,
                                     "method": "OS tools/release.py sync_sdk over the public repository HEAD",
                                     "replaceWith": "port_studio.py sdk-update once the release is on GitHub"}}
        (candidate / SDK_SOURCE).write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        problem = sdk_problem(sdk_report(candidate))
        if problem:
            raise ValueError(problem)
        for tool in sdk_paths(candidate):
            subprocess.run([sys.executable, "-B", str(tool), "--help"], check=True, stdout=subprocess.DEVNULL)
        install_candidate(candidate)
    print(f"Active SDK {versions['sdk']} / Native {versions['native']} (OS {version}, owner pre-release; OS commit {os_commit[:12]}).")


FRESHNESS_CACHE = STUDIO / "_EmulatorCache" / "public_release.json"
FRESHNESS_SECONDS = 3600


def public_latest():
    """(tag, commit) of the newest public release, or (None, None) when offline. Cached for an hour so doctor stays fast."""
    try:
        cached = json.loads(FRESHNESS_CACHE.read_text(encoding="utf-8"))
        if time.time() - cached.get("at", 0) < FRESHNESS_SECONDS:
            return cached.get("tag"), cached.get("sha")
    except (OSError, ValueError):
        pass
    tag, sha = _public_latest_uncached()
    if tag:
        FRESHNESS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        FRESHNESS_CACHE.write_text(json.dumps({"at": time.time(), "tag": tag, "sha": sha}), encoding="utf-8")
    return tag, sha


def _public_latest_uncached():
    try:
        tag = subprocess.run(["gh", "release", "list", "-R", SDK_REPOSITORY, "--limit", "1", "--json", "tagName",
                              "-q", ".[0].tagName"], capture_output=True, text=True, timeout=30).stdout.strip()
        if not tag:
            return None, None
        sha = subprocess.run(["gh", "api", f"repos/{SDK_REPOSITORY}/commits/{tag}", "-q", ".sha"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return tag, sha if re.fullmatch(r"[a-f0-9]{40}", sha or "") else None
    except (OSError, subprocess.SubprocessError):
        return None, None


def auto_update(os_checkout=None, public_checkout=None, dry_run=False):
    """Rule: the active SDK is always the newest one. A newer public release wins (official commit); otherwise a newer
    local OS release build is imported as an owner pre-release. Returns a one-line decision."""
    active = sdk_report(SDK)["versions"].get("os") if SDK.is_dir() else None
    choices = []
    tag, sha = public_latest()
    if tag and sha:
        choices.append((version_key(tag), "public", tag, sha))
    if os_checkout and Path(os_checkout).is_dir():
        version, _ = newest_os_release(os_checkout)
        if version:
            choices.append((version_key(version), "os-release", version, None))
    newer = [c for c in choices if c[0] > version_key(active)]
    if not newer:
        return f"SDK is current (OS {active})."
    best = max(newer, key=lambda c: (c[0], c[1] == "public"))
    if dry_run:
        return f"Newer SDK available: OS {best[2]} ({best[1]}); active OS {active}."
    if best[1] == "public":
        fetch(best[3])
        with tempfile.TemporaryDirectory(prefix="_temp_sdk_public_", dir=STUDIO) as scratch:
            copy = Path(scratch) / "sdk"
            shutil.copytree(STUDIO / "_SdkCandidates" / best[3], copy)
            install_candidate(copy)
        return f"Updated SDK to public OS {best[2]} (official commit {best[3][:12]})."
    if not public_checkout:
        raise ValueError("Set publicCheckout in _LocalData/studio_local.json (a clone of the public SDK repository).")
    sync_os_release(os_checkout, public_checkout)
    return f"Updated SDK to OS {best[2]} (owner pre-release)."


def local_paths():
    """Machine paths from the git-ignored _LocalData/studio_local.json (osCheckout, publicCheckout)."""
    try:
        return json.loads((STUDIO.parent / "_LocalData" / "studio_local.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fetch(commit):
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("--fetch requires a full Git commit ID.")
    target = STUDIO / "_SdkCandidates" / commit
    check_path(target.parent, missing_ok=True)
    check_path(target, missing_ok=True)
    if target.is_dir():
        report = sdk_report(target)
        if not sdk_problem(report) and report["commit"] == commit:
            print(f"SDK candidate is already ready: {target}")
            return
        raise ValueError(f"The existing SDK candidate could not be verified. Inspect and archive it: {target}")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    with tempfile.TemporaryDirectory(prefix="port-studio-sdk-") as scratch:
        checkout = Path(scratch)
        for command in (
            ("init", "--quiet"),
            ("remote", "add", "origin", f"https://github.com/{SDK_REPOSITORY}.git"),
            ("sparse-checkout", "set", "SDK"),
            ("fetch", "--quiet", "--no-tags", "--depth=1", "--filter=blob:none", "origin", commit),
            ("checkout", "--quiet", "--detach", commit),
        ):
            subprocess.run(["git", "-C", str(checkout), *command], check=True, env=env)
        if git(checkout, "rev-parse", "--verify", "HEAD") != commit:
            raise ValueError("The fetched SDK checkout does not match the requested commit.")
        sync(checkout, stage=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-checkout", type=Path)
    source.add_argument("--fetch", metavar="COMMIT", help="Fetch the pinned commit from the official source as an SDK candidate.")
    source.add_argument("--from-os-release", type=Path, metavar="OS_CHECKOUT",
                        help="Owner pre-release: export the newest local OS release build's SDK and make it active.")
    source.add_argument("--auto", action="store_true", help="Update to the newest SDK (public release or local OS release).")
    source.add_argument("--from-local", type=Path, metavar="OS_CHECKOUT",
                        help="Compare a local OS development checkout's native kit with the released snapshot (read-only; "
                             "--stage writes a private-preview candidate that build and pack refuse). See sdk_local.py.")
    parser.add_argument("--json", action="store_true", help="With --from-local: machine-readable comparison.")
    parser.add_argument("--public", type=Path, metavar="PUBLIC_CHECKOUT",
                        help="Clone of the public SDK repository (default: publicCheckout in _LocalData/studio_local.json).")
    parser.add_argument("--check", action="store_true", help="With --auto: only report whether a newer SDK exists.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--stage", action="store_true", help="Create a candidate without changing the active SDK.")
    modes.add_argument("--record-active", action="store_true", help="Write the commit record if the current snapshot matches.")
    args = parser.parse_args()
    if args.fetch and (args.stage or args.record_active):
        parser.error("--fetch produces a candidate on its own.")
    if args.from_local and args.record_active:
        parser.error("--from-local never records an active SDK.")
    try:
        if args.from_local:
            import sdk_local
            result = sdk_local.compare(args.from_local, SDK)
            if args.json:
                printable = {k: v for k, v in result.items() if k != "privateFiles"}
                print(json.dumps(printable, indent=2))
            else:
                print(sdk_local.render(result))
            if args.stage:
                print(f"Preview candidate (private-preview, not for builds): {sdk_local.stage(result, SDK, STUDIO / '_SdkCandidates')}")
            else:
                print("Nothing was written. Use --stage for a preview candidate.")
            return 0
        local = local_paths()
        if args.auto:
            print(auto_update(local.get("osCheckout"), args.public or local.get("publicCheckout"), dry_run=args.check))
            return 0
        if args.from_os_release:
            sync_os_release(args.from_os_release, args.public or local.get("publicCheckout") or "")
            return 0
        if args.fetch:
            fetch(args.fetch)
        else:
            sync(args.from_checkout, stage=args.stage, record_active=args.record_active)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
