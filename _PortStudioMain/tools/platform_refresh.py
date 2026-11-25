"""Refresh platform/capabilities.json from the released SDK snapshot (and, optionally, a local development checkout).

  python _PortStudioMain/tools/platform_refresh.py                       # show what would change
  python _PortStudioMain/tools/platform_refresh.py --from-local <os>     # also mark what the checkout adds as preview
  python _PortStudioMain/tools/platform_refresh.py --write [--from-local <os>]

Derived, not typed by hand:
  source + versions          from the snapshot's VERSION.json
  templates (status)         snapshot native-kit templates = released; checkout-only = private-preview
  tools.nxv_native           subcommands of the snapshot's nxv_native = released; checkout-only = preview
  libraries.versions/status  snapshot sysroot recipes = released; checkout-only recipes = preview
  newApis[].status           declared in snapshot headers = released; else private-preview
  capabilityBits             NXN_CAP_* names declared in the snapshot / checkout
  deviceValidation.counters  execution and device counters from the checkout's progress logs (numbers only)
  ownerReleased              applied last: the owner's released items (Vulkan) stay released
Hand-written facts (notes, performance tiers, rules) are kept. Every generated entry carries status and asOf.
Nothing from the checkout is written except names, version numbers and counters; never paths or source text.
"""

import argparse
import copy
import json
import re
import sys
from datetime import date
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
CAPABILITIES = STUDIO / "platform" / "capabilities.json"
SNAPSHOT = STUDIO / "nexvyn_sdk"
KIT = Path("Languages/c/native-kit")
LOCAL_KIT = Path("sdk/native")
LOCAL_TOOLS = Path("tools")


def read(path):
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def subcommands(main_py):
    return sorted(set(re.findall(r'add_parser\(\s*"([a-z][a-z0-9-]*)"', read(main_py))))


def recipes(path):
    if not path.is_file():
        return {}
    data = json.loads(read(path))
    out = {name: (item.get("version") if isinstance(item, dict) else str(item)) for name, item in data.get("recipes", {}).items()}
    for name in (data.get("vendored") or {}):
        out.setdefault(name, "vendored")
    return out


def cap_bits(include):
    text = "\n".join(read(p) for p in include.glob("*.h")) if include.is_dir() else ""
    return sorted(set(re.findall(r"#define (NXN_CAP_[A-Z0-9_]+)\s", text)))


def progress_log(checkout, plan):
    """Where a development checkout keeps a plan's progress log (the only checkout layout this tool reads)."""
    return checkout / "docs" / "current" / plan / f"{plan.upper()}_PROGRESS_LOG.md"


def counters(checkout):
    """Execution / device counters of the N3, N4, N5 plans: numbers only."""
    result = {}
    for plan in ("n3", "n4", "n5"):
        log = read(progress_log(checkout, plan))
        # The dashboard table at the top is current; later log lines are history, so only table rows are read.
        execution = re.search(r"^\|\s*\**Execution[^|]*\|\s*\**(\d+/\d+)", log, re.M)
        device = re.search(r"^\|\s*\**Device-verified\**\s*\|\s*\**([^|\n*]+)", log, re.M)
        if not execution:
            start, end = log.find("DASHBOARD_BEGIN"), log.find("DASHBOARD_END")
            block = log[start:end] if start >= 0 else ""
            cells = re.findall(r"^\|\s*[A-Z]\d+\s*\|.*?\|\s*(\d+)/(\d+)\s*\|", block, re.M)
            if cells:
                done, total = sum(int(a) for a, _ in cells), sum(int(b) for _, b in cells)
                execution = re.match(r"(.*)", f"{done}/{total}")
        if execution or device:
            text = device.group(1).strip() if device else ""
            if text and not re.fullmatch(r"\d+/\d+", text):
                # Named task lists are internal identifiers: publish only how many passed on the device.
                named = len(re.findall(r"\b[A-Z]+\.\d+\b", text))
                text = f"{named} task(s) passed on device" if named else "see the OS release notes"
            result[plan.upper()] = {"execution": execution.group(1) if execution else None,
                                    "device": text or "not recorded in the dashboard"}
    return result


def refresh(caps, snapshot=SNAPSHOT, checkout=None, today=None):
    caps = copy.deepcopy(caps)
    today = today or date.today().isoformat()
    versions = json.loads(read(snapshot / "VERSION.json") or "{}")
    kit = snapshot / KIT / "sdk" / "native"
    caps["asOf"] = today
    caps["source"] = (f"Nexvyn OS public SDK {versions.get('sdk')} / Native SDK {versions.get('native')} / "
                      f"ABI v{versions.get('nativeAbi')} (OS {versions.get('os')})"
                      + (", plus announced preview features" if checkout else ""))
    released_templates = {p.name for p in (kit / "templates").iterdir() if p.is_dir()} if (kit / "templates").is_dir() else set()
    local_templates = set()
    if checkout and (checkout / LOCAL_KIT / "templates").is_dir():
        local_templates = {p.name for p in (checkout / LOCAL_KIT / "templates").iterdir() if p.is_dir()}
    templates = caps.setdefault("templates", {})
    for name in sorted(released_templates | local_templates):
        entry = templates.setdefault(name, {"fits": [], "use": "describe this template"})
        entry["status"] = "released" if name in released_templates else "private-preview"
    for name, entry in templates.items():
        if name not in released_templates | local_templates:
            entry["status"] = "planned" if entry.get("status") != "released" else entry["status"]
    released_cmds = subcommands(snapshot / KIT / "tools" / "nxv_native" / "__main__.py")
    preview_cmds = []
    if checkout:
        preview_cmds = [c for c in subcommands(checkout / LOCAL_TOOLS / "nxv_native" / "__main__.py") if c not in released_cmds]
    caps.setdefault("tools", {})["nxv_native"] = {"released": released_cmds, "preview": preview_cmds}
    released_libs = recipes(kit / "sysroot" / "recipes.json")
    local_libs = recipes(checkout / LOCAL_KIT / "sysroot" / "recipes.json") if checkout else {}
    libraries = caps.setdefault("libraries", {})
    libraries["kitRecipes"] = {name: {"version": v, "status": "released"} for name, v in released_libs.items()}
    for name, version in local_libs.items():
        if name not in released_libs:
            libraries["kitRecipes"][name] = {"version": version, "status": "private-preview"}
    headers = "\n".join(read(p) for p in (kit / "include" / "nexvyn").glob("*.h"))
    for api in caps.get("newApis", []):
        declared = re.search(rf"\b{re.escape(api['symbol'])}\b", headers) is not None
        api["status"] = "released" if declared else "private-preview"
    bits = {"released": cap_bits(kit / "include" / "nexvyn")}
    if checkout:
        bits["preview"] = [b for b in cap_bits(checkout / LOCAL_KIT / "include" / "nexvyn") if b not in bits["released"]]
    caps["capabilityBits"] = bits
    if checkout:
        validation = caps.setdefault("deviceValidation", {})
        validation["counters"] = counters(checkout)
        validation["countersAsOf"] = today
    return apply_owner_released(caps)


def apply_owner_released(caps):
    """Items the owner declared released (ownerReleased) stay released whatever the snapshot headers say."""
    owner = caps.get("ownerReleased") or {}
    for group in ("graphics", "templates", "osSettings"):
        for name in owner.get(group, []):
            if name in caps.get(group, {}):
                caps[group][name]["status"] = "released"
    recipes_ = caps.get("libraries", {}).get("kitRecipes", {})
    for name in owner.get("kitRecipes", []):
        if name in recipes_:
            recipes_[name]["status"] = "released"
    libraries = caps.get("libraries", {})
    for name in owner.get("libraries", []):
        if name in libraries.get("preview", []):
            libraries["preview"].remove(name)
        if "released" in libraries and name not in libraries["released"]:
            libraries["released"].append(name)
    for api in caps.get("newApis", []):
        if api.get("symbol") in owner.get("newApis", []):
            api["status"] = "released"
    bits = caps.get("capabilityBits", {})
    for name in owner.get("capabilityBits", []):
        if name in bits.get("preview", []):
            bits["preview"].remove(name)
        if "released" in bits and name not in bits["released"]:
            bits["released"].append(name)
    return caps


def diff(old, new, prefix=""):
    lines = []
    keys = sorted(set(old) | set(new)) if isinstance(old, dict) and isinstance(new, dict) else None
    if keys is None:
        if old != new:
            lines.append(f"~ {prefix}: {json.dumps(old, ensure_ascii=False)[:120]} -> {json.dumps(new, ensure_ascii=False)[:120]}")
        return lines
    for key in keys:
        path = f"{prefix}.{key}" if prefix else key
        if key not in old:
            lines.append(f"+ {path}: {json.dumps(new[key], ensure_ascii=False)[:120]}")
        elif key not in new:
            lines.append(f"- {path}")
        else:
            lines += diff(old[key], new[key], path)
    return lines


def validate(caps):
    """Every status-bearing entry needs a known status. Returns a list of problems."""
    allowed = set(caps.get("statusLevels", {}))
    problems = []
    groups = {"platform": caps.get("platform", {}), "templates": caps.get("templates", {}), "runtimes": caps.get("runtimes", {}),
              "osSettings": caps.get("osSettings", {}), "kitRecipes": caps.get("libraries", {}).get("kitRecipes", {}),
              "scriptApis": caps.get("scriptApis", {}), "graphics": caps.get("graphics", {})}
    for group, entries in groups.items():
        for name, entry in entries.items():
            if not isinstance(entry, dict) or (group == "graphics" and "status" not in entry and "value" not in entry):
                continue
            if entry.get("status") not in allowed:
                problems.append(f"{group}.{name}: status {entry.get('status')!r}")
    for api in caps.get("newApis", []):
        if api.get("status") not in allowed or not api.get("evidence"):
            problems.append(f"newApis.{api.get('symbol')}: status/evidence missing")
    for key in ("asOf", "source"):
        if not caps.get(key):
            problems.append(f"{key} missing")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-local", type=Path, metavar="OS_CHECKOUT")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    old = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    new = refresh(old, checkout=args.from_local.resolve() if args.from_local else None)
    problems = validate(new)
    changes = diff(old, new)
    print("\n".join(changes) if changes else "No changes.")
    if problems:
        print("Problems (fix before writing):\n  " + "\n  ".join(problems))
        return 1
    if args.write and changes:
        CAPABILITIES.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Written: {CAPABILITIES}")
    elif changes:
        print("Nothing written. Add --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
