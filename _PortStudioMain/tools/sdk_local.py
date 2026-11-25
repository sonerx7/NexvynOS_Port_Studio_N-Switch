"""Compare a local Nexvyn OS development checkout with the released SDK snapshot.

  python _PortStudioMain/tools/sync_nexvyn_sdk.py --from-local <os-checkout> [--json]
  python _PortStudioMain/tools/sync_nexvyn_sdk.py --from-local <os-checkout> --stage

Read-only by default: it prints, folder by folder, how the checkout's native kit differs from the released
snapshot (identical, comment-only, changed, new, missing) and which ABI functions are new.

--stage writes a preview candidate to _PortStudioMain/_SdkCandidates/preview-<commit>/ (git-ignored): the released
snapshot plus the changed public-kit files from the allow list below. Its STUDIO_SOURCE.json says
"status": "private-preview" and a non-official repository, so build, check and pack refuse it (sdk_problem). It is
for comparing headers and planning, never for a release. The checkout path is not written anywhere.
Never staged: prebuilt libraries, build output, tests, ports, canaries, documentation, tools.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

PRIVATE_KIT = PurePosixPath("sdk/native")
SNAPSHOT_KIT = PurePosixPath("Languages/c/native-kit/sdk/native")
FOLDERS = ("include", "lib", "loader", "sysroot", "compat", "templates", "toolchain")
SKIP_PARTS = {"build", "build_pic", "tests", "__pycache__", "ports", "canary"}
BINARY_SUFFIXES = {".a", ".o", ".so", ".nxvmod", ".nxvlib", ".debug", ".elf", ".nro", ".png", ".jpg", ".zip"}
# Only these may be staged into a preview candidate: public headers, templates, build recipes, compat sources.
STAGE_ALLOW = (
    re.compile(r"^include/nexvyn/[^/]+\.h$"),
    re.compile(r"^templates/"),
    re.compile(r"^toolchain/[^/]+\.(cmake|txt|json|ini)$"),
    re.compile(r"^sysroot/(recipes\.json|patches/|shims/)"),
    re.compile(r"^compat/(src|include|cmake|win)/|^compat/wrap_[a-z]+\.txt$"),
    re.compile(r"^loader/[^/]+\.[ch]$"),
)
COMMENT_LINE = re.compile(r"^\s*(//|/\*|\*|\*/|#)")


def git(checkout, *args):
    return subprocess.check_output(["git", "-C", str(checkout), *args], encoding="utf-8", errors="replace").strip()


def tracked_kit_files(checkout):
    names = git(checkout, "ls-files", "-z", "--", str(PRIVATE_KIT)).split("\0")
    files = {}
    for name in filter(None, names):
        rel = PurePosixPath(name).relative_to(PRIVATE_KIT)
        if rel.parts[0] not in FOLDERS or SKIP_PARTS & set(rel.parts) or rel.suffix in BINARY_SUFFIXES:
            continue
        files[str(rel)] = checkout / name
    return files


def snapshot_kit_files(snapshot):
    root = snapshot / SNAPSHOT_KIT
    files = {}
    for path in root.rglob("*") if root.is_dir() else []:
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if path.is_file() and rel.parts[0] in FOLDERS and not SKIP_PARTS & set(rel.parts) and rel.suffix not in BINARY_SUFFIXES:
            files[str(rel)] = path
    return files


def normalise(text):
    return text.replace("\r\n", "\n")


def comment_only(a, b):
    """True when the only differing lines are comments."""
    left = [line for line in normalise(a).split("\n") if not COMMENT_LINE.match(line)]
    right = [line for line in normalise(b).split("\n") if not COMMENT_LINE.match(line)]
    return left == right


def abi_functions(path):
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("functions", [])
    return {item["name"] if isinstance(item, dict) else item for item in items}


def compare(checkout, snapshot):
    checkout, snapshot = Path(checkout).resolve(strict=True), Path(snapshot)
    commit = git(checkout, "rev-parse", "--verify", "HEAD")
    dirty = git(checkout, "status", "--porcelain", "--", str(PRIVATE_KIT))
    private, released = tracked_kit_files(checkout), snapshot_kit_files(snapshot)
    folders = {folder: {"identical": [], "comment": [], "changed": [], "new": [], "missing": []} for folder in FOLDERS}
    for rel in sorted(set(private) | set(released)):
        bucket = folders[PurePosixPath(rel).parts[0]]
        if rel not in released:
            bucket["new"].append(rel)
        elif rel not in private:
            bucket["missing"].append(rel)
        else:
            a = released[rel].read_text(encoding="utf-8", errors="replace")
            b = private[rel].read_text(encoding="utf-8", errors="replace")
            if normalise(a) == normalise(b):
                bucket["identical"].append(rel)
            elif comment_only(a, b):
                bucket["comment"].append(rel)
            else:
                bucket["changed"].append(rel)
    abi_rel = "toolchain/nxn_abi_v1.json"
    new_abi = sorted(abi_functions(private.get(abi_rel, Path("-"))) - abi_functions(released.get(abi_rel, Path("-"))))
    removed_abi = sorted(abi_functions(released.get(abi_rel, Path("-"))) - abi_functions(private.get(abi_rel, Path("-"))))
    stageable = [rel for folder in folders.values() for rel in folder["changed"] + folder["new"] + folder["comment"]
                 if any(rule.search(rel) for rule in STAGE_ALLOW)]
    return {"commit": commit, "kitDirty": bool(dirty), "folders": folders, "newAbiFunctions": new_abi,
            "removedAbiFunctions": removed_abi, "stageable": sorted(stageable), "privateFiles": private}


def render(result):
    lines = [f"Local checkout commit {result['commit'][:12]} against the released snapshot (private-preview differences):", "",
             f"{'folder':10} {'same':>5} {'comment':>8} {'changed':>8} {'new':>5} {'missing':>8}"]
    for folder, b in result["folders"].items():
        lines.append(f"{folder:10} {len(b['identical']):5} {len(b['comment']):8} {len(b['changed']):8} {len(b['new']):5} {len(b['missing']):8}")
    for folder, b in result["folders"].items():
        for kind in ("changed", "new", "missing"):
            for rel in b[kind]:
                lines.append(f"  {kind:8} {rel}")
    lines.append("")
    lines.append("New ABI functions (private-preview): " + (", ".join(result["newAbiFunctions"]) or "none"))
    if result["removedAbiFunctions"]:
        lines.append("ABI functions missing from the checkout (ABI v1 is add-only; this is an error): " + ", ".join(result["removedAbiFunctions"]))
    if result["kitDirty"]:
        lines.append("The checkout's sdk/native has uncommitted changes: they are not compared (tracked HEAD files only).")
    lines.append(f"Stageable public-kit files: {len(result['stageable'])}.")
    return "\n".join(lines)


def stage(result, snapshot, candidates):
    if result["removedAbiFunctions"]:
        raise ValueError("The checkout removes ABI v1 functions; refusing to stage.")
    target = candidates / f"preview-{result['commit'][:12]}"
    if target.exists():
        raise ValueError(f"Preview candidate already exists; inspect or delete it first: {target}")
    candidates.mkdir(parents=True, exist_ok=True)
    shutil.copytree(snapshot, target)
    kit = target / SNAPSHOT_KIT
    for rel in result["stageable"]:
        destination = kit / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result["privateFiles"][rel], destination)
    provenance = {"repository": "local-development-checkout", "commit": result["commit"], "status": "private-preview",
                  "note": "Comparison and planning only. Build, check and pack refuse this snapshot."}
    (target / "STUDIO_SOURCE.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    (target / "PREVIEW_FILES.json").write_text(json.dumps(result["stageable"], indent=2) + "\n", encoding="utf-8")
    return target
