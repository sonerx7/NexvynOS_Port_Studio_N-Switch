"""Gameplay scenario run: launcher -> menu -> real play, a screenshot at each phase, then the run review.

  python _PortStudioMain/tools/scenario_run.py <port-dir> --app-id <id> --module <file.nxvmod> [--game-dir <dir>]
         [--scenario gameplay] [--mode docked|handheld|both]

Reads port.json emulator.scenarios.<name>:
  steps     autorun lines (tap NAME, finger, dpad, padhold, key, hold, wait, stats ...) with `shot NAME` at each phase
  gameplay  shots that must show real play
  motion    [a, b] shot pairs whose pictures must differ (the game is not frozen)
  expectLog regexes that must appear in the app log
  wait, timeout  seconds before the steps and for the whole run

Each run writes <port>/screenshots/runs/<stamp>_<name>_<mode>/ (shots, app log, system.log, scenario.json, report.json,
review.md) and never touches the port's other screenshots. It reuses emulator_test.py for the isolated profile,
the shared lock and the minimized emulator start. The visual review in review.md is required afterwards
(shot_review.py <run> --check).
"""

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import emulator_test as emu
import shot_review


def load_scenario(port, name):
    config = json.loads((Path(port) / "port.json").read_text(encoding="utf-8-sig"))
    scenarios = config.get("emulator", {}).get("scenarios", {})
    if name not in scenarios:
        raise SystemExit(f"No emulator.scenarios.{name} in {port}/port.json (have: {', '.join(scenarios) or 'none'}).")
    block = dict(scenarios[name])
    block["name"] = name
    shots = [line.split()[1] for line in block.get("steps", []) if line.split()[:1] == ["shot"] and len(line.split()) > 1]
    if not shots:
        raise SystemExit(f"Scenario {name} takes no screenshot: add `shot <name>` lines at each phase.")
    unknown = [s for s in block.get("gameplay", []) + [s for pair in block.get("motion", []) for s in pair] if s not in shots]
    if unknown:
        raise SystemExit(f"Scenario {name} refers to shots it never takes: {', '.join(sorted(set(unknown)))}.")
    block["shots"] = shots
    return block


def apply_console_profile(pid):
    """Closer to console limits: the emulator gets 4 logical CPUs and a below-normal priority.
    Numbers stay emulator-relative; this only makes before/after comparisons fairer."""
    try:
        import psutil
    except ImportError:
        return "not applied (psutil missing)"
    try:
        process = psutil.Process(pid)
        cpus = sorted(process.cpu_affinity())[:4]
        process.cpu_affinity(cpus)
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS") else 10)
        return f"4 CPUs {cpus}, below-normal priority"
    except (psutil.Error, OSError, ValueError) as error:
        return f"not applied ({error})"


def app_paths(app_id):
    """(installed bundle folder, list of data folders) of an app in the emulator profile."""
    sd = emu.PROFILE / "sdcard" / "NexvynOS"
    data = sorted((sd / "Users").glob(f"*/Library/Application Support/{app_id}")) if (sd / "Users").is_dir() else []
    return sd / "Applications" / f"{app_id}.nxvapp", data


def install_previous(previous, target):
    """Unpack a previous .nxvapp (zip) or copy a previous bundle folder into the installed app folder."""
    import zipfile
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    previous = Path(previous)
    if previous.is_dir():
        shutil.copytree(previous, target, dirs_exist_ok=True)
    else:
        with zipfile.ZipFile(previous) as package:
            package.extractall(target)


def prepare(args, scenario):
    """Scenario `setup`: "clean" removes the app and its data first (first launch); "update" installs --previous and
    runs it once so it writes its data, then this version is installed over it. Returns a note for scenario.json."""
    setup = scenario.get("setup")
    app, data = app_paths(args.app_id)
    if setup == "clean":
        shutil.rmtree(app, ignore_errors=True)
        for folder in data:
            shutil.rmtree(folder, ignore_errors=True)
        return "clean: app and data removed before install"
    if setup == "update":
        if not args.previous:
            raise SystemExit("Scenario setup 'update' needs --previous <older .nxvapp or bundle folder>.")
        install_previous(args.previous, app)
        first = argparse.Namespace(**dict(vars(args), steps=None, shot_name="previous_version", module=None, source=None))
        sd = emu.setup_profile_previous(first)
        proc = emu.launch_ryujinx([str(emu.find_ryujinx(args.ryujinx)), "--root-data-dir", str(emu.PROFILE),
                                   str(emu.find_nro(args.nro, refresh=False))])
        start = time.time()
        while time.time() - start < min(args.timeout, 180) and proc.poll() is None:
            time.sleep(2)
        if proc.poll() is None:
            proc.terminate()
        return f"update: previous version from {Path(args.previous).name} ran first, then this version was installed over it"
    return None


def run_one(args, scenario):
    lock = emu.wait_profile_lock()
    if lock is None:
        print("Another emulator test is using this profile (.emulator_profile.lock). Wait for it to finish.", file=sys.stderr)
        return 3
    try:
        args.setup_note = prepare(args, scenario)
        return run_locked(args, scenario)
    finally:
        lock.unlink(missing_ok=True)


def run_locked(args, scenario):
    ryujinx = emu.find_ryujinx(args.ryujinx)
    if not ryujinx:
        print(emu.RYUJINX_HELP, file=sys.stderr)
        return 2
    nro = emu.find_nro(args.nro) or emu.fetch_os()
    if not (emu.appdata_ryujinx() / "system" / "prod.keys").is_file():
        print("prod.keys missing: start Ryujinx once and install keys + firmware.", file=sys.stderr)
        return 2
    running = emu.other_ryujinx()
    if running:
        print(f"Note: Ryujinx is already running (PID {', '.join(running)}); both will run slower.", file=sys.stderr)
    with tempfile.TemporaryDirectory() as temp:
        steps = Path(temp) / "steps.txt"
        steps.write_text("\n".join(scenario["steps"]) + "\n", encoding="utf-8")
        # emulator_test appends `shot <shot_name>` after the steps; name it so it is recognisable in the run folder.
        setup = argparse.Namespace(**dict(vars(args), steps=str(steps), shot_name="zz_end"))
        sd = emu.setup_profile(setup, True)
    logs = sd / "System" / "Logs"
    (logs / "Apps" / f"{args.app_id}.log").unlink(missing_ok=True)   # a stale log would fake an expectLog pass
    shots = sd / "autoshots"
    for old in shots.glob("*.png") if shots.exists() else []:
        old.unlink(missing_ok=True)
    proc = emu.launch_ryujinx([str(ryujinx), "--root-data-dir", str(emu.PROFILE), str(nro)])
    profile = apply_console_profile(proc.pid) if args.console_profile else "off"
    start = time.time()
    while time.time() - start < args.timeout and proc.poll() is None:
        time.sleep(2)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    out = Path(args.port) / "screenshots" / "runs" / f"{time.strftime('%Y%m%d-%H%M%S')}_{scenario['name']}_{args.mode}"
    out.mkdir(parents=True, exist_ok=True)
    for shot in shots.glob("*.png") if shots.exists() else []:
        shutil.copy2(shot, out / shot.name)
    for source, name in ((logs / "Apps" / f"{args.app_id}.log", f"{args.app_id}.log"), (logs / "system.log", "system.log")):
        if source.is_file():
            shutil.copy2(source, out / name)
    block = dict(scenario, mode=args.mode, appId=args.app_id, consoleProfile=profile, setupDone=getattr(args, "setup_note", None),
                 os={"version": emu.LAST_OS.get("version"), "source": emu.LAST_OS.get("source")})
    (out / "scenario.json").write_text(json.dumps(block, indent=2), encoding="utf-8")
    report = shot_review.review(out, block, args.app_id)
    print(f"Mode: {args.mode}. Run folder: {out}")
    for item in report["checks"]:
        print(f"  {item['result']:7} {item['check']}")
    print(f"Automatic: {report['automatic']}. Visual review PENDING: open every PNG in the run folder, fill review.md, "
          f"then run shot_review.py {out} --check.")
    print("Evidence level: emulator only. The physical console is untested.")
    return 0 if report["automatic"] == "PASS" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("port")
    parser.add_argument("--app-id", required=True)
    bundle = parser.add_mutually_exclusive_group(required=True)
    bundle.add_argument("--module", help="Native module (.nxvmod).")
    bundle.add_argument("--source", help="Script app bundle folder (contains app.json).")
    parser.add_argument("--game-dir")
    parser.add_argument("--scenario", default="gameplay")
    parser.add_argument("--mode", choices=("docked", "handheld", "both"), default="both")
    parser.add_argument("--wait", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--data-file", action="append", metavar="NAME=TEXT")
    parser.add_argument("--console-profile", action="store_true",
                        help="Limit the emulator to 4 CPUs at below-normal priority (fairer before/after comparisons).")
    parser.add_argument("--ryujinx")
    parser.add_argument("--nro")
    parser.add_argument("--previous", help="Older .nxvapp or bundle folder for a scenario with setup 'update'.")
    args = parser.parse_args(argv)
    scenario = load_scenario(args.port, args.scenario)
    args.wait = scenario.get("wait", args.wait)
    args.timeout = scenario.get("timeout", args.timeout)
    modes = ("docked", "handheld") if args.mode == "both" else (args.mode,)
    codes = []
    for index, mode in enumerate(modes):
        if index:
            time.sleep(8)   # let the first emulator release the profile
        codes.append(run_one(argparse.Namespace(**dict(vars(args), mode=mode)), scenario))
    return 1 if any(codes) else 0


if __name__ == "__main__":
    sys.exit(main())
