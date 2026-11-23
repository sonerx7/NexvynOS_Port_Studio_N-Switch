"""Port experience layer: input modes, gestures, performance profiles, compatibility.

One source of truth: the `experience` block in a port's port.json, layered on a genre
preset from _PortStudioMain/profiles/. This module resolves, validates, migrates and
generates files from it. It never edits engine code.

  python _PortStudioMain/tools/experience.py init  GamePorts/<port> rts
  python _PortStudioMain/tools/experience.py check GamePorts/<port>
  python _PortStudioMain/tools/experience.py generate GamePorts/<port>   # generated/experience.json + nx_experience.h
  python _PortStudioMain/tools/experience.py migrate GamePorts/<port>    # upgrade the block to the current schema
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
PROFILES = STUDIO / "profiles"

# Bump CURRENT when the block layout changes; add MIGRATIONS[old] to upgrade old ports.
# Old schemas stay readable for as long as they appear in MIGRATIONS.
CURRENT_SCHEMA = 1
MIGRATIONS = {}  # {from_schema: function(block) -> block for from_schema + 1}

MODES = ("auto", "gamepad", "touch", "kbm")
DEVICE_MODES = ("gamepad", "touch", "kbm")
GESTURES = (
    "tap", "double_tap", "long_press", "one_finger_drag", "two_finger_tap",
    "two_finger_pan", "pinch", "rotate", "edge_swipe",
)
# Owned by Nexvyn OS. A port must not bind these (see INPUT_AND_PLAY_MODES.md).
RESERVED = {"home", "l+r_hold", "minus_hold", "edge_swipe_top", "edge_swipe"}
# How a pinch becomes a zoom, best first. native: the game has its own zoom and the port
# wires the pinch into it. wheel / keys: the port sends the mouse wheel or the zoom keys
# the game already understands. present: the port magnifies the finished picture (the game
# has no zoom of its own). Pick the first one the game really supports and record how you know.
ZOOM_METHODS = ("native", "wheel", "keys", "present", "none")
ZOOM_ORDER = ["native", "wheel", "keys", "present"]
NEEDS_EVIDENCE = ("native", "wheel", "keys")
PERF_KEYS = {"renderScale": (0.25, 2.0), "fpsCap": (15, 120), "msaa": (0, 8)}
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_profile(name):
    path = PROFILES / f"{name}.json"
    if not re.fullmatch(r"[a-z0-9-]+", name) or not path.is_file():
        available = ", ".join(sorted(p.stem for p in PROFILES.glob("*.json")))
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return load_json(path)


def merge(base, over):
    """Deep merge; dict values merge, everything else replaces."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def migrate_block(block):
    schema = block.get("schema")
    if not isinstance(schema, int) or schema < 1:
        raise ValueError("experience.schema must be a positive integer.")
    if schema > CURRENT_SCHEMA:
        raise ValueError(
            f"experience.schema {schema} is newer than this Studio supports ({CURRENT_SCHEMA}). Update the Studio.")
    while schema < CURRENT_SCHEMA:
        if schema not in MIGRATIONS:
            raise ValueError(f"No migration from experience.schema {schema}.")
        block = MIGRATIONS[schema](block)
        schema += 1
        block["schema"] = schema
    return block


def resolve(port_config):
    """Preset + the port's overrides. Raises ValueError for a missing or unreadable block."""
    block = port_config.get("experience")
    if not isinstance(block, dict):
        raise ValueError("port.json has no experience block. Run: experience.py init <port> <profile>")
    block = migrate_block(copy.deepcopy(block))
    preset = load_profile(block.get("profile", ""))
    preset = migrate_block(preset)
    merged = merge(preset, {k: v for k, v in block.items() if k not in ("profile", "schema")})
    merged["profile"] = block["profile"]
    merged["schema"] = CURRENT_SCHEMA
    # The engine decides what a port can do. A port lists actions it cannot support
    # (for example camera_zoom in an engine without zoom); they are removed, and
    # every gesture that pointed at them is removed too. A gesture set to null is dropped.
    inp = merged["input"]
    unsupported = set(inp.get("unsupported", []))
    for name in unsupported:
        inp["actions"].pop(name, None)
    inp["gestures"] = {g: a for g, a in inp.get("gestures", {}).items()
                       if a is not None and a not in unsupported}
    zoom = inp.setdefault("zoom", {"method": "none"})
    zoom.setdefault("order", list(ZOOM_ORDER))
    if zoom.get("method", "none") != "none" and "touch" in inp.get("modes", []) and "camera_zoom" in inp["actions"]:
        inp["gestures"].setdefault("pinch", "camera_zoom")
    return merged


def validate(resolved):
    errors = []
    inp, perf = resolved.get("input", {}), resolved.get("performance", {})
    modes = inp.get("modes", [])
    if not modes or any(m not in MODES for m in modes):
        errors.append(f"input.modes must be a non-empty subset of {MODES}.")
    if inp.get("defaultMode") not in modes:
        errors.append("input.defaultMode must be one of input.modes.")
    if "auto" in modes and not any(m in modes for m in DEVICE_MODES):
        errors.append("input.modes has 'auto' but no concrete device mode.")
    actions = inp.get("actions", {})
    for needed in ("select", "cancel", "menu"):
        if needed not in actions:
            errors.append(f"input.actions.{needed} is required: every port needs a way to confirm, go back and open the menu.")
    for name, binds in actions.items():
        if not NAME.match(name):
            errors.append(f"action '{name}': use lowercase letters, digits and underscores.")
        for mode in DEVICE_MODES:
            if mode in modes and not binds.get(mode):
                errors.append(f"action '{name}': no binding for declared mode '{mode}'.")
        for mode, keys in binds.items():
            for key in keys if isinstance(keys, list) else []:
                if key.lower() in RESERVED:
                    errors.append(f"action '{name}': '{key}' is reserved for Nexvyn OS.")
    for gesture, action in inp.get("gestures", {}).items():
        if gesture not in GESTURES:
            errors.append(f"gesture '{gesture}' unknown. Known: {', '.join(GESTURES)}")
        elif gesture in RESERVED:
            errors.append(f"gesture '{gesture}' is reserved for Nexvyn OS.")
        if action not in actions:
            errors.append(f"gesture '{gesture}' maps to undefined action '{action}'.")
    zoom = inp.get("zoom", {})
    method = zoom.get("method", "none")
    if method not in ZOOM_METHODS:
        errors.append(f"input.zoom.method must be one of {ZOOM_METHODS}.")
    elif method != "none":
        if "camera_zoom" not in actions:
            errors.append("input.zoom.method is set but the action 'camera_zoom' does not exist.")
        if method in NEEDS_EVIDENCE and not str(zoom.get("evidence", "")).strip():
            errors.append(f"input.zoom.evidence is required for method '{method}': say how you know the game reacts to it.")
        if method == "keys" and not zoom.get("keys"):
            errors.append("input.zoom.keys is required for method 'keys' (for example [\"+\", \"-\"]).")
        low, high = zoom.get("min", 1.0), zoom.get("max", 2.0)
        if not 0 < low <= 1.0 <= high:
            errors.append("input.zoom needs 0 < min <= 1 <= max.")
    elif inp.get("gestures", {}).get("pinch") == "camera_zoom":
        errors.append("pinch maps to camera_zoom but input.zoom.method is 'none'.")
    for scenario in resolved.get("scenarios", []):
        if not scenario.get("id") or not scenario.get("steps"):
            errors.append("each scenario needs an id and steps.")
        for mode in scenario.get("steps", {}):
            if mode not in DEVICE_MODES:
                errors.append(f"scenario '{scenario.get('id')}': unknown mode '{mode}'.")
            elif mode not in modes:
                errors.append(f"scenario '{scenario.get('id')}': mode '{mode}' is not declared in input.modes.")
    if "touch" in modes and inp.get("touch", {}).get("minTargetPx", 0) < 44:
        errors.append("input.touch.minTargetPx must be at least 44.")
    pad = inp.get("gamepad", {})
    if not 0 <= pad.get("deadzone", 0) < 1:
        errors.append("input.gamepad.deadzone must be in [0, 1).")
    for profile_name in ("handheld", "docked"):
        profile = perf.get(profile_name)
        if not isinstance(profile, dict):
            errors.append(f"performance.{profile_name} is required.")
            continue
        for key, (low, high) in PERF_KEYS.items():
            if key in profile and not low <= profile[key] <= high:
                errors.append(f"performance.{profile_name}.{key} must be in [{low}, {high}].")
    launcher = resolved.get("launcher", {})
    if not launcher.get("primaryAction"):
        errors.append("launcher.primaryAction is required (play, resume, new, open_recent).")
    return errors


def howto_strings(resolved, locale):
    """Flat lang keys for the launcher's How to play tab, in one locale."""
    path = PROFILES / "i18n" / f"{locale}.json"
    words = load_json(path) if path.is_file() else {}
    en = load_json(PROFILES / "i18n" / "en.json")

    def word(key):
        return words.get(key) or en.get(key) or key.split(".", 1)[-1]

    inp = resolved["input"]
    out = {"howto.title": word("howto.title"), "howto.intro": word("howto.intro")}
    for mode in DEVICE_MODES:
        out[f"howto.scheme.{mode}"] = word(f"howto.scheme.{mode}")
    for name, binds in inp["actions"].items():
        label = word("act." + name) if ("act." + name) in en else name
        for mode in DEVICE_MODES:
            if mode in binds:
                out[f"howto.row.{name}.{mode}"] = label + ": " + ", ".join(word("bind." + b) for b in binds[mode])
    method = inp.get("zoom", {}).get("method", "none")
    out["howto.zoom"] = word("howto.zoom." + ("keys" if method == "keys" else "present" if method == "present"
                                              else "none" if method == "none" else "wheel"))
    return out


def scenarios_markdown(resolved):
    lines = [f"# Acceptance scenarios: {resolved['profile']}", "",
             "Run each in every declared input mode, in handheld (720p, touch) and in docked (1080p, no touch screen). Record pass/fail, the console mode, and where it ran (host, emulator, physical Switch).", ""]
    for scenario in resolved.get("scenarios", []):
        lines += [f"## {scenario['title']} (`{scenario['id']}`)", ""]
        for mode in DEVICE_MODES:
            if mode in scenario["steps"] and mode in resolved["input"]["modes"]:
                lines.append(f"- [ ] {mode}: {scenario['steps'][mode]}")
        lines.append("")
    return "\n".join(lines)


def generate(port, resolved, merge_lang=None):
    out = port / "generated"
    out.mkdir(exist_ok=True)
    (out / "scenarios.md").write_text(scenarios_markdown(resolved), encoding="utf-8")
    (out / "howto").mkdir(exist_ok=True)
    for locale_file in sorted((PROFILES / "i18n").glob("*.json")):
        strings = howto_strings(resolved, locale_file.stem)
        (out / "howto" / f"{locale_file.stem}.json").write_text(
            json.dumps(strings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if merge_lang:
            target = port / merge_lang / f"{locale_file.stem}.json"
            if target.is_file():
                existing = json.loads(target.read_text(encoding="utf-8-sig"))
                existing = {k: v for k, v in existing.items() if not k.startswith("howto.")}
                existing.update(strings)
                target.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "experience.json").write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")
    actions = sorted(resolved["input"]["actions"])
    lines = [
        "/* Generated by Nexvyn Port Studio (experience.py). Do not edit; change port.json instead. */",
        "#ifndef NX_EXPERIENCE_H", "#define NX_EXPERIENCE_H", "",
        f"#define NX_EXPERIENCE_SCHEMA {resolved['schema']}",
        "typedef enum {",
    ]
    lines += [f"    NX_ACT_{a.upper()}," for a in actions] + ["    NX_ACT_COUNT", "} nx_action;", ""]
    lines += ["typedef enum { NX_GEST_NONE = 0,"]
    lines += [f"    NX_GEST_{g.upper()}," for g in GESTURES] + ["    NX_GEST_COUNT", "} nx_gesture;", ""]
    gmap = resolved["input"].get("gestures", {})
    lines.append("/* Gesture -> action; -1 when the port leaves the gesture unbound. */")
    lines.append("static const int nx_gesture_action[NX_GEST_COUNT] = {")
    lines.append("    -1,")
    lines += [f"    {'NX_ACT_' + gmap[g].upper() if g in gmap else '-1'}," for g in GESTURES]
    lines += ["};", "",
              "typedef struct { float render_scale; int width, height, fps_cap, msaa; } nx_perf_profile;"]
    for name in ("handheld", "docked"):
        p = resolved["performance"][name]
        w, h = p.get("resolution", [1280, 720])
        lines.append(f"static const nx_perf_profile nx_perf_{name} = "
                     f"{{ {float(p.get('renderScale', 1.0))}f, {w}, {h}, {p.get('fpsCap', 30)}, {p.get('msaa', 0)} }};")
    zoom = resolved["input"].get("zoom", {})
    lines += ["", f'#define NX_ZOOM_METHOD "{zoom.get("method", "none")}"',
              f"#define NX_ZOOM_MIN {float(zoom.get('min', 1.0))}f",
              f"#define NX_ZOOM_MAX {float(zoom.get('max', 1.0))}f",
              f"#define NX_ZOOM_STEP {float(zoom.get('step', 0.25))}f",
              f"#define NX_ZOOM_DEFAULT_ON {1 if zoom.get('defaultOn') else 0}",
              "", "/* How to play tab: lang keys per action and device (see generated/howto/<locale>.json). */",
              "typedef struct { const char *action; const char *key[3]; } nx_howto_row; /* gamepad, touch, kbm */",
              "static const nx_howto_row nx_howto_rows[] = {"]
    for name in resolved["input"]["actions"]:   # the preset's order reads better than A to Z
        keys = [f'"howto.row.{name}.{m}"' if m in resolved["input"]["actions"][name] else "0" for m in DEVICE_MODES]
        lines.append(f'    {{ "{name}", {{ {", ".join(keys)} }} }},')
    lines += ["};", f"#define NX_HOWTO_ROW_COUNT {len(actions)}", '#define NX_HOWTO_ZOOM_KEY "howto.zoom"', '#define NX_HOWTO_TITLE_KEY "howto.title"', '#define NX_HOWTO_INTRO_KEY "howto.intro"', "", "#endif", ""]
    (out / "nx_experience.h").write_text("\n".join(lines), encoding="utf-8")
    return out


def port_config(port):
    return load_json(port / "port.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("init", "check", "generate", "migrate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("port", type=Path)
        if name == "init":
            cmd.add_argument("profile")
        if name == "generate":
            cmd.add_argument("--merge-lang", help="Merge the howto.* keys into <port>/<dir>/<locale>.json.")
    args = parser.parse_args(argv)
    port = args.port
    try:
        config = port_config(port)
        if args.action == "init":
            load_profile(args.profile)
            if "experience" in config:
                raise ValueError("port.json already has an experience block.")
            config["experience"] = {"schema": CURRENT_SCHEMA, "profile": args.profile}
            (port / "port.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"Added experience block (profile '{args.profile}'). Override only what differs from the preset.")
            return 0
        if args.action == "migrate":
            block = migrate_block(copy.deepcopy(config.get("experience") or {}))
            config["experience"] = block
            (port / "port.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"experience block is at schema {block['schema']}.")
            return 0
        resolved = resolve(config)
        errors = validate(resolved)
        if errors:
            print("\n".join(f"- {e}" for e in errors), file=sys.stderr)
            return 1
        if args.action == "generate":
            print(f"Generated {generate(port, resolved, args.merge_lang)}")
        else:
            print(f"experience OK: profile '{resolved['profile']}', schema {resolved['schema']}, modes {resolved['input']['modes']}")
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
