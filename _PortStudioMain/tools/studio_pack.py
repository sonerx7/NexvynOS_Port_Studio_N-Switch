"""Package payload helpers: local data entries and package size limits."""

import os
import sys
from pathlib import Path

from studio_files import check_path, list_files, under, unique_paths
from studio_store import check_payload_name


def local_entries(root, mappings, public_paths):
    if bool(mappings) != bool(root):
        raise ValueError("--data-root is required when localData mappings exist. If no data is needed, leave both empty.")
    if not mappings:
        return {}
    base = Path(os.path.abspath(root))
    if not base.is_dir():
        raise ValueError(f"Local data folder not found: {base}")
    for ancestor in (*reversed(base.parents), base):
        check_path(ancestor)
    entries = {}
    destinations = list(public_paths)
    for origin, dest in mappings:
        source = under(base, origin)
        children = list(list_files(source)) if source.is_dir() else [None]
        if not children:
            raise ValueError(f"Local data folder is empty: {origin}")
        for child in children:
            target = dest if child is None else dest / child
            check_payload_name(origin if child is None else origin / child, public=False)
            check_payload_name(target, public=False)
            destinations.append(target)
            entries[target] = source if child is None else source / child
        count = 1 if child is None else len(children)
        size = sum(f.stat().st_size for f in ([source] if child is None else (source / c for c in children)))
        print(f"  local data: {origin} -> {dest}: {count:,} file(s), {size / (1 << 20):,.1f} MiB", file=sys.stderr)
    unique_paths(destinations)
    return entries


def check_package_limits(files, label):
    if len(files) > 20_000 or sum(entry.file_size for entry in files) > 1 << 30:
        raise ValueError(f"{label}: exceeds the Nexvyn OS limits of 20,000 files or 1 GiB unpacked.")
    size = sum(entry.file_size for entry in files)
    count = len(files)
    if count > 1000:
        print(f"WARNING: {label} has {count:,} files. Installing it may take very long and the Nexvyn OS install "
              "sheet can freeze on \"Checking the package\" (older OS builds rescan the zip for every file; a 5,944-file "
              "package sat there for minutes, a 37-file one did not). Merge or drop files, or let the player pick "
              "the data folder instead of bundling it. Test the install on the OS build you ship to.", file=sys.stderr)
    elif count > 500:
        print(f"Note: {label} has {count:,} files. Install checks slow down as the count grows; above 1,000 files the "
              "install sheet can appear frozen. Prefer fewer, larger files.", file=sys.stderr)
    if size > 0.9 * (1 << 30):
        print(f"Note: {label} unpacks to {size / (1 << 20):,.0f} MiB, close to the 1 GiB limit. Drop optional data first.",
              file=sys.stderr)


# Preview-only SDK files must not reach a package until the OS release that ships them is public (OS 1.4.0 / SDK 1.16).
# Always-preview headers are named here; preview candidates add their own new headers and file digests.
PREVIEW_HEADERS = {"nxn_vk.h", "nxn_imgui_vk.h"}
PREVIEW_KIT = Path("Languages/c/native-kit/sdk/native")


def _sha256(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preview_fingerprints(released_sdk, candidates_dir):
    """(header names, SHA-256 set) of preview-candidate kit files the released snapshot lacks or holds with other content."""
    import json
    # A header counts as preview only while the active SDK does not ship it (SDK 1.16 ships nxn_vk.h).
    shipped = Path(released_sdk) / PREVIEW_KIT / "include" / "nexvyn"
    names, digests = {h for h in PREVIEW_HEADERS if not (shipped / h).is_file()}, set()
    for candidate in sorted(Path(candidates_dir).glob("preview-*")) if Path(candidates_dir).is_dir() else []:
        listed = candidate / "PREVIEW_FILES.json"
        if not listed.is_file():
            continue
        for rel in json.loads(listed.read_text(encoding="utf-8")):
            path, released = candidate / PREVIEW_KIT / rel, Path(released_sdk) / PREVIEW_KIT / rel
            if not path.is_file():
                continue
            if released.is_file() and released.read_bytes() == path.read_bytes():
                continue
            digests.add(_sha256(path))
            if not released.is_file() and path.suffix == ".h":
                names.add(path.name)
    return names, digests


def check_no_preview_payload(stage, released_sdk, candidates_dir):
    """Refuse a package payload that carries preview-only SDK files (by header name or exact content)."""
    names, digests = preview_fingerprints(released_sdk, candidates_dir)
    leaks = []
    for path in sorted(Path(stage).rglob("*")):
        if not path.is_file():
            continue
        if path.name in names or (path.suffix != ".nxvmod" and _sha256(path) in digests):
            leaks.append(path.relative_to(stage).as_posix())
    if leaks:
        raise ValueError("Preview-only SDK files must not be packaged before their OS release is public: " + ", ".join(leaks))
