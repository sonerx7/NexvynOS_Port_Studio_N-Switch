#!/usr/bin/env python3
"""Prepare the SD catalog and the public distribution archive candidate for Port Market."""

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from port_studio import (
    APP_ID, PACKER, PORT_TYPES, RELEASE_ROOT, ROOT, VERSION, check_manifest_sdk, check_package_limits, check_path,
    config_for, port_path, port_sdk, public_source, read_json, relative_path, require_release,
    sdk_call, sdk_paths, store_metadata, write_atomic,
)


HEADER = "NXVPORTMARKET\t1\n"
FILE_NAME = r"[A-Za-z0-9][A-Za-z0-9._-]*\.nxvapp"
ITEM_ID = r"[A-Za-z0-9][A-Za-z0-9._-]{2,99}"
ARCHIVE_URL = rf"https://archive\.org/download/{ITEM_ID}/{FILE_NAME}"


def package_fields(package, packer=PACKER):
    check_path(package)
    if ".." in package.name or not re.fullmatch(FILE_NAME, package.name):
        raise ValueError(f"Invalid package name for Port Market: {package.name}")
    with ZipFile(package) as bundle:
        files = bundle.infolist()
        check_package_limits(files, package.name)
        for required in ("app.json", "manifest.sha256"):
            if bundle.namelist().count(required) != 1:
                raise ValueError(f"{package.name}: {required} eksik veya yineleniyor.")
        info = bundle.getinfo("app.json")
        if info.file_size > 64 * 1024:
            raise ValueError(f"{package.name}: manifest is too large.")
        manifest = json.loads(bundle.read(info))
    if not isinstance(manifest, dict):
        raise ValueError(f"{package.name}: manifest must be a JSON object.")
    app_id = manifest.get("id")
    version = manifest.get("version")
    if not isinstance(app_id, str) or not re.fullmatch(APP_ID, app_id):
        raise ValueError(f"{package.name}: invalid app ID.")
    if not isinstance(version, str) or not re.fullmatch(VERSION, version):
        raise ValueError(f"{package.name}: invalid version.")
    name = manifest.get("name")
    if isinstance(name, dict):
        name = name.get("en") or name.get("tr")
    if not isinstance(name, str) or not name.strip():
        name = app_id
    name = " ".join(name.split())
    if len(name.encode("utf-8")) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError(f"{package.name}: invalid display name.")
    sdk_call(packer, "--verify", package)
    with package.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else sha256(stream)
    return app_id, name, version, package.stat().st_size, digest


def sha256(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def archive_row(path):
    row = read_json(path)
    values = tuple(row.get(key) for key in ("kind", "name", "version", "size", "sha256", "url"))
    kind, name, version, size, digest, url = values
    if (kind not in {"game", "software"} or not isinstance(name, str) or not name.strip()
            or len(name.encode("utf-8")) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or not isinstance(version, str) or not re.fullmatch(VERSION, version)
            or type(size) is not int or not 0 < size < 10_000_000_000
            or not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{64}", digest)
            or not isinstance(url, str) or ".." in url or not re.fullmatch(ARCHIVE_URL, url)):
        raise ValueError(f"Invalid archive record: {path}")
    return kind, name, version, size, digest, "", url


def catalog(args):
    release = args.release_root.resolve()
    check_path(release)
    rows = []
    for kind in ("game", "software"):
        folder = release / kind
        check_path(folder)
        ports = []
        for child in sorted(folder.iterdir()):
            if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", child.name) and child.is_dir():
                check_path(child)
                ports.extend(child.glob("*.nxvapp"))
        for package in sorted([*folder.glob("*.nxvapp"), *ports]):
            _, name, version, size, digest = package_fields(package)
            rows.append((kind, name, version, size, digest, package.relative_to(release).as_posix(), ""))
    rows.extend(archive_row(path) for path in args.archive)
    if len(rows) > 256 or len({(r[5] or r[6]).casefold() for r in rows}) != len(rows):
        raise ValueError("The catalog can hold at most 256 unique package entries.")
    rows.sort(key=lambda row: (row[0], row[1].casefold(), row[2], row[5] or row[6]))
    output = release / "port-market.tsv"
    write_atomic(output, HEADER + "".join("\t".join(map(str, row)) + "\n" for row in rows))
    print(f"{len(rows)} entries: {output}")


def archive(args):
    if not re.fullmatch(ITEM_ID, args.item) or ".." in args.item:
        raise ValueError("Invalid Internet Archive item ID.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]{1,79}", args.license):
        raise ValueError("Provide the license ID from the distribution record.")
    port = port_path(args.port)
    require_release(port)
    snapshot = port_sdk(port, getattr(args, "sdk", None))
    _, _, packer = sdk_paths(snapshot)
    slug, category, paths, mappings = config_for(port)
    item, source, entries, _, app_id, version = public_source(port, slug, category, paths, mappings)
    check_manifest_sdk(snapshot, read_json(source / "app.json"))
    require_release(port, version)
    kind = PORT_TYPES[port.parent.name][0]
    if args.full_package:
        if read_json(port / "port.json").get("archiveFullData") is not True:
            raise ValueError("A full package requires archiveFullData: true in port.json and a completed distribution record.")
        package = ROOT / RELEASE_ROOT / kind / slug / f"{app_id}-{version}-local.nxvapp"
    else:
        store_metadata(item, slug, require_screenshots=True)
        package = item / f"{slug}.nxvapp"
    found_id, name, found_version, size, digest = package_fields(package, packer)
    if (found_id, found_version) != (app_id, version):
        raise ValueError("Rebuild the package with the current manifest.")
    with ZipFile(package) as bundle:
        files = bundle.namelist()
        expected = {p.as_posix() for p in entries}
        payload = set(files) - {"manifest.sha256", "manifest.sig"}
        extra = payload - expected
        if len(files) != len(set(files)) or expected - payload or (extra and not args.full_package):
            raise ValueError("The archive candidate does not match the expected package file list.")
        if args.full_package:
            for filename in extra:
                rel = relative_path(filename)
                if not any(rel == target or target in rel.parents for _, target in mappings):
                    raise ValueError(f"File in the full package without a local data mapping: {filename}")
        for rel, file in entries.items():
            with bundle.open(rel.as_posix()) as inside, file.open("rb") as original:
                if sha256(inside) != sha256(original):
                    raise ValueError(f"Rebuild the Store package. File changed: {rel}")
    target = args.output.resolve()
    filename = f"{slug}-{version}.nxvapp"
    url = f"https://archive.org/download/{args.item}/{filename}"
    target.mkdir(parents=True, exist_ok=True)
    for output in (filename, "internet-archive.json", "port-market-entry.json", "DISTRIBUTION.md"):
        check_path(target / output, missing_ok=True)
        if (target / output).exists():
            raise ValueError(f"Archive output already exists: {target / output}")
    shutil.copyfile(package, target / filename)
    shutil.copyfile(port / "DISTRIBUTION.md", target / "DISTRIBUTION.md")
    metadata = {
        "identifier": args.item, "mediatype": "software", "title": f"{name} {version}",
        "description": f"Nexvyn OS port package, version {version}. Redistribution record included.",
        "subject": ["Nexvyn OS", "Nintendo Switch", "port"], "license": args.license,
    }
    row = {"kind": kind, "name": name, "version": version, "size": size,
           "sha256": digest, "url": url}
    for output, data in (("internet-archive.json", metadata), ("port-market-entry.json", row)):
        write_atomic(target / output, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Archive candidate ready locally: {target / filename}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    local = commands.add_parser("catalog")
    local.add_argument("--release-root", type=Path, default=ROOT / RELEASE_ROOT)
    local.add_argument("--archive", type=Path, action="append", default=[])
    export = commands.add_parser("prepare-archive")
    export.add_argument("port")
    export.add_argument("--item", required=True)
    export.add_argument("--license", required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--sdk", type=Path, help="SDK snapshot matching the port's lock.")
    export.add_argument("--full-package", action="store_true", help="Use the local full package that has a recorded distribution right.")
    args = parser.parse_args()
    try:
        (catalog if args.action == "catalog" else archive)(args)
    except (BadZipFile, OSError, ValueError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
