#!/usr/bin/env python3
"""Yetkili bir yerel public checkout'tan SDK snapshot'ını günceller."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from port_studio import SDK, STUDIO, check_path, read_json, sdk_paths, under, write_atomic


REQUIRED = (
    "README.md", "VERSION.json", "Tools/nxv/nxv.py",
    "Guides/PORT_AND_LAUNCHER.md", "Publishing/PUBLISHING.md",
    "Languages/c/native-kit/tools/nxvapp_pack.py", "Languages/c/native-kit/tools/nxwin_imports.py",
    "Languages/c/native-kit/tools/nxv_native/__main__.py",
)


def git(checkout, *args):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], encoding="utf-8", errors="replace"
    ).strip()


def sync(checkout, *, stage=False, record_active=False, verify_tools=True):
    checkout = checkout.resolve(strict=True)
    source = under(checkout, PurePosixPath("SDK"))
    if source.is_relative_to(STUDIO) or STUDIO.is_relative_to(source):
        raise ValueError("Studio dışında temiz bir Nexvyn OS checkout'u seçin.")
    commit = git(checkout, "rev-parse", "--verify", "HEAD")
    if git(checkout, "status", "--porcelain", "--untracked-files=all", "--", "SDK"):
        raise ValueError("Kaynak checkout'un SDK ağacında yerel değişiklik var.")
    for name in REQUIRED:
        if not under(source, PurePosixPath(name)).is_file():
            raise ValueError(f"Kaynak SDK dosyası eksik: {name}")
    versions = read_json(source / "VERSION.json")
    for name in ("os", "sdk", "native"):
        if not isinstance(versions.get(name), str) or not versions[name].strip():
            raise ValueError(f"SDK VERSION.json alanı eksik: {name}")
    # Git'te kayıtlı SDK dosyalarını al. Yok sayılan yerel dosyalar snapshot'a karışmaz.
    tracked = git(checkout, "ls-files", "-z", "--", "SDK").split("\0")
    relative = [PurePosixPath(name).relative_to("SDK") for name in tracked if name]
    if not relative or any(not under(source, name).is_file() for name in relative):
        raise ValueError("SDK ağacında eksik veya normal dosya olmayan bir Git girdisi var.")
    provenance = json.dumps({"repository": "sonerx7/Nexvyn-OS-NX", "commit": commit}, indent=2) + "\n"
    lock = STUDIO / "_temp_sdk_sync.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError(f"Başka SDK güncellemesi sürüyor veya kilit kaldı: {lock}") from None
    try:
        check_path(SDK, missing_ok=True)
        if record_active:
            if not SDK.is_dir():
                raise ValueError("Etkin SDK snapshot'ı yok.")
            for name in relative:
                active = under(SDK, name).read_bytes()
                upstream = (source / name).read_bytes()
                if active != upstream and (
                    (name.suffix not in {".md", ".json", ".py", ".txt", ".h", ".c", ".cpp", ".cmake"})
                    or active.replace(b"\r\n", b"\n") != upstream.replace(b"\r\n", b"\n")
                ):
                    raise ValueError(f"Etkin SDK kaynakla eşleşmiyor: {name}")
            if (git(checkout, "rev-parse", "--verify", "HEAD") != commit
                    or git(checkout, "status", "--porcelain", "--untracked-files=all", "--", "SDK")):
                raise ValueError("Doğrulama sırasında SDK checkout'u değişti.")
            write_atomic(SDK / "STUDIO_SOURCE.json", provenance)
            print(f"Etkin SDK içeriği kaynak commit'i {commit} ile doğrulandı.")
            return
        with tempfile.TemporaryDirectory(prefix="_temp_sdk_sync_", dir=STUDIO) as scratch:
            candidate = Path(scratch) / "sdk"
            for name in relative:
                target = candidate / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, target)
            if (git(checkout, "rev-parse", "--verify", "HEAD") != commit
                    or git(checkout, "status", "--porcelain", "--untracked-files=all", "--", "SDK")):
                raise ValueError("Kopyalama sırasında SDK checkout'u değişti.")
            (candidate / "STUDIO_SOURCE.json").write_text(provenance, encoding="utf-8")
            if verify_tools:
                for tool in sdk_paths(candidate):
                    subprocess.run([sys.executable, "-B", str(tool), "--help"], check=True, stdout=subprocess.DEVNULL)
            if stage:
                candidates = STUDIO / "_SdkCandidates"
                check_path(candidates, missing_ok=True)
                candidates.mkdir(exist_ok=True)
                target = candidates / commit
                check_path(target, missing_ok=True)
                if target.exists():
                    raise ValueError(f"Bu SDK commit'i zaten aday olarak var: {target}")
                candidate.rename(target)
                print(f"SDK adayı hazır: {target}")
                return
            backup = None
            if SDK.exists():
                backups = STUDIO / "_SdkBackups"
                check_path(backups, missing_ok=True)
                backups.mkdir(exist_ok=True)
                backup = Path(tempfile.mkdtemp(prefix="sdk-", dir=backups)) / SDK.name
                SDK.rename(backup)
            try:
                candidate.rename(SDK)
            except OSError:
                if backup is not None:
                    backup.rename(SDK)
                raise
            if backup is not None:
                print(f"Önceki SDK korundu: {backup}")
    finally:
        lock.rmdir()
    print(f"SDK {versions['sdk']} / Native {versions['native']} alındı. Kaynak commit {commit}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-checkout", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--stage", action="store_true", help="Etkin SDK'yı değiştirmeden bir aday oluştur.")
    modes.add_argument("--record-active", action="store_true", help="Mevcut snapshot eşleşirse commit kaydını yaz.")
    args = parser.parse_args()
    try:
        sync(args.from_checkout, stage=args.stage, record_active=args.record_active)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
