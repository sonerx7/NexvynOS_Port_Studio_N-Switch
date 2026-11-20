"""
Package & deploy Red Alert 2: Yuri's Revenge Nexvyn OS Native SDK 1.2 (.nxvapp).
- Verifies ABI imports with nxwin_imports.py
- Verifies 8-language localization with nxv_i18n.py
- Verifies ImGui launcher design with design_check.py
- Builds dist/com.sonerx7.redalert2.nxvapp (folder) and dist/ra2.nxvapp (signed/packed zip)
- Optionally links/deploys game files from C:\Program Files (x86)\DODI-Repacks\Red Alert 2\Game
  into Ryujinx SD card for instant testing.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK_TOOLS = ROOT / "work" / "nexvyn_sdk_latest" / "SDK" / "Languages" / "c" / "native-kit" / "tools"
BUILD_NX = ROOT / "build_nx"
DIST_DIR = ROOT / "dist"
BUNDLE_DIR = DIST_DIR / "com.sonerx7.redalert2.nxvapp"
DODI_GAME_DIR = Path(r"C:\Program Files (x86)\DODI-Repacks\Red Alert 2\Game")
RYU_APP_DIR = Path(os.environ.get("APPDATA", "")) / "Ryujinx" / "sdcard" / "NexvynOS" / "Applications" / "com.sonerx7.redalert2.nxvapp"


def run(cmd, desc):
    print(f"\n[*] {desc}...")
    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        print(f"[FAIL] {desc} (exit {res.returncode})")
        sys.exit(res.returncode)


def main():
    mod_path = BUILD_NX / "ra2.nxvmod"
    if not mod_path.exists():
        print(f"[ERROR] {mod_path} not found. Run build_nx.sh first.")
        sys.exit(1)

    # 1. SDK checks
    run([sys.executable, str(SDK_TOOLS / "nxwin_imports.py"), "check", str(mod_path)],
        "ABI import check (nxwin_imports.py)")
    run([sys.executable, str(SDK_TOOLS / "nxv_i18n.py"), "--check", str(ROOT)],
        "Localization check (nxv_i18n.py)")
    run([sys.executable, str(SDK_TOOLS / "design_check.py"), str(ROOT / "src" / "nx" / "launcher.cpp")],
        "Design check (design_check.py)")

    # 2. Assemble bundle folder
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(mod_path, BUNDLE_DIR / "ra2.nxvmod")
    shutil.copy2(ROOT / "app.json", BUNDLE_DIR / "app.json")
    shutil.copy2(ROOT / "icon.png", BUNDLE_DIR / "icon.png")
    shutil.copy2(ROOT / "LICENSE", BUNDLE_DIR / "LICENSE")
    if (ROOT / "NOTICE.md").exists():
        shutil.copy2(ROOT / "NOTICE.md", BUNDLE_DIR / "NOTICE.md")

    shutil.copytree(ROOT / "lang", BUNDLE_DIR / "lang")
    shutil.copytree(ROOT / "assets", BUNDLE_DIR / "assets")

    # 3. Pack .nxvapp archive with manifest.sha256
    out_pkg = DIST_DIR / "redalert2.nxvapp"
    if out_pkg.exists():
        out_pkg.unlink()
    run([sys.executable, str(SDK_TOOLS / "nxvapp_pack.py"), str(BUNDLE_DIR), "-o", str(out_pkg)],
        "Pack .nxvapp (nxvapp_pack.py)")
    print(f"[OK] Packed: {out_pkg} ({out_pkg.stat().st_size / (1024*1024):.1f} MB)")

    # 4. Deploy to Ryujinx SD card (if Ryujinx sdcard exists)
    ryu_apps_root = RYU_APP_DIR.parent
    if ryu_apps_root.exists():
        print(f"\n[*] Deploying bundle to Ryujinx SD card: {RYU_APP_DIR}")
        RYU_APP_DIR.mkdir(parents=True, exist_ok=True)
        for item in ["ra2.nxvmod", "app.json", "icon.png", "LICENSE"]:
            if (BUNDLE_DIR / item).exists():
                shutil.copy2(BUNDLE_DIR / item, RYU_APP_DIR / item)
        for folder in ["lang", "assets"]:
            dst = RYU_APP_DIR / folder
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(BUNDLE_DIR / folder, dst)

        # Ensure game files exist on Ryujinx SD card from DODI-Repacks
        game_dst = RYU_APP_DIR / "game"
        if not (game_dst / "gamemd.exe").exists() and DODI_GAME_DIR.exists():
            print(f"[*] Copying Red Alert 2 game files from {DODI_GAME_DIR} -> {game_dst}")
            game_dst.mkdir(parents=True, exist_ok=True)
            wanted_exts = {".exe", ".mix", ".dll", ".ini", ".csf", ".dat"}
            copied = 0
            for f in DODI_GAME_DIR.iterdir():
                if f.is_file() and f.suffix.lower() in wanted_exts:
                    shutil.copy2(f, game_dst / f.name)
                    copied += 1
            print(f"[OK] Copied {copied} game files to {game_dst}")
        elif (game_dst / "gamemd.exe").exists():
            print(f"[OK] Game files already present in {game_dst}")

    print("\n[SUCCESS] Build, validation, and packaging complete!")


if __name__ == "__main__":
    main()
