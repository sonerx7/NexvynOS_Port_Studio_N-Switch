"""Update check: Nexvyn OS / SDK releases and a port's Internet Archive item.

  python _PortStudioMain/tools/updates.py [--port GamePorts/<port>] [--archive-item ITEM] [--json]

Read-only. It only asks public servers (GitHub releases of the official Nexvyn OS repository,
archive.org item metadata) and compares what they say with this checkout. It never downloads
or replaces anything: to take an SDK update follow SDK_UPDATES.md, to publish a port release
follow RELEASE_WORKFLOW.md. The port can name its archive item in port.json:

  "updates": { "archiveItem": "my-nexvyn-port" }

Archive files follow the Port Market name <slug>-<version>.nxvapp, so the newest version is read
from the file names. Needs `curl` or `gh` (the Python SSL store is not used: it fails on some
Windows setups).
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
OS_REPO = "sonerx7/Nexvyn-OS-NX"
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:[-.]([0-9A-Za-z.]+))?")


def fetch_json(url):
    """GET a JSON document with curl, so the system certificate store is used."""
    curl = shutil.which("curl")
    if not curl:
        raise ValueError("curl is needed for the update check.")
    result = subprocess.run([curl, "-s", "-L", "-m", "20", "-H", "User-Agent: nexvyn-port-studio", url],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"Could not reach {url} (curl exit {result.returncode}).")
    try:
        return json.loads(result.stdout or "null")
    except ValueError:
        raise ValueError(f"{url} did not answer with JSON.") from None


def version_key(text):
    """Sortable key: numbers first; a pre-release (-beta.2) sorts below its release."""
    match = VERSION.search(text.lstrip("v"))
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    pre_key = (0, pre) if pre else (1, "")
    return (int(major), int(minor), int(patch), pre_key)


def os_report(local):
    releases = fetch_json(f"https://api.github.com/repos/{OS_REPO}/releases?per_page=10")
    if not isinstance(releases, list) or not releases:
        raise ValueError("No Nexvyn OS releases found.")
    stable = [r for r in releases if not r.get("prerelease")]
    newest = max(releases, key=lambda r: version_key(r["tag_name"]) or (0,))
    newest_stable = max(stable, key=lambda r: version_key(r["tag_name"]) or (0,)) if stable else None
    local_key = version_key(local)
    return {
        "local": local,
        "newest": newest["tag_name"], "newestIsPrerelease": bool(newest.get("prerelease")),
        "newestStable": newest_stable["tag_name"] if newest_stable else None,
        "behind": bool(local_key and version_key(newest["tag_name"]) and version_key(newest["tag_name"]) > local_key),
        "published": newest.get("published_at"),
    }


def archive_report(item, slug, local_version):
    meta = fetch_json(f"https://archive.org/metadata/{item}")
    files = (meta or {}).get("files") if isinstance(meta, dict) else None
    if not files:
        return {"item": item, "found": False}
    pattern = re.compile(rf"^{re.escape(slug)}-(\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?)\.nxvapp$")
    versions = [m.group(1) for f in files for m in [pattern.match(f.get("name", ""))] if m]
    if not versions:
        return {"item": item, "found": True, "versions": []}
    newest = max(versions, key=lambda v: version_key(v) or (0,))
    local_key = version_key(local_version or "")
    return {"item": item, "found": True, "versions": sorted(versions, key=lambda v: version_key(v) or (0,)),
            "newest": newest, "local": local_version,
            "behind": bool(local_key and version_key(newest) > local_key)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=Path)
    parser.add_argument("--archive-item")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = {}
    try:
        import port_studio
        snapshot = port_studio.select_sdk()
        versions = port_studio.sdk_report(snapshot)["versions"]
        report["os"] = os_report(versions["os"])
        report["sdk"] = {"sdk": versions["sdk"], "native": versions["native"]}
        if args.port:
            port = args.port if args.port.is_absolute() else Path.cwd() / args.port
            config = json.loads((port / "port.json").read_text(encoding="utf-8-sig"))
            lock = json.loads((port / "sdk.lock.json").read_text(encoding="utf-8-sig")) if (port / "sdk.lock.json").is_file() else {}
            report["port"] = {"slug": config.get("slug"), "sdkLock": lock.get("commit"), "release": config.get("release", {})}
            item = args.archive_item or config.get("updates", {}).get("archiveItem")
            version = (config.get("release") or {}).get("version")
            if item:
                report["archive"] = archive_report(item, config.get("slug", ""), version)
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    o = report["os"]
    flag = "UPDATE AVAILABLE" if o["behind"] else "up to date"
    print(f"Nexvyn OS : local {o['local']}, newest {o['newest']}{' (pre-release)' if o['newestIsPrerelease'] else ''}, "
          f"newest stable {o['newestStable']} -> {flag}")
    print(f"SDK       : SDK {report['sdk']['sdk']}, Native {report['sdk']['native']} (see SDK_UPDATES.md to take an update)")
    if "archive" in report:
        a = report["archive"]
        if not a.get("found"):
            print(f"Archive   : item '{a['item']}' not found on archive.org")
        elif not a.get("versions"):
            print(f"Archive   : item '{a['item']}' has no <slug>-<version>.nxvapp files")
        else:
            print(f"Archive   : newest {a['newest']}, port release {a['local']} -> "
                  f"{'NEWER ON ARCHIVE' if a['behind'] else 'matches or ahead'}")
    elif args.port:
        print("Archive   : no item set. Add \"updates\": {\"archiveItem\": \"<item>\"} to port.json or pass --archive-item.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
