"""One command to get a port ready for the Port Market: prepare the Archive candidate, show the dry run, print the
upload command for the owner.

  python _PortStudioMain/tools/market_release.py <port> [--license MIT] [--item ID] [--source-url URL]

Steps (each one is an existing port_market.py command):
  1. prepare-archive   the data-free store package, icon, screenshots, listing and Archive metadata (search-friendly
                       title and subjects) into _RealesedBuilds/archive/<port>/
  2. publish           dry run: shows what would be uploaded and writes the merged catalog; nothing is sent
  3. prints            the one-line upload command (`publish ... --yes`) for the owner to run on the machine that holds
                       the Archive keys

The store package carries no game data (players use their own files). This tool never uploads, never passes --yes,
never reads Archive keys, and never uses --full-package: a package with game data needs recorded clearance and is the
owner's own step in PORT_MARKET.md.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
MARKET = TOOLS / "port_market.py"


def suggested_item(port):
    """Search-friendly Archive identifier: nexvyn-os-nx-<slug>-<game-port|app>."""
    kind = "game-port" if port.parent.name == "GamePorts" else "app"
    slug = re.sub(r"[^a-z0-9]+", "-", port.name.lower()).strip("-")
    return f"nexvyn-os-nx-{slug}-{kind}"


def run(command):
    print("> " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in command), flush=True)
    return subprocess.run([sys.executable, "-X", "utf8", *map(str, command)]).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("port")
    parser.add_argument("--license", default="MIT", help="SPDX id of the port's own code (default MIT).")
    parser.add_argument("--item", help="Archive identifier (default: nexvyn-os-nx-<port>-<game-port|app>).")
    parser.add_argument("--source-url", help="https link to the port's source code (default: port.json sourceUrl).")
    args = parser.parse_args(argv)
    port = Path(args.port).resolve()
    if not (port / "port.json").is_file():
        print(f"Error: {port} has no port.json.", file=sys.stderr)
        return 1
    release = json.loads((port / "port.json").read_text(encoding="utf-8-sig")).get("release", {})
    if release.get("status") != "ready":
        print(f"Stopped: release.status is '{release.get('status')}', not 'ready' "
              f"({'; '.join(release.get('reasons', [])) or 'no reason recorded'}). "
              "Record the redistribution rights in DISTRIBUTION.md and set the status first (RELEASE_WORKFLOW.md).",
              file=sys.stderr)
        return 1
    item = args.item or suggested_item(port)
    output = ROOT / "_RealesedBuilds" / "archive" / port.name
    prepare = [MARKET, "prepare-archive", port, "--item", item, "--license", args.license, "--output", output]
    if args.source_url:
        prepare += ["--source-url", args.source_url]
    if run(prepare) != 0:
        print("Stopped at prepare-archive (see the message above).", file=sys.stderr)
        return 1
    if run([MARKET, "publish", output]) != 0:
        print("Stopped at the publish dry run (see the message above).", file=sys.stderr)
        return 1
    metadata = json.loads((output / "internet-archive.json").read_text(encoding="utf-8"))
    print("\nReady. Archive item:", item)
    print("Title:", metadata.get("title"))
    print("Check the dry run above, then upload it yourself with:\n")
    print(f'  python -X utf8 _PortStudioMain/tools/port_market.py publish "{output.relative_to(ROOT).as_posix()}" --yes\n')
    return 0


if __name__ == "__main__":
    sys.exit(main())
