"""Console test round: send the app to a physical console, give the tester a sheet, record what they saw.

  python _PortStudioMain/tools/console_run.py push <port> --host <console IP> [--module FILE | --source DIR] [--dry-run]
  python _PortStudioMain/tools/console_run.py sheet <port> [--scenario gameplay]
  python _PortStudioMain/tools/console_run.py record <sheet-folder>

push    uploads the app over FTP with the SDK's `nxv push` (Connect to PC on the console). Native ports send the store
        source with the built module; script apps send their bundle.
sheet   writes <port>/screenshots/console/<stamp>/checklist.md from port.json emulator.scenarios: every step as a human
        action, for handheld and docked, with fields for the OS performance panel (Ctrl+Alt+P or L+R+ZL+ZR) and the
        photos or captures the tester adds next to it.
record  reads the filled sheet (`Result: PASS|FAIL` per mode) and writes results.jsonl with environment=console.
        A sheet that is not filled stays NOT_RUN. Studio never marks a console result on its own.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
NXV = TOOLS.parent / "nexvyn_sdk" / "Tools" / "nxv" / "nxv.py"
MODES = ("handheld", "docked")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def bundle_for(port, module=None, source=None):
    """(folder to upload, temp dir or None). Script apps: their bundle; native ports: store source + module."""
    if source:
        return Path(source), None
    if (port / "source" / "app.json").is_file():
        return port / "source", None
    sources = sorted(port.glob("AppMarket/Store/*/*/*/source"))
    if not sources:
        raise SystemExit("No store source folder (AppMarket/Store/.../source) and no --source.")
    if not module:
        return sources[0], None
    work = Path(tempfile.mkdtemp(prefix="console_bundle_"))
    bundle = work / sources[0].parent.name
    shutil.copytree(sources[0], bundle)
    shutil.copy2(module, bundle / Path(module).name)
    return bundle, work


def push(args):
    port = Path(args.port).resolve()
    bundle, work = bundle_for(port, args.module, args.source)
    command = [sys.executable, str(NXV), "push", str(bundle), "--host", args.host]
    if args.dry_run:
        command.append("--dry-run")
    try:
        return subprocess.run(command).returncode
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)


def human(step, targets, mode):
    parts = step.split()
    if not parts:
        return ""
    verb = parts[0]
    if verb == "tap" and len(parts) == 2:
        point = (targets.get(parts[1]) or {}).get(mode)
        return f"Tap {parts[1]}" + (f" (at {point[0]},{point[1]} on the emulator shot)" if point else "")
    if verb == "tap":
        return f"Tap at {parts[1]},{parts[2]}"
    if verb == "wait":
        return f"Wait about {parts[1]} s"
    if verb == "shot":
        return f"Take a capture: **{parts[1]}** (Capture button or a photo); save it as `{parts[1]}_<mode>.png` here"
    if verb in ("padhold", "dpad"):
        return f"Press {' '.join(parts[1:])} on the controller"
    if verb in ("hold", "key"):
        return f"Keyboard: {' '.join(parts[1:])}"
    if verb == "stats":
        return "Open the performance panel (Ctrl+Alt+P or L+R+ZL+ZR) and write the numbers below"
    return "Do: `" + step + "`"


def sheet(args):
    port = Path(args.port).resolve()
    config = read_json(port / "port.json")
    emulator = config.get("emulator", {})
    scenario = emulator.get("scenarios", {}).get(args.scenario)
    if not scenario:
        raise SystemExit(f"port.json has no emulator.scenarios.{args.scenario}.")
    folder = port / "screenshots" / "console" / f"{time.strftime('%Y%m%d-%H%M%S')}_{args.scenario}"
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"# Console test: {port.name} / {args.scenario}", "",
             "Install the package on the console first (`console_run.py push`). Fill every field. Only what you saw",
             "on the console counts; leave `Result: NOT_RUN` when a mode was not tested.", "",
             "- Console firmware / Nexvyn OS version: ", "- Package version: ", "- Tester and date: ", ""]
    for mode in MODES:
        lines += [f"## {mode.capitalize()}", ""]
        for number, step in enumerate(scenario.get("steps", []), 1):
            text = human(step, emulator.get("targets", {}), mode)
            if text:
                lines.append(f"{number}. {text}")
        lines += ["", "- What the screen showed (in game? menu? error?): ",
                  "- Performance panel: frame time ms = , skipped frames = , RAM MB = , GPU lock ms = ",
                  "- Problems seen: ", f"- Result: NOT_RUN", ""]
    (folder / "checklist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "scenario.json").write_text(json.dumps(dict(scenario, name=args.scenario, port=port.name), indent=2),
                                          encoding="utf-8")
    print(f"Console sheet: {folder / 'checklist.md'}")
    return 0


def record(args):
    folder = Path(args.folder).resolve()
    text = (folder / "checklist.md").read_text(encoding="utf-8")
    scenario = read_json(folder / "scenario.json")
    rows = []
    for mode, block in re.findall(r"^## (\w+)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        result = re.search(r"^- Result:\s*(PASS|FAIL|NOT_RUN)\b", block, re.M)
        status = result.group(1) if result else "NOT_RUN"
        numbers = dict(re.findall(r"(frame time ms|skipped frames|RAM MB|GPU lock ms)\s*=\s*([\d.]+)", block))
        rows.append({"id": f"{scenario.get('port')}/{scenario.get('name')}/{mode.lower()}", "status": status,
                     "environment": "console", "metrics": numbers, "markers": []})
    (folder / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for r in rows:
        print(f"{r['id']}: {r['status']} {r['metrics'] or ''}")
    return 0 if rows and all(r["status"] == "PASS" for r in rows) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("push")
    p.add_argument("port")
    p.add_argument("--host", required=True)
    bundle = p.add_mutually_exclusive_group()
    bundle.add_argument("--module")
    bundle.add_argument("--source")
    p.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("sheet")
    s.add_argument("port")
    s.add_argument("--scenario", default="gameplay")
    r = sub.add_parser("record")
    r.add_argument("folder")
    args = parser.parse_args(argv)
    return {"push": push, "sheet": sheet, "record": record}[args.action](args)


if __name__ == "__main__":
    sys.exit(main())
