"""Path and file helpers shared by the studio tools; no studio globals."""

import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON nesnesi bekleniyor.")
    return data


def relative_path(value):
    if not isinstance(value, str):
        raise ValueError("File path must be a string.")
    parts = value.split("/")
    for part in parts:
        if (
            not part or part.startswith(".") or part.endswith((" ", "."))
            or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
            or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL"}
            or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", part.split(".")[0].upper())
        ):
            raise ValueError(f"Not a safe relative package path: {value!r}")
    return PurePosixPath(value)


def check_path(path, *, missing_ok=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return
        raise
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"Links and junctions are not allowed: {path}")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ValueError(f"Expected a regular file or folder: {path}")


def under(base, rel, *, missing_ok=False):
    current = base
    for part in rel.parts:
        current /= part
        check_path(current, missing_ok=missing_ok)
    return current


def list_files(base, relative=None):
    directory = base if relative is None else base / relative
    for item in sorted(directory.iterdir()):
        rel = relative_path(item.name) if relative is None else relative / relative_path(item.name)
        check_path(item)
        if item.is_dir():
            yield from list_files(base, rel)
        else:
            yield rel


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
                raise ValueError(f"Case collision in package paths: {item}")
    for path in paths:
        if any(parent.as_posix().casefold() in files for parent in path.parents):
            raise ValueError(f"File/folder collision in package path: {path}")


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


def app_runtime(manifest):
    """The app's runtime as the SDK reads it: the `runtime` field, else the main file's extension."""
    if manifest.get("runtime"):
        return manifest["runtime"]
    main = str(manifest.get("main", ""))
    return {".lua": "lua", ".js": "javascript", ".mjs": "javascript", ".py": "python", ".nut": "squirrel",
            ".c": "c", ".jar": "java"}.get(Path(main).suffix.lower(), "native")
