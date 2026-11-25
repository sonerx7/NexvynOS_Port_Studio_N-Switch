"""Port Market release automation for ports whose code may be redistributed (open-source ports): one command from a
verified port to a ready Archive candidate. The owner uploads with the printed command.

  python _PortStudioMain/tools/market_release.py <port> [--approve] [--license SPDX] [--item ID] [--source-url URL]
  python _PortStudioMain/tools/market_release.py --all          # what every port still needs (changes nothing)

Steps:
  1. license      SPDX id from --license, port.json "license", or the port's LICENSE/COPYING text
  2. verify       verify.py must have no FAIL (fake content, imports, locales, limits ...)
  3. screenshots  3-5 real shots copied from the newest emulator run whose automatic and visual review both PASS
                  (store screenshots/1.png ...); never generated images
  4. records      with --approve only (the owner's rights decision): DISTRIBUTION.md, the version sections of
                  CHANGELOG.md and KNOWN_ISSUES.md (facts from the run), release.status "ready" for the app.json version
  5. archive      port_market.py prepare-archive (data-free store package: players supply their own game data),
                  search-friendly item name nexvyn-os-nx-<port>-game-port, then the publish dry run
  6. command      prints `port_market.py publish <candidate> --yes` for the owner

It never uploads, never passes --yes or --full-package, and never reads Archive keys. Ports whose code is not
redistributable stay blocked: --approve refuses an unrecognised licence and a module with lifted or recompiled
commercial code (evidence in port.json or PORT.md, unless port.json says "codeRedistributable": true).
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
MARKET = TOOLS / "port_market.py"
VERIFY = TOOLS / "verify.py"
PORT_TYPES = ("GamePorts", "SoftwarePorts")
# Text markers of licences that allow redistribution of the port's own code (SPDX id, pattern).
LICENSES = (
    ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"), ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"),
    ("LGPL-2.1", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 2\.1"), ("LGPL-3.0", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3"),
    ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"), ("MPL-2.0", r"Mozilla Public License,? Version 2\.0"),
    ("Apache-2.0", r"Apache License,?\s+Version 2\.0"), ("MIT", r"Permission is hereby granted, free of charge"),
    ("BSD-3-Clause", r"Neither the name of .* nor the names of its\s+contributors"),
    ("BSD-2-Clause", r"Redistributions in binary form must reproduce"), ("Zlib", r"This notice may not be removed or altered"),
    ("Unlicense", r"This is free and unencumbered software released into the public domain"),
)
OPEN_SOURCE = {spdx for spdx, _ in LICENSES}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def detect_license(port):
    config = read_json(port / "port.json")
    if config.get("license"):
        return config["license"], "port.json"
    for path in sorted([*port.glob("LICENSE*"), *port.glob("COPYING*")]):
        text = path.read_text(encoding="utf-8", errors="replace")
        for spdx, pattern in LICENSES:
            if re.search(pattern, text, re.I):
                return spdx, path.name
    return None, None


LIFTED = re.compile(r"(?i)\b(lifted|lift_stamp|tools/lift|recompil\w*|recomp\b|pcrecomp|static recompilation|"
                    r"gamemd\.exe|default\.xbe|\.xbe\b)")


def lifted_code(port):
    """Evidence that the module carries code translated from a commercial binary (not the port author's to share)."""
    config = read_json(port / "port.json")
    if config.get("codeRedistributable") is True:  # the owner states the code is theirs to share
        return None
    if config.get("codeRedistributable") is False:
        return "port.json codeRedistributable is false"
    for name in ("port.json", "PORT.md"):
        path = port / name
        match = LIFTED.search(path.read_text(encoding="utf-8", errors="replace")) if path.is_file() else None
        if match:
            return f"{name} mentions '{match.group(0)}'"
    return None


def store_item(port):
    items = [p.parent for p in port.glob("AppMarket/Store/*/*/*/source")]
    return items[0] if items else None


def passing_runs(port):
    """Newest first: emulator runs whose review.md says the automatic and the visual review passed."""
    runs = []
    for run in (port / "screenshots" / "runs").glob("*") if (port / "screenshots" / "runs").is_dir() else []:
        review = run / "review.md"
        if not review.is_file():
            continue
        text = review.read_text(encoding="utf-8", errors="replace")
        if "Automatic checks: **PASS**" in text and "Visual review: **PASS**" in text:
            runs.append(run)
    return sorted(runs, key=lambda r: r.name, reverse=True)


def pick_shots(run):
    """Real shots for the store: the gameplay shots first, then the others; never the launcher or the end frame."""
    scenario = read_json(run / "scenario.json") if (run / "scenario.json").is_file() else {}
    gameplay = [run / f"{name}.png" for name in scenario.get("gameplay", [])]
    others = sorted(p for p in run.glob("*.png") if p.stem not in {"launcher", "zz_end"} and p not in gameplay)
    shots = [p for p in gameplay + others if p.is_file()]
    return shots[:5]


def verify_fails(port):
    out = subprocess.run([sys.executable, "-X", "utf8", str(VERIFY), str(port)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return [line.strip() for line in out.stdout.splitlines() if re.match(r"^\S+\s+FAIL\b", line)]


def status(port):
    """(missing: list of what blocks a release, facts: dict) without changing anything."""
    missing, facts = [], {}
    config = read_json(port / "port.json")
    spdx, where = detect_license(port)
    facts["license"] = f"{spdx} ({where})" if spdx else None
    if not spdx:
        missing.append("licence: add LICENSE/COPYING or port.json \"license\"")
    elif spdx not in OPEN_SOURCE:
        missing.append(f"licence {spdx} is not a recognised redistributable open-source licence")
    lifted = lifted_code(port)
    if lifted:
        missing.append(f"module carries lifted/recompiled commercial code ({lifted}): not redistributable")
    item = store_item(port)
    if not item:
        missing.append("no AppMarket/Store/.../source folder")
        return missing, facts
    app = read_json(item / "source" / "app.json")
    facts["version"] = app.get("version")
    main = item / "source" / str(app.get("main", ""))
    if str(app.get("main", "")).endswith(".nxvmod") and not main.is_file():
        missing.append("module not built/staged into the store source")
    runs = passing_runs(port)
    facts["run"] = runs[0].name if runs else None
    if not runs:
        missing.append("no emulator run with automatic and visual review PASS (scenario_run + review.md)")
    elif len(pick_shots(runs[0])) < 3:
        missing.append(f"run {runs[0].name} has fewer than 3 usable shots")
    release = config.get("release", {})
    facts["release"] = release.get("status")
    if release.get("status") != "ready" or release.get("version") != facts["version"]:
        missing.append("release not approved for this version (run with --approve)")
    return missing, facts


def copy_screenshots(port, item, run):
    target = item / "screenshots"
    if target.is_dir():
        shutil.rmtree(target)
    target.mkdir()
    for index, shot in enumerate(pick_shots(run), 1):
        shutil.copyfile(shot, target / f"{index}.png")
    return len(list(target.glob("*.png")))


def add_section(path, version, lines):
    text = path.read_text(encoding="utf-8") if path.is_file() else f"# {path.stem.replace('_', ' ').title()}\n"
    if re.search(rf"^## (?:\[{re.escape(version)}\]|{re.escape(version)})(?=\s|$)", text, re.M):
        return False
    head, _, rest = text.partition("\n## ")
    section = f"## {version}\n\n" + "\n".join(f"- {line}" for line in lines) + "\n"
    path.write_text(head.rstrip() + "\n\n" + section + ("\n## " + rest if rest else ""), encoding="utf-8")
    return True


def approve(port, spdx, version, run, source_url):
    """The owner's release decision, written as records. Only for a recognised open-source licence."""
    if spdx not in OPEN_SOURCE:
        raise SystemExit(f"Refused: {spdx} is not a recognised redistributable open-source licence.")
    lifted = lifted_code(port)
    if lifted:
        raise SystemExit(f"Refused: the module carries lifted/recompiled commercial code ({lifted}).")
    today = date.today().isoformat()
    dist = port / "DISTRIBUTION.md"
    if not dist.is_file() or "PORT_STUDIO_TEMPLATE" in dist.read_text(encoding="utf-8") or not dist.read_text(encoding="utf-8").strip():
        dist.write_text(
            f"# Distribution record\n\n- Version: {version}\n- Licence of the port's code: {spdx}\n"
            f"- Source code: {source_url or 'see port.json sourceUrl'}\n"
            "- Package content: the port's own code and assets only. No game data, BIOS or firmware; players supply "
            "their own files.\n"
            f"- Approved by the owner on {today} with `market_release.py --approve`.\n", encoding="utf-8")
    add_section(port / "CHANGELOG.md", version,
                [f"Port Market release candidate ({spdx}).", f"Emulator run {run.name}: automatic and visual review PASS."])
    add_section(port / "KNOWN_ISSUES.md", version,
                ["Not tested on a physical console; emulator results are relative only.",
                 "Players need their own game data; the package has none."])
    config = read_json(port / "port.json")
    config["release"] = {"status": "ready", "version": version, "reasons": []}
    config.setdefault("license", spdx)
    write_json(port / "port.json", config)


def suggested_item(port):
    """Search-friendly Archive identifier: nexvyn-os-nx-<slug>-<game-port|app>."""
    kind = "game-port" if port.parent.name == "GamePorts" else "app"
    slug = re.sub(r"[^a-z0-9]+", "-", port.name.lower()).strip("-")
    return f"nexvyn-os-nx-{slug}-{kind}"


def run(command):
    print("> " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in command), flush=True)
    return subprocess.run([sys.executable, "-X", "utf8", *map(str, command)]).returncode


def report_all():
    print(f"{'port':34} {'licence':20} {'version':9} missing")
    for kind in PORT_TYPES:
        for port in sorted((ROOT / kind).iterdir()) if (ROOT / kind).is_dir() else []:
            if not (port / "port.json").is_file():
                continue
            try:
                missing, facts = status(port)
            except (OSError, ValueError) as error:
                missing, facts = [f"unreadable: {error}"], {}
            print(f"{kind + '/' + port.name:34} {str(facts.get('license') or '-')[:20]:20} "
                  f"{str(facts.get('version') or '-'):9} {'; '.join(missing) or 'READY'}")
    return 0


def release(args):
    port = Path(args.port).resolve()
    if not (port / "port.json").is_file():
        print(f"Error: {port} has no port.json.", file=sys.stderr)
        return 1
    spdx = args.license or detect_license(port)[0]
    fails = verify_fails(port)
    if fails:
        print("Stopped: verify has FAIL rows:\n  " + "\n  ".join(fails), file=sys.stderr)
        return 1
    item = store_item(port)
    runs = passing_runs(port)
    if not item or not runs:
        print("Stopped: " + ("no store item" if not item else "no emulator run with automatic and visual PASS"),
              file=sys.stderr)
        return 1
    count = copy_screenshots(port, item, runs[0])
    print(f"Store screenshots: {count} real shots from run {runs[0].name}")
    if count < 3:
        print("Stopped: a store package needs at least 3 real screenshots.", file=sys.stderr)
        return 1
    version = read_json(item / "source" / "app.json").get("version")
    source_url = args.source_url or read_json(port / "port.json").get("sourceUrl", "")
    if args.approve:
        approve(port, spdx, version, runs[0], source_url)
        print(f"Release approved for {version} ({spdx}); records written.")
    missing, _ = status(port)
    if missing:
        print("Stopped: " + "; ".join(missing), file=sys.stderr)
        return 1
    item_id = args.item or suggested_item(port)
    output = ROOT / "_RealesedBuilds" / "archive" / port.name
    prepare = [MARKET, "prepare-archive", port, "--item", item_id, "--license", spdx, "--output", output]
    if source_url:
        prepare += ["--source-url", source_url]
    if run(prepare) != 0 or run([MARKET, "publish", output]) != 0:
        print("Stopped (see the message above).", file=sys.stderr)
        return 1
    title = read_json(output / "internet-archive.json").get("title")
    print(f"\nReady. Archive item: {item_id}\nTitle: {title}\nUpload it yourself with:\n")
    print(f'  python -X utf8 _PortStudioMain/tools/port_market.py publish "{output.relative_to(ROOT).as_posix()}" --yes\n')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("port", nargs="?")
    parser.add_argument("--all", action="store_true", help="Show what every port still needs; changes nothing.")
    parser.add_argument("--approve", action="store_true", help="Owner: approve the release and write the records.")
    parser.add_argument("--license", help="SPDX id (default: port.json license or the port's LICENSE text).")
    parser.add_argument("--item", help="Archive identifier (default: nexvyn-os-nx-<port>-<game-port|app>).")
    parser.add_argument("--source-url", help="https link to the port's source code (default: port.json sourceUrl).")
    args = parser.parse_args(argv)
    if args.all:
        return report_all()
    if not args.port:
        parser.error("give a port folder or --all")
    return release(args)


if __name__ == "__main__":
    sys.exit(main())
