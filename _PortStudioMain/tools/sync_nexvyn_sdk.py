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
    finally:
        lock.rmdir()
    print(f"Fetched SDK {versions['sdk']} / Native {versions['native']}. Source commit {commit}.")


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
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--stage", action="store_true", help="Create a candidate without changing the active SDK.")
    modes.add_argument("--record-active", action="store_true", help="Write the commit record if the current snapshot matches.")
    args = parser.parse_args()
    if args.fetch and (args.stage or args.record_active):
        parser.error("--fetch produces a candidate on its own.")
    try:
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
