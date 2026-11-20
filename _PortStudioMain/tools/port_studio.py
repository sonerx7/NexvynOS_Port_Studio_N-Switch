#!/usr/bin/env python3
"""Nexvyn Port Studio: hazırlık, denetim ve iki kanallı yerel paketleme."""

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "_PortStudioMain"
SDK = STUDIO / "nexvyn_sdk"
STUDIO_VERSION = "0.2.0"
NXV = SDK / "Tools/nxv/nxv.py"
NATIVE_TOOLS = SDK / "Languages/c/native-kit/tools"
PACKER = NATIVE_TOOLS / "nxvapp_pack.py"
NATIVE = NATIVE_TOOLS / "nxv_native/__main__.py"
PORT_TYPES = {"GamePorts": ("game", "Games"), "SoftwarePorts": ("software", "Apps")}
STORE_CATEGORIES = {
    "Games": {"action", "arcade", "board", "cards", "casual", "puzzle", "racing", "sports", "strategy", "word"},
    "Apps": {"productivity", "utilities", "media", "internet", "developer", "system", "switch", "other"},
}
VERSION = r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}"
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
APP_ID = r"[a-z][a-z0-9-]*(?:\.[a-z0-9][a-z0-9_-]*){2,}"
RELEASE_ROOT = "_RealesedBuilds"
PRIVATE_SUFFIXES = {
    ".exe", ".dll", ".msi", ".zip", ".rar", ".7z", ".tar", ".gz", ".xz",
    ".iso", ".rom", ".nsp", ".xci", ".nxvapp", ".pem", ".key", ".pfx", ".p12",
    ".csf", ".mix", ".mpq", ".wad", ".pak", ".vpk", ".bsp", ".bik", ".smk",
}
PRIVATE_DIRS = {"_localdata", "userdata", "private", "saves"}
FORBIDDEN_DIRS = {"__pycache__", "dist", "appmarket", "_realesedbuilds", "build"}
FORBIDDEN_NAMES = {"manifest.sha256", "manifest.sig", "id_rsa", "id_ed25519", "desktop.ini", "thumbs.db"}


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Tekrarlanan JSON alanı: {key}")
            result[key] = value
        return result

    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON nesnesi bekleniyor.")
    return data


def relative_path(value):
    if not isinstance(value, str):
        raise ValueError("Dosya yolu metin olmalı.")
    parts = value.split("/")
    for part in parts:
        if (
            not part or part.startswith(".") or part.endswith((" ", "."))
            or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
            or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL"}
            or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", part.split(".")[0].upper())
        ):
            raise ValueError(f"Güvenli bir göreli paket yolu değil: {value!r}")
    return PurePosixPath(value)


def check_path(path, *, missing_ok=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return
        raise
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"Bağlantı veya junction kullanılamaz: {path}")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ValueError(f"Normal dosya veya klasör bekleniyor: {path}")


def under(base, rel, *, missing_ok=False):
    current = base
    for part in rel.parts:
        current /= part
        check_path(current, missing_ok=missing_ok)
    return current


def port_path(value):
    raw = Path(os.path.abspath(value))
    if raw.parent.parent != ROOT or raw.parent.name not in PORT_TYPES:
        raise ValueError("Doğrudan GamePorts veya SoftwarePorts altındaki bir portu seçin.")
    check_path(raw.parent)
    check_path(raw)
    if not raw.is_dir():
        raise ValueError(f"Port klasörü bulunamadı: {raw}")
    return raw


def list_files(base, relative=None):
    directory = base if relative is None else base / relative
    for item in sorted(directory.iterdir()):
        rel = relative_path(item.name) if relative is None else relative / relative_path(item.name)
        check_path(item)
        if item.is_dir():
            yield from list_files(base, rel)
        else:
            yield rel


def check_payload_name(path, *, public):
    names = {part.casefold() for part in path.parts}
    suffix = path.suffix.casefold()
    if names & (FORBIDDEN_DIRS | FORBIDDEN_NAMES) or suffix in {".pem", ".key", ".pfx", ".p12", ".nxvapp"}:
        raise ValueError(f"Paket girdisi olarak kullanılamaz: {path}")
    if public and (names & PRIVATE_DIRS or suffix in PRIVATE_SUFFIXES):
        raise ValueError(f"Mağaza kaynağına alınamaz: {path}")


def unique_paths(paths):
    seen = {}
    files = set()
    for path in paths:
        folded = path.as_posix().casefold()
        if folded in files:
            raise ValueError(f"Paket yolu yineleniyor: {path}")
        files.add(folded)
        for item in (*path.parents, path):
            key = item.as_posix().casefold()
            if seen.setdefault(key, item) != item:
                raise ValueError(f"Paket yollarında büyük/küçük harf çakışması: {item}")
    for path in paths:
        if any(parent.as_posix().casefold() in files for parent in path.parents):
            raise ValueError(f"Paket yolunda dosya/klasör çakışması: {path}")


def copy_files(entries, destination):
    for rel, source in entries.items():
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def write_atomic(target, content):
    check_path(target, missing_ok=True)
    with tempfile.TemporaryDirectory(prefix=".port-studio-", dir=target.parent) as work:
        candidate = Path(work) / target.name
        candidate.write_text(content, encoding="utf-8", newline="\n")
        os.replace(candidate, target)


def sdk_call(tool, *args):
    if not tool.is_file():
        raise ValueError(f"Yerel public SDK aracı eksik: {tool}")
    result = subprocess.run([sys.executable, "-B", str(tool), *map(str, args)])
    if result.returncode:
        raise ValueError(f"SDK denetimi başarısız: {tool.name} (çıkış {result.returncode})")


def sdk_paths(snapshot):
    return (
        snapshot / NXV.relative_to(SDK),
        snapshot / NATIVE.relative_to(SDK),
        snapshot / PACKER.relative_to(SDK),
    )


def sdk_report(snapshot):
    versions = read_json(snapshot / "VERSION.json")
    source = snapshot / "STUDIO_SOURCE.json"
    provenance = read_json(source) if source.is_file() else {}
    return {
        "path": str(snapshot), "versions": versions, "commit": provenance.get("commit"),
        "tools": {str(path.relative_to(snapshot)): path.is_file() for path in sdk_paths(snapshot)},
    }


def doctor(args):
    snapshot = args.sdk.resolve() if args.sdk else SDK
    report = sdk_report(snapshot)
    report["studioVersion"] = STUDIO_VERSION
    checkout = args.upstream
    if checkout:
        report["upstreamVersions"] = read_json(checkout / "SDK/VERSION.json")
        head = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True,
        )
        report["upstreamCommit"] = head.stdout.strip()
        report["matchesUpstreamCommit"] = (
            report["commit"] == report["upstreamCommit"] if report["commit"] else None
        )
    if args.port:
        port = port_path(args.port)
        report["port"] = str(port.relative_to(ROOT))
        pin = port / "sdk.lock.json"
        report["portSdkCommit"] = read_json(pin).get("commit") if pin.is_file() else None
        report["portConfigured"] = (port / "port.json").is_file()
    windows = os.name == "nt"
    devkit = Path(os.environ.get("DEVKITPRO_WIN", "C:/devkitPro") if windows else os.environ.get("DEVKITPRO", "/opt/devkitpro"))
    report["toolchain"] = {
        name: shutil.which(name) for name in ("git", "cmake", "ninja")
    }
    report["toolchain"]["devkitA64"] = (
        devkit / "devkitA64/bin" / ("aarch64-none-elf-gcc.exe" if windows else "aarch64-none-elf-gcc")
    ).is_file()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(report["tools"].values()) else 1


def config_for(port):
    config = read_json(under(port, PurePosixPath("port.json")))
    slug = config.get("slug")
    category = config.get("storeCategory")
    public_files = config.get("publicFiles")
    data = config.get("localData")
    if not isinstance(slug, str) or not re.fullmatch(SLUG, slug):
        raise ValueError("port.json: slug küçük harf, rakam ve kısa çizgiden oluşmalı.")
    store_type = PORT_TYPES[port.parent.name][1]
    if not isinstance(category, str) or category not in STORE_CATEGORIES[store_type]:
        raise ValueError(f"port.json: storeCategory seçenekleri: {', '.join(sorted(STORE_CATEGORIES[store_type]))}")
    if not isinstance(public_files, list) or not public_files or not isinstance(data, list):
        raise ValueError("port.json: publicFiles dolu bir liste, localData bir liste olmalı.")
    mappings = []
    for mapping in data:
        if not isinstance(mapping, dict) or set(mapping) != {"from", "to"}:
            raise ValueError("localData girdileri from ve to alanları içermeli.")
        origin, target = relative_path(mapping["from"]), relative_path(mapping["to"])
        check_payload_name(target, public=False)
        mappings.append((origin, target))
    return slug, category, [relative_path(path) for path in public_files], mappings


def release_documents(port, version):
    for name in ("CHANGELOG.md", "KNOWN_ISSUES.md"):
        path = under(port, PurePosixPath(name))
        section = re.search(
            rf"^## (?:\[{re.escape(version)}\]|{re.escape(version)})(?=\s|$)[^\n]*\n(.*?)(?=^## |\Z)",
            path.read_text(encoding="utf-8-sig"), re.MULTILINE | re.DOTALL,
        )
        content = section.group(1).strip() if section else ""
        if not content or "<!--" in content:
            raise ValueError(f"{name}: ## {version} altında sürüm kaydı gerekli.")
    for name in ("PORT.md", "DISTRIBUTION.md"):
        path = under(port, PurePosixPath(name))
        content = path.read_text(encoding="utf-8-sig")
        if not content.strip() or "<!-- PORT_STUDIO_TEMPLATE -->" in content:
            raise ValueError(f"{name}: portun kayıtlarını tamamlayın ve şablon işaretini kaldırın.")


def public_source(port, slug, category, paths, mappings):
    store_type = PORT_TYPES[port.parent.name][1]
    item_rel = relative_path(f"AppMarket/Store/{store_type}/{category}/{slug}")
    item = under(port, item_rel)
    source = under(item, PurePosixPath("source"))
    unique_paths(paths)
    for rel in paths:
        check_payload_name(rel, public=True)
        for _, target in mappings:
            public = rel.as_posix().casefold()
            private = target.as_posix().casefold()
            if public == private or public.startswith(private + "/") or private.startswith(public + "/"):
                raise ValueError(f"Mağaza girdisi kişisel veri hedefiyle çakışıyor: {rel}")
    actual = set(list_files(source))
    missing = set(paths) - actual
    extra = actual - set(paths)
    if missing or extra:
        changes = [*(f"eksik: {p}" for p in sorted(missing)), *(f"liste dışı: {p}" for p in sorted(extra))]
        raise ValueError("Mağaza kaynağı publicFiles listesiyle birebir eşleşmeli:\n  " + "\n  ".join(changes))
    entries = {rel: source / rel for rel in paths}
    for notice in ("LICENSE", "NOTICE.md"):
        rel = PurePosixPath(notice)
        if rel not in entries or not entries[rel].read_text(encoding="utf-8-sig").strip():
            raise ValueError(f"Mağaza kaynağında dolu {notice} gerekli.")
    manifest = read_json(under(source, PurePosixPath("app.json")))
    app_id, version = manifest.get("id"), manifest.get("version")
    if not isinstance(app_id, str) or len(app_id) > 128 or not re.fullmatch(APP_ID, app_id):
        raise ValueError("app.json: küçük harfli kalıcı uygulama kimliği gerekli (com.sahip.port).")
    if not isinstance(version, str) or not re.fullmatch(VERSION, version):
        raise ValueError("app.json: sürüm MAJOR.MINOR.PATCH biçiminde olmalı.")
    if manifest.get("runtime") != "native" or manifest.get("mode") not in {"window", "fullscreen"}:
        raise ValueError("Stüdyo paketi window veya fullscreen modunda çalışan entegre native modül olmalı.")
    main = relative_path(manifest.get("main"))
    icon = relative_path(manifest.get("icon", "icon.png"))
    if main.suffix != ".nxvmod" or main not in entries or icon not in entries:
        raise ValueError("app.json: main (.nxvmod) ve icon mağaza kaynak listesinde bulunmalı.")
    if store_type == "Games" and (manifest.get("category") != "games" or manifest.get("gamepad") is not True):
        raise ValueError('Oyun manifestinde "category": "games" ve "gamepad": true gerekli.')
    release_documents(port, version)
    return item, source, entries, main, app_id, version


def local_entries(root, mappings, public_paths):
    if bool(mappings) != bool(root):
        raise ValueError("localData eşlemesi varsa --data-root gerekli. Veri gerekmiyorsa ikisini de boş bırakın.")
    if not mappings:
        return {}
    base = Path(os.path.abspath(root))
    if not base.is_dir():
        raise ValueError(f"Yerel veri klasörü bulunamadı: {base}")
    for ancestor in (*reversed(base.parents), base):
        check_path(ancestor)
    entries = {}
    destinations = list(public_paths)
    for origin, dest in mappings:
        source = under(base, origin)
        children = list(list_files(source)) if source.is_dir() else [None]
        if not children:
            raise ValueError(f"Yerel veri klasörü boş: {origin}")
        for child in children:
            target = dest if child is None else dest / child
            check_payload_name(origin if child is None else origin / child, public=False)
            check_payload_name(target, public=False)
            destinations.append(target)
            entries[target] = source if child is None else source / child
    unique_paths(destinations)
    return entries


def store_metadata(item, slug):
    required = {"source", "README.md", "store.json"}
    optional = {"screenshots", "icon.png", f"{slug}.nxvapp"}
    screenshot_count = 0
    for entry in item.iterdir():
        check_path(entry)
        if entry.name not in required | optional:
            raise ValueError(f"Mağaza gönderi klasöründe beklenmeyen girdi: {entry.name}")
        if entry.name == "screenshots":
            for screenshot in list_files(entry):
                if len(screenshot.parts) != 1 or screenshot.suffix != ".png":
                    raise ValueError(f"Mağaza ekran görüntüsü PNG dosyası olmalı: {screenshot}")
                with (entry / screenshot).open("rb") as image:
                    if image.read(16) != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
                        raise ValueError(f"Geçersiz mağaza ekran görüntüsü: {screenshot}")
                screenshot_count += 1
        elif entry.name != "source" and not entry.is_file():
            raise ValueError(f"Mağaza girdisi dosya olmalı: {entry.name}")
    for name in ("README.md", "store.json"):
        path = under(item, PurePosixPath(name))
        content = path.read_text(encoding="utf-8-sig")
        if not content.strip() or "PORT_STUDIO_TEMPLATE" in content:
            raise ValueError(f"Mağaza bilgisi tamamlanmalı: {name}")
    metadata = read_json(item / "store.json")
    if metadata.get("kind") != "port":
        raise ValueError('Mağaza kaydında "kind": "port" gerekli.')
    shots = metadata.get("shots")
    if screenshot_count < 3 and (
        not isinstance(shots, list) or not 3 <= len(shots) <= 5 or any(not shot for shot in shots)
    ):
        raise ValueError("Mağaza için en az üç ekran görüntüsü veya 3–5 SDK çekim senaryosu gerekli.")


def prepare(args):
    port = port_path(args.port)
    snapshot = args.sdk.resolve() if args.sdk else SDK
    nxv, native, packer = sdk_paths(snapshot)
    pin = port / "sdk.lock.json"
    if pin.is_file():
        expected = read_json(pin).get("commit")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{40}", expected):
            raise ValueError("sdk.lock.json: 40 karakterli kaynak commit kimliği gerekli.")
        if sdk_report(snapshot)["commit"] != expected:
            raise ValueError(f"Port SDK commit'i {expected}. Eşleşen snapshot'ı --sdk ile seçin.")
    slug, category, paths, mappings = config_for(port)
    item, source, entries, main, app_id, version = public_source(port, slug, category, paths, mappings)
    if args.channel == "store":
        if getattr(args, "data_root", None):
            raise ValueError("Mağaza paketinde --data-root kullanılamaz.")
        store_metadata(item, slug)
    if args.action == "check":
        sdk_call(nxv, "check", item if args.channel == "store" else source)
        sdk_call(native, "check-win", source / main)
        print(f"Kaynak denetimi tamamlandı: {app_id} {version} ({args.channel})")
        return

    if args.channel == "local":
        personal = local_entries(args.data_root, mappings, entries)
        port_type = PORT_TYPES[port.parent.name][0]
        output_dir = under(ROOT, relative_path(f"{RELEASE_ROOT}/{port_type}/{slug}"), missing_ok=True)
        output = output_dir / f"{app_id}-{version}-local.nxvapp"
    else:
        personal = {}
        output_dir = item
        output = item / f"{slug}.nxvapp"
    # Verify a completed candidate before replacing an earlier build.
    output_dir.mkdir(parents=True, exist_ok=True)
    check_path(output, missing_ok=True)
    with tempfile.TemporaryDirectory(prefix=".port-studio-", dir=output_dir) as work:
        temp = Path(work)
        stage = temp / ("source" if args.channel == "store" else "bundle")
        candidate = Path(work) / "candidate.nxvapp"
        copy_files(entries, stage)
        if args.channel == "store":
            for metadata in ("store.json", "README.md"):
                shutil.copyfile(item / metadata, temp / metadata)
            if (item / "screenshots").is_dir():
                shutil.copytree(item / "screenshots", temp / "screenshots")
        sdk_call(nxv, "check", stage)
        sdk_call(native, "check-win", stage / main)
        copy_files(personal, stage)
        sdk_call(packer, stage, "-o", candidate)
        sdk_call(packer, "--verify", candidate)
        os.replace(candidate, output)
    print(f"Paket hazır: {output.relative_to(ROOT)}")


def init_port(args):
    name = relative_path(args.slug)
    if len(name.parts) != 1 or not re.fullmatch(SLUG, args.slug):
        raise ValueError("Port adı küçük harf, rakam ve kısa çizgiden oluşmalı.")
    port_type = "GamePorts" if args.kind == "game" else "SoftwarePorts"
    store_type = PORT_TYPES[port_type][1]
    if args.category not in STORE_CATEGORIES[store_type]:
        raise ValueError(f"Mağaza kategorileri: {', '.join(sorted(STORE_CATEGORIES[store_type]))}")
    parent = ROOT / port_type
    check_path(parent)
    port = parent / name
    port.mkdir()
    templates = STUDIO / "templates"
    for filename in ("PORT.md", "DISTRIBUTION.md", "CHANGELOG.md", "KNOWN_ISSUES.md"):
        shutil.copyfile(templates / filename, port / filename)
    config = {
        "slug": args.slug,
        "storeCategory": args.category,
        "publicFiles": ["app.json", "icon.png", "LICENSE", "NOTICE.md"],
        "localData": [],
    }
    (port / "port.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    item = port / "AppMarket" / "Store" / store_type / args.category / args.slug
    (item / "source").mkdir(parents=True)
    shutil.copyfile(templates / "STORE_README.md", item / "README.md")
    shutil.copyfile(templates / "store.json", item / "store.json")
    print(f"Port dosyası açıldı: {port.relative_to(ROOT)}/PORT.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"Nexvyn Port Studio {STUDIO_VERSION}")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="Yeni port için fizibilite ve sürüm kayıtlarını oluşturur.")
    init.add_argument("kind", choices=("game", "software"))
    init.add_argument("slug")
    init.add_argument("category")
    status = sub.add_parser("doctor", help="SDK, araç zinciri ve isteğe bağlı port durumunu gösterir.")
    status.add_argument("--json", action="store_true", help="Makine tarafından okunabilir çıktı.")
    status.add_argument("--port")
    status.add_argument("--sdk", type=Path)
    status.add_argument("--upstream", type=Path, help="Karşılaştırılacak yerel public OS checkout'u.")
    for action in ("check", "pack"):
        command = sub.add_parser(action)
        command.add_argument("channel", choices=("local", "store"))
        command.add_argument("port")
        command.add_argument("--sdk", type=Path)
        if action == "pack":
            command.add_argument("--data-root", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "init":
            init_port(args)
        elif args.action == "doctor":
            return doctor(args)
        else:
            prepare(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
