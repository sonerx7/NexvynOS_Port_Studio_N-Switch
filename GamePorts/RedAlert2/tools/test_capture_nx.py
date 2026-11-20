"""
Launch Red Alert 2: Yuri Port (v1.1.0, Native SDK 1.2) in isolated Ryujinx profile,
capture screenshots of both the Launcher UI and the running game, and export logs.
"""

import os
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / ".emulator_profile"
RYUJINX_EXE = Path(r"C:\Users\soned\OneDrive\Masaüstü\ryujinx\Ryujinx.exe")
NEXVYN_NRO = Path(r"C:\Users\soned\Documents\antigravityProjects\NintendoSwitchProjects\SnxOS-NX\build\release-candidate\NexvynOS-1.3.28-beta.2-efb1fc2b.nro")
BUNDLE_DIR = ROOT / "dist" / "com.sonerx7.redalert2.nxvapp"
DODI_GAME_DIR = Path(r"C:\Program Files (x86)\DODI-Repacks\Red Alert 2\Game")
SHOTS_OUT = ROOT / "screenshots" / "v1_1_live"


def setup_profile():
    appdata_ryu = Path(os.environ["APPDATA"]) / "Ryujinx"
    PROFILE.mkdir(parents=True, exist_ok=True)

    for sub in ["system", "bis/system/Contents/registered"]:
        src = appdata_ryu / sub
        dst = PROFILE / sub
        if src.exists() and not dst.exists():
            shutil.copytree(src, dst)

    cfg_src = appdata_ryu / "Config.json"
    cfg_dst = PROFILE / "Config.json"
    if cfg_src.exists() and not cfg_dst.exists():
        shutil.copy2(cfg_src, cfg_dst)

    sd = PROFILE / "sdcard" / "NexvynOS"
    config_dir = sd / "System" / "Config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file = config_dir / "settings.json"
    settings = {}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text(encoding="utf-8-sig"))
        except Exception:
            settings = {}

    settings.setdefault("system", {})["reopenWindows"] = False
    settings.setdefault("session", {})["windows"] = []
    settings.setdefault("privacy", {})["telemetry"] = False
    settings.setdefault("updates", {})["autoCheck"] = False
    settings.setdefault("native", {})["windowMenu"] = True
    trusted = settings.setdefault("apps", {}).setdefault("trustedNative", [])
    if "com.sonerx7.redalert2" not in trusted:
        trusted.append("com.sonerx7.redalert2")
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    app_dst = sd / "Applications" / "com.sonerx7.redalert2.nxvapp"
    app_dst.mkdir(parents=True, exist_ok=True)
    for item in ["ra2.nxvmod", "app.json", "icon.png", "LICENSE"]:
        if (BUNDLE_DIR / item).exists():
            shutil.copy2(BUNDLE_DIR / item, app_dst / item)
    for folder in ["lang", "assets"]:
        d = app_dst / folder
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(BUNDLE_DIR / folder, d)

    game_dst = app_dst / "game"
    if not (game_dst / "gamemd.exe").exists() and DODI_GAME_DIR.exists():
        game_dst.mkdir(parents=True, exist_ok=True)
        for f in DODI_GAME_DIR.iterdir():
            if f.is_file() and f.suffix.lower() in {".exe", ".mix", ".dll", ".ini", ".csf", ".dat"}:
                shutil.copy2(f, game_dst / f.name)

    # Autorun sequence on Nexvyn OS 1.3.28-beta.2 (1920x1080 fullscreen launcher):
    # Video tab: 200, 170 | Controls tab: 320, 170 | PLAY button: 1815, 108
    autorun = (
        "wait 3\n"
        "setup tr\n"
        "wait 2\n"
        "closeall\n"
        "trust com.sonerx7.redalert2\n"
        "launch com.sonerx7.redalert2\n"
        "wait 4\n"
        "shot ra2_v12_01_launcher_overview\n"
        "wait 1\n"
        "click 200 170\n"
        "wait 1\n"
        "shot ra2_v12_02_launcher_video\n"
        "wait 1\n"
        "click 320 170\n"
        "wait 1\n"
        "shot ra2_v12_03_launcher_controls\n"
        "wait 1\n"
        "click 1815 108\n"
        "wait 22\n"
        "shot ra2_v12_04_game_running\n"
        "wait 2\n"
        "exit\n"
    )
    (sd / "autorun.txt").write_text(autorun, encoding="utf-8")


def run_test(timeout=110):
    autoshots = PROFILE / "sdcard" / "NexvynOS" / "autoshots"
    if autoshots.exists():
        for f in autoshots.glob("*.png"):
            try:
                f.unlink()
            except Exception:
                pass

    local_nro = PROFILE / "NexvynOS_test.nro"
    if not local_nro.exists() or local_nro.stat().st_size != NEXVYN_NRO.stat().st_size:
        shutil.copy2(NEXVYN_NRO, local_nro)

    proc = subprocess.Popen([str(RYUJINX_EXE), "--root-data-dir", str(PROFILE), str(local_nro)])
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            break
        time.sleep(2)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    SHOTS_OUT.mkdir(parents=True, exist_ok=True)
    captured = []
    if autoshots.exists():
        for f in sorted(autoshots.glob("ra2_v12_*.png")):
            dst = SHOTS_OUT / f.name
            shutil.copy2(f, dst)
            captured.append(dst)
            print(f"[SHOT] {dst}")

    log_src = PROFILE / "sdcard" / "NexvynOS" / "System" / "Logs" / "Apps" / "com.sonerx7.redalert2.log"
    if log_src.exists():
        log_dst = ROOT / "build_nx" / "ra2_v11_app.log"
        shutil.copy2(log_src, log_dst)
        print(f"[LOG] {log_dst}")
    else:
        print("[WARN] App log not found.")

    print(f"Done. Captured {len(captured)} screenshot(s).")


if __name__ == "__main__":
    setup_profile()
    run_test()
