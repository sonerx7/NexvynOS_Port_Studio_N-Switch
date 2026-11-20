"""
Run Red Alert 2: Yuri's Revenge in an isolated Ryujinx profile for Nexvyn OS.
Captures genuine screenshots and runtime logs.
"""

import os
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path

WORKSPACE = Path(r"C:\Users\soned\Documents\antigravityProjects\NintendoSwitchProjects\NexvynUygulamaGelistirrrr\RedAlert2Port")
PROFILE = WORKSPACE / '.emulator_profile'
RYUJINX_DIR = Path(r"C:\Users\soned\OneDrive\Masaüstü\ryujinx")
RYUJINX_EXE = RYUJINX_DIR / "Ryujinx.exe"
NEXVYN_NRO = Path(r"C:\Users\soned\Documents\antigravityProjects\NintendoSwitchProjects\SnxOS-NX\NexvynOS.nro")
SOURCE_APP = Path(r"C:\Users\soned\AppData\Roaming\Ryujinx\sdcard\NexvynOS\Applications\com.sonerx7.redalert2.nxvapp")

def setup_profile():
    appdata_ryu = Path(os.environ['APPDATA']) / 'Ryujinx'
    PROFILE.mkdir(parents=True, exist_ok=True)

    # 1. Copy keys and firmware
    for sub in ['system', 'bis/system/Contents/registered']:
        src = appdata_ryu / sub
        dst = PROFILE / sub
        if src.exists() and not dst.exists():
            print(f"Copying {sub}...")
            shutil.copytree(src, dst)

    # 2. Config.json
    cfg_src = appdata_ryu / 'Config.json'
    cfg_dst = PROFILE / 'Config.json'
    if cfg_src.exists() and not cfg_dst.exists():
        shutil.copy2(cfg_src, cfg_dst)

    # 3. SD Card & Settings
    sd = PROFILE / 'sdcard' / 'NexvynOS'
    sd.mkdir(parents=True, exist_ok=True)
    
    config_dir = sd / 'System' / 'Config'
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file = config_dir / 'settings.json'
    
    settings = {}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text(encoding='utf-8-sig'))
        except Exception:
            settings = {}
    
    settings.setdefault('system', {})['reopenWindows'] = False
    settings.setdefault('session', {})['windows'] = []
    settings.setdefault('privacy', {})['telemetry'] = False
    settings.setdefault('updates', {})['autoCheck'] = False
    trusted = settings.setdefault('apps', {}).setdefault('trustedNative', [])
    if 'com.sonerx7.redalert2' not in trusted:
        trusted.append('com.sonerx7.redalert2')
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding='utf-8')

    # 4. Deploy app bundle
    app_target = sd / 'Applications' / 'com.sonerx7.redalert2.nxvapp'
    app_target.mkdir(parents=True, exist_ok=True)
    
    # Copy latest ra2.nxvmod and app.json from build
    shutil.copy2(WORKSPACE / 'build' / 'ra2.nxvmod', app_target / 'ra2.nxvmod')
    shutil.copy2(WORKSPACE / 'app.json', app_target / 'app.json')
    if (WORKSPACE / 'icon.png').exists():
        shutil.copy2(WORKSPACE / 'icon.png', app_target / 'icon.png')
    
    # Link game assets directory
    game_target = app_target / 'game'
    if not game_target.exists():
        if (SOURCE_APP / 'game').exists():
            print("Linking game directory...")
            try:
                os.symlink(SOURCE_APP / 'game', game_target, target_is_directory=True)
            except Exception:
                shutil.copytree(SOURCE_APP / 'game', game_target)

    # 5. Autorun script
    autorun_script = (
        "wait 3\n"
        "setup tr\n"
        "wait 2\n"
        "closeall\n"
        "trust com.sonerx7.redalert2\n"
        "launch com.sonerx7.redalert2\n"
        "wait 100\n"
        "key space\n"
        "wait 2\n"
        "click 640 360\n"
        "wait 5\n"
        "shot ra2_interactive_menu\n"
        "wait 5\n"
        "exit\n"
    )
    (sd / 'autorun.txt').write_text(autorun_script, encoding='utf-8')
    print("Autorun script configured.")

def run_emulator(timeout=150):
    autoshots_dir = PROFILE / 'sdcard' / 'NexvynOS' / 'autoshots'
    if autoshots_dir.exists():
        for old_shot in autoshots_dir.glob("*.png"):
            try: old_shot.unlink()
            except Exception: pass
            
    print("Launching Ryujinx with isolated profile...")
    args = [
        str(RYUJINX_EXE),
        '--root-data-dir', str(PROFILE),
        str(NEXVYN_NRO)
    ]
    proc = subprocess.Popen(args)
    print(f"Ryujinx running with PID: {proc.pid}")
    
    start_t = time.time()
    try:
        while time.time() - start_t < timeout:
            if proc.poll() is not None:
                print(f"Ryujinx exited with code {proc.returncode}")
                break
            time.sleep(2)
        else:
            print("Timeout reached, closing Ryujinx...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except KeyboardInterrupt:
        proc.kill()

    # Harvest screenshots
    shots_out = WORKSPACE / 'screenshots'
    shots_out.mkdir(parents=True, exist_ok=True)
    
    if autoshots_dir.exists():
        for f in autoshots_dir.glob("ra2_live_*.png"):
            shutil.copy2(f, shots_out / f.name)
            print(f"Captured: {f.name}")

    # Copy log
    log_src = PROFILE / 'sdcard' / 'NexvynOS' / 'System' / 'Logs' / 'Apps' / 'com.sonerx7.redalert2.log'
    if log_src.exists():
        shutil.copy2(log_src, WORKSPACE / 'build' / 'ra2_app.log')
        print("Exported RA2 app log.")

if __name__ == '__main__':
    setup_profile()
    run_emulator()
