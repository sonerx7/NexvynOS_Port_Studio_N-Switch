"""Raise a port's version everywhere the pack step reads it.

  python _PortStudioMain/tools/port_studio.py bump GamePorts/<port> <new-version> [--dry-run]

Changes, in the port folder: app.json and every AppMarket/**/source/app.json ("version"), the
`project(... VERSION x)` line of CMakeLists.txt when it has one, and adds an empty heading for the
new version to CHANGELOG.md and KNOWN_ISSUES.md (pack refuses a version without a KNOWN_ISSUES
section). Nexvyn OS updates a package with the same ID only when the version is higher.
It does not touch store.json or port.json release.version: those need real text and a review.
"""

import argparse
import re
import sys
from pathlib import Path

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?$")
APP_VERSION = re.compile(r'("version"\s*:\s*")([^"]+)(")')


def read(path):
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


def write(path, text):
    path.write_bytes(text.encode("utf-8"))


def insert_heading(text, heading, body):
    match = re.search(r"^## ", text, re.M)
    if not match:
        return text.rstrip("\n") + f"\n\n{heading}\n\n{body}\n"
    return text[:match.start()] + f"{heading}\n\n{body}\n\n" + text[match.start():]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("port", type=Path)
    parser.add_argument("version")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    port = args.port if args.port.is_absolute() else Path.cwd() / args.port
    if not SEMVER.match(args.version):
        print(f"Error: {args.version!r} is not a version like 1.2.3.", file=sys.stderr)
        return 1
    app_json = port / "app.json"
    if not app_json.is_file():
        print(f"Error: {app_json} not found.", file=sys.stderr)
        return 1
    current = APP_VERSION.search(read(app_json)).group(2)
    key = lambda v: tuple(int(n) for n in re.findall(r"\d+", v)[:3])
    if key(args.version) <= key(current):
        print(f"Error: {args.version} is not higher than the current {current}.", file=sys.stderr)
        return 1
    done = []

    def change(path, text, label):
        done.append(f"{label}: {path.relative_to(port)}")
        if not args.dry_run:
            write(path, text)

    for path in [app_json, *sorted(port.glob("AppMarket/**/source/app.json"))]:
        text = read(path)
        new, n = APP_VERSION.subn(lambda m: m.group(1) + args.version + m.group(3), text, count=1)
        if n:
            change(path, new, "version")
    cmake = port / "CMakeLists.txt"
    if cmake.is_file():
        text = read(cmake)
        new, n = re.subn(r"(project\([^)]*?VERSION\s+)[0-9][0-9A-Za-z.\-]*", lambda m: m.group(1) + args.version, text, count=1)
        if n:
            change(cmake, new, "cmake")
    changelog = port / "CHANGELOG.md"
    if changelog.is_file():
        text = read(changelog)
        first = re.search(r"^## (.*)$", text, re.M)
        if first and f"## {args.version}" not in text and f"[{args.version}]" not in text:
            title = re.sub(re.escape(current), args.version, first.group(0), count=1) if current in first.group(0) else f"## {args.version}"
            change(changelog, insert_heading(text, title, "- TODO: describe what changed for the player."), "changelog")
    issues = port / "KNOWN_ISSUES.md"
    if issues.is_file():
        text = read(issues)
        if not re.search(rf"^## {re.escape(args.version)}\s*$", text, re.M):
            change(issues, insert_heading(text, f"## {args.version}", "- TODO: carry forward or update the known issues for this version."), "known issues")
    print(f"{'Would change' if args.dry_run else 'Changed'} ({current} -> {args.version}):")
    for line in done:
        print("  " + line)
    print("Still yours: fill the two TODO lines, review store.json (changelog text) and port.json release.version, "
          "then `stage` and `pack local`. Delete the older -local.nxvapp afterwards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
