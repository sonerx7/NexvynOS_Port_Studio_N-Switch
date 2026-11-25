"""Store submission checks: payload names, metadata folder, and PNG screenshots."""

import struct
from pathlib import PurePosixPath
from zlib import crc32

from studio_files import check_path, list_files, read_json, under


PRIVATE_SUFFIXES = {
    ".exe", ".dll", ".msi", ".zip", ".rar", ".7z", ".tar", ".gz", ".xz",
    ".iso", ".rom", ".nsp", ".xci", ".nxvapp", ".pem", ".key", ".pfx", ".p12",
    ".csf", ".mix", ".mpq", ".wad", ".pak", ".vpk", ".bsp", ".bik", ".smk",
}
PRIVATE_DIRS = {"_localdata", "userdata", "private", "saves"}
FORBIDDEN_DIRS = {"__pycache__", "dist", "appmarket", "_realesedbuilds", "build"}
FORBIDDEN_NAMES = {"manifest.sha256", "manifest.sig", "id_rsa", "id_ed25519", "desktop.ini", "thumbs.db"}


def check_payload_name(path, *, public):
    names = {part.casefold() for part in path.parts}
    suffix = path.suffix.casefold()
    if names & (FORBIDDEN_DIRS | FORBIDDEN_NAMES) or suffix in {".pem", ".key", ".pfx", ".p12", ".nxvapp"}:
        raise ValueError(f"Cannot be used as a package entry: {path}")
    if public and (names & PRIVATE_DIRS or suffix in PRIVATE_SUFFIXES):
        raise ValueError(f"Cannot be added to the Store source: {path}")


def store_metadata(item, slug, *, require_screenshots=False):
    required = {"source", "README.md", "store.json"}
    optional = {"screenshots", "icon.png", f"{slug}.nxvapp"}
    screenshot_names = set()
    for entry in item.iterdir():
        check_path(entry)
        if entry.name not in required | optional:
            raise ValueError(f"Unexpected entry in the Store submission folder: {entry.name}")
        if entry.name == "screenshots":
            for screenshot in list_files(entry):
                if len(screenshot.parts) != 1 or screenshot.suffix != ".png":
                    raise ValueError(f"Store screenshot must be a PNG file: {screenshot}")
                check_screenshot(entry / screenshot)
                screenshot_names.add(screenshot.name)
        elif entry.name != "source" and not entry.is_file():
            raise ValueError(f"Store entry must be a file: {entry.name}")
    for name in ("README.md", "store.json"):
        path = under(item, PurePosixPath(name))
        content = path.read_text(encoding="utf-8-sig")
        if not content.strip() or "PORT_STUDIO_TEMPLATE" in content:
            raise ValueError(f"Store information must be completed: {name}")
    metadata = read_json(item / "store.json")
    if metadata.get("kind") != "port":
        raise ValueError('The Store record requires "kind": "port".')
    shots = metadata.get("shots")
    if require_screenshots and (
        not 3 <= len(screenshot_names) <= 5
        or screenshot_names != {f"{index}.png" for index in range(1, len(screenshot_names) + 1)}
    ):
        raise ValueError("A Store package requires 3-5 consecutive real screenshots starting with 1.png.")
    if len(screenshot_names) < 3 and (
        not isinstance(shots, list) or not 3 <= len(shots) <= 5 or any(not shot for shot in shots)
    ):
        raise ValueError("The Store requires at least three screenshots or 3-5 SDK capture scenarios.")


def check_screenshot(path):
    error = ValueError(f"Invalid store screenshot: {path.name}")
    with path.open("rb") as image:
        if image.read(8) != b"\x89PNG\r\n\x1a\n":
            raise error
        header = image.read(25)
        if len(header) != 25 or header[:8] != b"\x00\x00\x00\rIHDR":
            raise error
        width, height = struct.unpack_from(">II", header, 8)
        if not width or not height or crc32(header[4:-4]) != int.from_bytes(header[-4:], "big"):
            raise error
        has_data = False
        while chunk := image.read(8):
            if len(chunk) != 8:
                raise error
            length, kind = struct.unpack(">I4s", chunk)
            checksum = crc32(kind)
            remaining = length
            while remaining:
                block = image.read(min(remaining, 1024 * 1024))
                if not block:
                    raise error
                checksum = crc32(block, checksum)
                remaining -= len(block)
            expected = image.read(4)
            if len(expected) != 4 or checksum != int.from_bytes(expected, "big"):
                raise error
            if kind == b"IDAT" and length:
                has_data = True
            if kind == b"IEND":
                if length == 0 and has_data and image.read(1) == b"":
                    return
                break
    raise error
