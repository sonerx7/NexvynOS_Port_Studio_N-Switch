#!/usr/bin/env python3
"""Port Market'i resmi App Market aracıyla yerel beta olarak paketler."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from port_studio import ROOT, SDK, read_json, sdk_call, sdk_paths, sdk_report, under, write_atomic


PROJECT = ROOT / "SoftwarePorts/port-market"
ITEM = PurePosixPath("Store/Beta/Apps/utilities/port-market")
APP_ID = "com.sonerx7.portmarket"


def install_beta(item, candidate, checkout):
    path = under(checkout, ITEM, missing_ok=True)
    index = under(checkout, PurePosixPath("Store/beta.json"))
    if path.exists():
        current = read_json(path / "source/app.json")
        proposed = read_json(item / "source/app.json")
        if current["id"] != APP_ID:
            raise ValueError("Beta yolunda farklı bir uygulama var.")
        if current["version"] == proposed["version"]:
            digest = hashlib.sha256((path / "port-market.nxvapp").read_bytes()).hexdigest()
            if digest == candidate["sha256"]:
                print(f"Bu beta sürümü zaten kurulu: {path}")
                return
        if tuple(map(int, current["version"].split("."))) >= tuple(map(int, proposed["version"].split("."))):
            raise ValueError("Beta klasörü mevcut. Güncelleme için Port Market sürümünü artırın.")
    catalog = read_json(index)
    if catalog.get("schema") != 1 or not isinstance(catalog.get("apps"), list):
        raise ValueError("Mağaza beta kataloğu beklenen biçimde değil.")
    catalog["apps"] = [entry for entry in catalog["apps"] if entry["id"] != APP_ID] + [candidate]
    catalog["apps"].sort(key=lambda entry: (
        entry["name"].get("en", "") if isinstance(entry["name"], dict) else entry["name"]
    ).casefold())
    catalog["count"] = len(catalog["apps"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".port-market-", dir=path.parent) as work:
        candidate_path = Path(work) / "new"
        shutil.copytree(item, candidate_path)
        previous = Path(work) / "previous"
        if path.exists():
            path.rename(previous)
        try:
            candidate_path.rename(path)
            try:
                write_atomic(index, json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
            except OSError:
                path.rename(candidate_path)
                raise
        except OSError:
            if previous.exists():
                previous.rename(path)
            raise
    print(f"Yerel beta: {path}")


def build(checkout, snapshot, install, checker_checkout):
    report = sdk_report(snapshot)
    pin = read_json(PROJECT / "sdk.lock.json")
    if report["commit"] != pin["commit"]:
        raise ValueError("Seçilen SDK snapshot'ı Port Market sdk.lock.json ile eşleşmiyor.")
    manifest = read_json(PROJECT / "app.json")
    if manifest["id"] != APP_ID:
        raise ValueError("Port Market uygulama kimliği değişmiş.")
    version = manifest["version"]
    for document in ("CHANGELOG.md", "KNOWN_ISSUES.md"):
        if f"\n## {version}\n" not in (PROJECT / document).read_text(encoding="utf-8"):
            raise ValueError(f"Sürüm kaydı eksik: {document}")
    nxv, native, packer = sdk_paths(snapshot)
    module = PROJECT / manifest["main"]
    if manifest.get("runtime") == "native":
        sdk_call(native, "build", PROJECT)
        module = PROJECT / "build" / manifest["main"]
    with tempfile.TemporaryDirectory(prefix="port-market-beta-") as work:
        stage = Path(work)
        tools = stage / "Tools"
        tools.mkdir()
        (stage / "SDK").mkdir()
        for filename in ("build_store.py", "store_layout.py"):
            shutil.copyfile(checkout / "Tools" / filename, tools / filename)
        item = stage / ITEM
        source = item / "source"
        source.mkdir(parents=True)
        for name in ("app.json", "icon.png", "LICENSE", "NOTICE.md"):
            shutil.copyfile(PROJECT / name, source / name)
        if manifest.get("runtime") == "native":
            shutil.copyfile(PROJECT / "LICENSE-IMGUI.txt", source / "LICENSE-IMGUI.txt")
        shutil.copyfile(module, source / manifest["main"])
        shutil.copytree(PROJECT / "lang", source / "lang")
        for name in ("README.md", "CHANGELOG.md", "KNOWN_ISSUES.md", "store.json"):
            shutil.copyfile(PROJECT / name, item / name)
        checker = checker_checkout or (checkout if (checkout / "tools/lua_check.py").is_file() else None)
        sdk_call(nxv, "check", item, *(("--sdk", checker) if checker else ()))
        subprocess.run([sys.executable, "-B", str(tools / "build_store.py")], check=True)
        catalog = read_json(stage / "Store/beta.json")
        entry, = catalog["apps"]
        if entry["id"] != APP_ID or entry["version"] != version or not entry["beta"]:
            raise ValueError("Üretilen beta katalog girdisi beklenen sürüme ait değil.")
        sdk_call(packer, "--verify", item / "port-market.nxvapp")
        output = PROJECT / "build" / f"beta-{version}"
        output.mkdir(exist_ok=True)
        shutil.copytree(item, output / ITEM, dirs_exist_ok=True)
        shutil.copyfile(stage / "Store/beta.json", output / "Store/beta.json")
        print(f"Beta paketi: {output / ITEM / 'port-market.nxvapp'}")
        if install:
            install_beta(item, entry, checkout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True, help="Resmi Store araçlarını içeren yerel Nexvyn OS checkout'u.")
    parser.add_argument("--sdk", type=Path, default=SDK)
    parser.add_argument("--checker-checkout", type=Path, help="İsteğe bağlı tam OS kaynak ağacı ve runtime denetleyicileri.")
    parser.add_argument("--install-local", action="store_true", help="Beta girdisini yerel checkout'a ekle.")
    args = parser.parse_args()
    try:
        build(args.checkout.resolve(), args.sdk.resolve(), args.install_local,
              args.checker_checkout.resolve() if args.checker_checkout else None)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
