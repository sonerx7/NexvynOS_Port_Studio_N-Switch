"""`port_studio.py make`: run the existing Studio tools in order for one port and write one report.

  python _PortStudioMain/tools/port_studio.py make GamePorts/<port> [--module FILE] [--data-root DIR]
         [--workspace DIR] [--mode both|docked|handheld] [--steps doctor,build,verify,pack,scenario,review]

Steps (each one is an existing command; make adds no checks of its own):
  doctor    port_studio.py doctor --json --port P
  build     port_studio.py build P              (build.driver "sdk")
            port_studio.py stage P --module M   (other drivers: the module comes from --module)
  verify    verify.py P --module M
  pack      port_studio.py pack local P --data-root D   (when the port has localData and --data-root is given)
            port_studio.py check store P                (otherwise)
  scenario  scenario_run.py P --app-id ID --module M --game-dir D --mode MODE
  review    shot_review.py <run>   for each run the scenario wrote (automatic layer only)

--workspace copies the port to <workspace>/<GamePorts|SoftwarePorts>/<name> once (build output, emulator profile,
screenshots and personal data stay behind) and runs every step there with PORT_STUDIO_ROOT=<workspace>, so the
original port folder is only read. A later make with the same --workspace reuses the copy.
The visual review (open every screenshot, fill review.md, then `shot_review.py <run> --check`) stays a manual step:
make never reports a gameplay pass.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from studio_files import app_runtime

TOOLS = Path(__file__).resolve().parent
STEPS = ("doctor", "build", "verify", "pack", "scenario", "review")
SKIP_COPY = {"build", "dist", "work", ".emulator_profile", "screenshots", "__pycache__", ".git"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def copy_port(port, workspace):
    """Copy the port once into the workspace, leaving build output and personal data behind."""
    target = workspace / port.parent.name / port.name
    if target.is_dir():
        return target
    config = read_json(port / "port.json")
    public_tops = {Path(p).parts[0] for p in config.get("publicFiles", [])}
    data_files = {Path(m["from"]).as_posix() for m in config.get("localData", []) if isinstance(m, dict) and m.get("from")}
    data_tops = {Path(p).parts[0] for p in data_files} - public_tops

    def ignore(directory, names):
        rel = Path(directory).relative_to(port)
        skipped = set()
        for name in names:
            path = (rel / name).as_posix()
            if rel == Path(".") and (name in SKIP_COPY or name.startswith("build_") or name in data_tops):
                skipped.add(name)
            elif path in data_files:
                skipped.add(name)
        return skipped

    shutil.copytree(port, target, ignore=ignore)
    return target


def run_step(name, command, env, log):
    start = time.time()
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    output = (result.stdout + result.stderr).strip()
    row = {"step": name, "command": " ".join(str(c) for c in command), "exit": result.returncode,
           "seconds": round(time.time() - start, 1), "tail": output.splitlines()[-12:]}
    log.append(row)
    status = "ok" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
    print(f"[make] {name}: {status} in {row['seconds']} s")
    return result.returncode == 0, output


def run_dirs(port, since):
    runs = port / "screenshots" / "runs"
    return sorted(p for p in runs.iterdir() if p.is_dir() and p.stat().st_mtime >= since) if runs.is_dir() else []


def portlib_versions():
    """Installed devkitPro switch-* portlibs (`pacman -Q`), so a build can be repeated with the same libraries."""
    pacman = Path(os.environ.get("DEVKITPRO_WIN", "C:/devkitPro")) / "msys2" / "usr" / "bin" / "pacman.exe"
    if not pacman.is_file():
        pacman = Path(shutil.which("pacman") or "")
    if not pacman.name or not pacman.is_file():
        return []
    try:
        out = subprocess.run([str(pacman), "-Q"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in out.splitlines() if line.startswith(("switch-", "devkitA64", "libnx"))]


def write_report(where, port, log, notes):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# make report: {port.name}", "", f"- Date: {stamp}", f"- Port folder used: `{port}`", "",
             "| Step | Exit | Seconds | Command |", "| --- | --- | --- | --- |"]
    lines += [f"| {r['step']} | {r['exit']} | {r['seconds']} | `{r['command']}` |" for r in log]
    for r in log:
        lines += ["", f"## {r['step']}", "", "```", *r["tail"], "```"]
    lines += ["", "## Notes", "", *[f"- {n}" for n in notes]]
    portlibs = portlib_versions()
    lines += ["", "## Toolchain and portlibs (this machine)", "",
              *([f"- `{p}`" for p in portlibs] or ["- pacman not found: versions not recorded."])]
    (where / "make_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (where / "make_report.json").write_text(json.dumps({"port": str(port), "steps": log, "notes": notes,
                                                        "portlibs": portlibs}, indent=2),
                                            encoding="utf-8")
    return where / "make_report.md"


def make(args, root):
    """Returns the exit code. `root` is port_studio.ROOT."""
    port = Path(os.path.abspath(args.port))
    steps = [s.strip() for s in (args.steps or ",".join(STEPS)).split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        raise ValueError(f"Unknown make steps: {', '.join(unknown)} (choose from {', '.join(STEPS)})")
    env = dict(os.environ)
    work_root = root
    if args.workspace:
        work_root = Path(os.path.abspath(args.workspace))
        work_root.mkdir(parents=True, exist_ok=True)
        port = copy_port(port, work_root)
        env["PORT_STUDIO_ROOT"] = str(work_root)
    config = read_json(port / "port.json") if (port / "port.json").is_file() else {}
    driver = (config.get("build") or {}).get("driver", "sdk")
    script_source = port / "source" if (port / "source" / "app.json").is_file() else None
    script = script_source is not None and app_runtime(read_json(script_source / "app.json")) != "native"
    module = Path(os.path.abspath(args.module)) if args.module else None
    data_root = Path(os.path.abspath(args.data_root)) if args.data_root else None
    py, studio = sys.executable, str(TOOLS / "port_studio.py")
    log, notes = [], []
    started = time.time()

    store_sources = [script_source / "app.json"] if script else list(port.glob("AppMarket/Store/*/*/*/source/app.json"))
    app = read_json(store_sources[0]) if store_sources else {}
    if module is None and driver == "sdk":
        module = port / "build" / app.get("main", "")

    nxv = str(TOOLS.parent / "nexvyn_sdk" / "Tools" / "nxv" / "nxv.py")
    if script:
        plan = {
            "doctor": [py, studio, "doctor", "--json"],
            "build": "skip",
            "verify": [py, str(TOOLS / "verify.py"), str(port)],
            "pack": [py, nxv, "pack", str(script_source)],
            "scenario": [py, str(TOOLS / "scenario_run.py"), str(port), "--app-id", app.get("id", ""),
                         "--source", str(script_source), "--mode", args.mode],
        }
    else:
        plan = None
    plan = plan or {
        "doctor": [py, studio, "doctor", "--json", "--port", str(port)],
        "build": ([py, studio, "build", str(port)] if driver == "sdk"
                  else [py, studio, "stage", str(port), "--module", str(module)] if module else None),
        "verify": [py, str(TOOLS / "verify.py"), str(port)] + (["--module", str(module)] if module else []),
        "pack": ([py, studio, "pack", "local", str(port), "--data-root", str(data_root)]
                 if config.get("localData") and data_root else [py, studio, "check", "store", str(port)]),
        "scenario": ([py, str(TOOLS / "scenario_run.py"), str(port), "--app-id", app.get("id", ""), "--module", str(module),
                      "--mode", args.mode] + (["--game-dir", str(data_root)] if data_root else [])) if module else None,
    }
    code = 0
    for step in steps:
        if step == "review":
            runs = run_dirs(port, started)
            if not runs:
                notes.append("review: no scenario run in this make; nothing to review.")
            for run in runs:
                run_step(f"review {run.name}", [py, str(TOOLS / "shot_review.py"), str(run)], env, log)
            if runs:
                notes.append("Visual review is still required: open every PNG in each run folder, fill review.md, then "
                             "`shot_review.py <run> --check`. make does not report a gameplay pass.")
            continue
        command = plan[step]
        if command == "skip":
            notes.append(f"{step}: skipped; script app (no native build).")
            continue
        if command is None:
            notes.append(f"{step}: skipped; build.driver is '{driver}', pass --module with the built .nxvmod.")
            code = 1
            break
        ok, _ = run_step(step, command, env, log)
        if not ok:
            notes.append(f"Stopped at {step}; later steps did not run.")
            code = 1
            break
    notes.append("Checks ran on the host and, for the scenario step, in the Ryujinx emulator. Not tested on a device.")
    report = write_report(work_root if args.workspace else port, port, log, notes)
    print(f"[make] report: {report}")
    return code


def add_parser(sub):
    p = sub.add_parser("make", help="Run doctor, build/stage, verify, pack, scenario and review for one port (see studio_make.py).")
    p.add_argument("port")
    p.add_argument("--module", help="Built .nxvmod (required when build.driver is not 'sdk').")
    p.add_argument("--data-root", help="Personal game data for the local package and the emulator run.")
    p.add_argument("--workspace", help="Copy the port here and run every step on the copy; the original is only read.")
    p.add_argument("--mode", choices=("both", "docked", "handheld"), default="both")
    p.add_argument("--steps", help=f"Comma list, default all: {','.join(STEPS)}")
    return p
