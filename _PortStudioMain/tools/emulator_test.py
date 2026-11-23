"""Emulator smoke test for a port: Ryujinx + Nexvyn OS, launcher run, screenshots, log.

Usage:
  python _PortStudioMain/tools/emulator_test.py check
  python _PortStudioMain/tools/emulator_test.py fetch-os
  python _PortStudioMain/tools/emulator_test.py run <port-dir> --app-id <id> --module <file.nxvmod> [--game-dir <dir>]

Everything lives in an isolated profile (<repo>/.emulator_profile, git-ignored).
Ryujinx itself is never downloaded silently: `check` prints where to get it.
Your Ryujinx keys and firmware are copied into the profile, never uploaded.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / ".emulator_profile"
CACHE = ROOT / "_PortStudioMain" / "_EmulatorCache"
OS_REPO = "sonerx7/Nexvyn-OS-NX"
RYUJINX_HELP = (
    "Ryujinx not found. Install a Ryujinx build (for example the Ryubing fork), "
    "start it once so it creates its keys/firmware folders, then either put it on PATH, "
    "set RYUJINX_EXE=<path to Ryujinx.exe>, or pass --ryujinx <path>."
)


def appdata_ryujinx():
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "Ryujinx"


def find_ryujinx(explicit=None):
    candidates = [explicit, os.environ.get("RYUJINX_EXE"), shutil.which("Ryujinx"), shutil.which("Ryujinx.exe")]
    for item in candidates:
        if item and Path(item).is_file():
            return Path(item)
    return None


def find_nro(explicit=None):
    for item in (explicit, os.environ.get("NEXVYN_NRO"), CACHE / "NexvynOS.nro"):
        if item and Path(item).is_file():
            return Path(item)
    return None


def fetch_os():
    """Download the newest NexvynOS.nro. Uses the gh CLI when available, else urllib."""
    CACHE.mkdir(parents=True, exist_ok=True)
    if shutil.which("gh"):
        tag = subprocess.run(
            ["gh", "release", "list", "-R", OS_REPO, "--limit", "1", "--json", "tagName", "-q", ".[0].tagName"],
            capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["gh", "release", "download", tag, "-R", OS_REPO, "-p", "NexvynOS.nro",
                        "-D", str(CACHE), "--clobber"], check=True)
        (CACHE / "os_version.txt").write_text(tag, encoding="utf-8")
        print(f"Downloaded Nexvyn OS {tag} -> {CACHE / 'NexvynOS.nro'}")
        return CACHE / "NexvynOS.nro"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{OS_REPO}/releases?per_page=5",
        headers={"User-Agent": "nexvyn-port-studio"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        releases = json.load(response)
    for release in releases:
        for asset in release.get("assets", []):
            if asset["name"] == "NexvynOS.nro":
                target = CACHE / "NexvynOS.nro"
                urllib.request.urlretrieve(asset["browser_download_url"], target)
                (CACHE / "os_version.txt").write_text(release["tag_name"], encoding="utf-8")
                print(f"Downloaded Nexvyn OS {release['tag_name']} -> {target}")
                return target
    raise SystemExit("No NexvynOS.nro asset found in recent releases.")


def check(args):
    ok = True
    ryujinx = find_ryujinx(args.ryujinx)
    print(f"Ryujinx : {ryujinx or 'MISSING'}")
    if not ryujinx:
        print("  " + RYUJINX_HELP)
        ok = False
    keys = appdata_ryujinx() / "system" / "prod.keys"
    print(f"Keys    : {'ok' if keys.is_file() else 'MISSING (' + str(keys) + ')'}")
    ok = ok and keys.is_file()
    nro = find_nro(args.nro)
    print(f"Nexvyn OS: {nro or 'MISSING (run: emulator_test.py fetch-os)'}")
    ok = ok and bool(nro)
    return 0 if ok else 1


def set_docked(docked):
    """Handheld or docked is an emulator setting (Config.json docked_mode); the launcher must work in both."""
    path = PROFILE / "Config.json"
    if not path.is_file():
        return
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    config["docked_mode"] = bool(docked)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def setup_profile(args, nro_ok):
    src = appdata_ryujinx()
    PROFILE.mkdir(parents=True, exist_ok=True)
    for sub in ("system", "bis/system/Contents/registered"):
        if (src / sub).exists() and not (PROFILE / sub).exists():
            shutil.copytree(src / sub, PROFILE / sub)
    if (src / "Config.json").exists() and not (PROFILE / "Config.json").exists():
        shutil.copy2(src / "Config.json", PROFILE / "Config.json")
    set_docked(args.mode == "docked")
    sd = PROFILE / "sdcard" / "NexvynOS"
    settings_file = sd / "System" / "Config" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings = {}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text(encoding="utf-8-sig"))
        except ValueError:
            settings = {}
    settings.setdefault("system", {})["reopenWindows"] = False
    settings.setdefault("session", {})["windows"] = []
    settings.setdefault("privacy", {})["telemetry"] = False
    settings.setdefault("updates", {})["autoCheck"] = False
    trusted = settings.setdefault("apps", {}).setdefault("trustedNative", [])
    if args.app_id not in trusted:
        trusted.append(args.app_id)
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    app = sd / "Applications" / f"{args.app_id}.nxvapp"
    app.mkdir(parents=True, exist_ok=True)
    module = Path(args.module)
    shutil.copy2(module, app / module.name)
    for name in ("app.json", "icon.png"):
        if (Path(args.port) / name).is_file():
            shutil.copy2(Path(args.port) / name, app / name)
    if (Path(args.port) / "lang").is_dir():
        shutil.copytree(Path(args.port) / "lang", app / "lang", dirs_exist_ok=True)
    # Everything the real package ships from the port folder (port.json publicFiles): logos, art, extra locales.
    config = Path(args.port) / "port.json"
    if config.is_file():
        for entry in json.loads(config.read_text(encoding="utf-8-sig")).get("publicFiles", []):
            source = Path(args.port) / entry
            if source.is_file() and source.suffix != ".nxvmod":
                (app / entry).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, app / entry)
    if args.game_dir and not (app / "game").exists():
        try:
            os.symlink(Path(args.game_dir).resolve(), app / "game", target_is_directory=True)
        except OSError:
            shutil.copytree(args.game_dir, app / "game")
    for item in args.data_file or []:
        name, _, text = item.partition("=")
        support = sorted((PROFILE / "sdcard" / "NexvynOS" / "Users").glob("*/Library/Application Support"))
        base = (support[0] if support else PROFILE / "sdcard" / "NexvynOS" / "Users" / "user" / "Library" / "Application Support") / args.app_id
        base.mkdir(parents=True, exist_ok=True)
        (base / name).write_text(text.replace("\\n", "\n"), encoding="utf-8")
    targets = {}
    if (Path(args.port) / "port.json").is_file():
        targets = json.loads((Path(args.port) / "port.json").read_text(encoding="utf-8-sig")).get("emulator", {}).get("targets", {})
    steps = expand_steps(Path(args.steps).read_text(encoding="utf-8"), targets, args.mode) if args.steps else ""
    script = (
        f"wait 3\nsetup en\nwait 2\ncloseall\ntrust {args.app_id}\nlaunch {args.app_id}\n"
        f"wait {args.wait}\n{steps}shot {args.shot_name}\nwait 3\nexit\n"
    )
    (sd / "autorun.txt").write_text(script, encoding="utf-8")
    return sd


def expand_steps(text, targets=None, mode="handheld"):
    """`tap X Y` becomes a finger down, a short wait and a finger up on slot 0 (pixels on the 1280x720 screen).
    `tap NAME` looks NAME up in port.json emulator.targets.NAME.<mode> = [x, y]."""
    lines = []
    for raw in text.splitlines():
        parts = raw.split()
        if len(parts) == 2 and parts[0] == "tap":
            point = ((targets or {}).get(parts[1]) or {}).get(mode)
            if not point:
                raise ValueError(f"tap {parts[1]}: no emulator.targets.{parts[1]}.{mode} in port.json.")
            parts = ["tap", str(point[0]), str(point[1])]
        if len(parts) == 3 and parts[0] == "tap":
            x, y = parts[1], parts[2]
            lines += [f"finger 0 down {x} {y}", "wait 1", f"finger 0 up {x} {y}", "wait 1"]
        elif raw.strip():
            lines.append(raw.rstrip())
    return "\n".join(lines) + "\n"


def pid_alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_profile_lock():
    """One emulator run per profile: two runs (two people, or two AI sessions) on the same .emulator_profile
    corrupt each other's screenshots and logs. Returns the lock path, or None when another run holds it."""
    lock = PROFILE.parent / ".emulator_profile.lock"
    if lock.is_file():
        try:
            holder = int(lock.read_text().strip())
        except ValueError:
            holder = 0
        if holder and holder != os.getpid() and pid_alive(holder):
            return None
    lock.write_text(str(os.getpid()))
    return lock


def other_ryujinx():
    """PIDs of Ryujinx processes already running (this tool uses its own profile, but two emulators slow each other)."""
    if os.name != "nt":
        return []
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Ryujinx.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return [line.split(",")[1].strip('"') for line in out.splitlines() if line.startswith('"Ryujinx')]


def run(args):
    if args.mode == "both":
        # The same checks in docked (1080p) and handheld (720p): layout, resolution choice and input differ.
        codes = []
        for mode in ("docked", "handheld"):
            one = argparse.Namespace(**vars(args))
            one.mode = mode
            one.shot_name = f"{args.shot_name}_{mode}"
            codes.append(run_one(one))
            time.sleep(8)   # let the first emulator release the profile before the second starts
        return 1 if any(codes) else 0
    return run_one(args)


def run_one(args):
    lock = acquire_profile_lock()
    if lock is None:
        print("Another emulator test is using this profile (.emulator_profile.lock). Wait for it to finish, "
              "or start yours after it; two runs on one profile corrupt each other.", file=sys.stderr)
        return 3
    try:
        return run_locked(args)
    finally:
        lock.unlink(missing_ok=True)


def run_locked(args):
    ryujinx = find_ryujinx(args.ryujinx)
    if not ryujinx:
        print(RYUJINX_HELP, file=sys.stderr)
        return 2
    nro = find_nro(args.nro)
    if not nro:
        nro = fetch_os()
    if not (appdata_ryujinx() / "system" / "prod.keys").is_file():
        print("prod.keys missing: start Ryujinx once and install keys + firmware.", file=sys.stderr)
        return 2
    running = other_ryujinx()
    if running:
        print(f"Note: Ryujinx is already running (PID {', '.join(running)}). Leave it alone; this test uses its own "
              "profile, but both will run slower.", file=sys.stderr)
    sd = setup_profile(args, True)
    (sd / "System" / "Logs" / "Apps" / f"{args.app_id}.log").unlink(missing_ok=True)   # a stale log would fake an --expect-log pass
    shots = sd / "autoshots"
    if shots.exists():
        for old in shots.glob("*.png"):
            old.unlink(missing_ok=True)
    proc = subprocess.Popen([str(ryujinx), "--root-data-dir", str(PROFILE), str(nro)])
    start = time.time()
    while time.time() - start < args.timeout and proc.poll() is None:
        time.sleep(2)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    out = Path(args.port) / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    captured = []
    if shots.exists():
        for shot in shots.glob("*.png"):
            shutil.copy2(shot, out / shot.name)
            captured.append(shot.name)
    log = sd / "System" / "Logs" / "Apps" / f"{args.app_id}.log"
    if log.is_file():
        shutil.copy2(log, out / f"{args.app_id}.log")
    print(f"Mode: {args.mode}.")
    print(f"Emulator run done. Screenshots: {captured or 'NONE'}; log: {'yes' if log.is_file() else 'no'}.")
    failed = []
    if args.expect_log:
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        for pattern in args.expect_log:
            found = re.search(pattern, text) is not None
            print(f"expect_log {'PASS' if found else 'FAIL'}: {pattern}")
            if not found:
                failed.append(pattern)
    print("Record this as an EMULATOR check only; physical Switch is untested.")
    return 0 if captured and not failed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ryujinx")
    parser.add_argument("--nro")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("check")
    sub.add_parser("fetch-os")
    runner = sub.add_parser("run")
    runner.add_argument("port")
    runner.add_argument("--app-id", required=True)
    runner.add_argument("--module", required=True)
    runner.add_argument("--game-dir")
    runner.add_argument("--wait", type=int, default=60, help="Seconds to wait before the screenshot.")
    runner.add_argument("--shot-name", default="launcher")
    runner.add_argument("--timeout", type=int, default=180)
    runner.add_argument("--mode", choices=("docked", "handheld", "both"), default="docked",
                        help="Console mode in the emulator. Test both before calling a launcher or input change done.")
    runner.add_argument("--data-file", action="append", metavar="NAME=TEXT",
                        help="Write a file into the app's data folder before launch (\\n makes a newline).")
    runner.add_argument("--steps", help="File of autorun lines (finger, dpad, wclick, key, wait ...) run after the launch wait. "
                             "`tap X Y` (pixels, 1280x720) or `tap NAME` (port.json emulator.targets) is a finger press and release.")
    runner.add_argument("--expect-log", action="append", metavar="REGEX",
                        help="Regex that must appear in the app log; a miss fails the run.")
    args = parser.parse_args()
    if args.action == "check":
        return check(args)
    if args.action == "fetch-os":
        fetch_os()
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
