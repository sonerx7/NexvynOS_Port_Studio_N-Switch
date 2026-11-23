"""Heuristic game/app analysis: suggests an experience profile and flags input needs.

  python _PortStudioMain/tools/analyze.py <game-or-source-dir> [--json]

Reads file names, executable import strings and source files. It never runs the program.
Everything it prints is a hint with its evidence; the porter confirms it. It cannot
tell a genre from code alone, so the genre guess is the weakest line in the report.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# (evidence regex over bytes, signal). A signal names what the program uses.
BINARY_SIGNALS = {
    rb"(?i)d3d(8|9|11|12)\.dll": "graphics:direct3d",
    rb"(?i)ddraw\.dll": "graphics:directdraw",
    rb"(?i)opengl32\.dll": "graphics:opengl",
    rb"(?i)vulkan-1\.dll": "graphics:vulkan",
    rb"(?i)dinput8?\.dll": "input:directinput",
    rb"(?i)xinput\d_\d\.dll|xinput9_1_0\.dll": "input:xinput",
    rb"GetAsyncKeyState": "input:keyboard-polling",
    rb"GetCursorPos|SetCursorPos|ClipCursor": "input:absolute-pointer",
    rb"(?i)winmm\.dll": "audio:winmm",
    rb"(?i)dsound\.dll": "audio:directsound",
    rb"(?i)ws2_32\.dll|wsock32\.dll": "network",
    rb"(?i)bink(w32|2w64)?\.dll": "video:bink",
}
SOURCE_SIGNALS = {
    r"SDL_FINGER|SDL_TOUCH|nxn_input_touch|finger_hook|FingerId|touch_count": "input:multitouch",
    r"SDL_MOUSEWHEEL|WM_MOUSEWHEEL|mouse_wheel": "input:wheel",
    r"SDL_GameController|SDL_Joystick|nxn_input_pad": "input:gamepad",
    r"SDL_SetRelativeMouseMode|mouse_relative|RawInput": "input:relative-mouse",
    r"edge_scroll|EdgeScroll|ScrollRate": "input:edge-scroll",
}
ENGINE_FILES = {
    "UnityPlayer.dll": "Unity", "globalgamemanagers": "Unity", "data.pck": "Godot", "*.pck": "Godot",
    "liblist.gam": "GoldSrc/Xash3D", "hl.exe": "GoldSrc", "gamemd.exe": "Westwood RA2 engine",
    "ra2.mix": "Westwood RA2 engine", "game.exe": "unknown", "*.pak": "pak-based (id Tech / Unreal / other)",
    "*.wad": "WAD-based (id Tech / GoldSrc)", "*.bsp": "BSP maps (id Tech / Source / GoldSrc)",
}
# Genre hints. Each hit adds weight; this is a guess, shown with its evidence.
GENRE_HINTS = {
    "rts": [r"(?i)\bmix\b", r"(?i)campaign", r"(?i)skirmish", r"(?i)ra2|redalert|aoe|empires|starcraft|warcraft"],
    "fps": [r"(?i)\.bsp$", r"(?i)cstrike|valve|halflife|quake|doom|unreal", r"(?i)weapons?"],
    "editor": [r"(?i)blender|editor|studio|cad|sketch"],
}
BINARY_LIMIT = 80 * 1024 * 1024


def scan_names(root, limit=20000):
    names = []
    for index, path in enumerate(root.rglob("*")):
        if index >= limit:
            break
        names.append(path)
    return names


def detect_engines(names):
    found = {}
    for path in names:
        for pattern, engine in ENGINE_FILES.items():
            if (pattern.startswith("*") and path.name.lower().endswith(pattern[1:])) or path.name.lower() == pattern.lower():
                found.setdefault(engine, str(path.name))
    return found


def scan_binaries(names):
    signals = {}
    for path in names:
        if path.suffix.lower() != ".exe" or not path.is_file():
            continue
        if path.stat().st_size > BINARY_LIMIT:
            continue
        data = path.read_bytes()
        for pattern, signal in BINARY_SIGNALS.items():
            if re.search(pattern, data):
                signals.setdefault(signal, path.name)
    return signals


def scan_sources(names):
    signals = {}
    for path in names:
        if path.suffix.lower() not in (".c", ".cpp", ".h", ".hpp", ".cc") or "recomp" in path.parts or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, signal in SOURCE_SIGNALS.items():
            if re.search(pattern, text):
                signals.setdefault(signal, path.name)
    return signals


def guess_genre(names):
    scores = {}
    evidence = {}
    for path in names:
        for genre, patterns in GENRE_HINTS.items():
            for pattern in patterns:
                if re.search(pattern, path.name):
                    scores[genre] = scores.get(genre, 0) + 1
                    evidence.setdefault(genre, []).append(path.name)
                    break
    if not scores:
        return "generic", 0, []
    genre = max(scores, key=scores.get)
    return genre, scores[genre], sorted(set(evidence[genre]))[:5]


def analyze(root):
    names = scan_names(root)
    engines = detect_engines(names)
    signals = {}
    signals.update(scan_binaries(names))
    signals.update(scan_sources(names))
    genre, weight, evidence = guess_genre(names)
    notes = []
    graphics = [s for s in signals if s.startswith("graphics:")]
    if any(s in signals for s in ("graphics:direct3d", "graphics:directdraw")):
        notes.append("DirectX graphics: needs a translation layer or recompilation path; record the choice in PORT.md.")
    if "input:wheel" not in signals and genre in ("rts", "editor"):
        notes.append("No mouse wheel use found: the game may have no camera zoom. Add input.unsupported: [camera_zoom] only after checking in the running game.")
    if "input:multitouch" not in signals:
        notes.append("No multitouch use found: touch must be added by the port (pointer emulation, two-finger pan).")
    if "input:gamepad" not in signals:
        notes.append("No gamepad use found: the port must map pad actions to the engine's keyboard/mouse input.")
    if "input:absolute-pointer" in signals:
        notes.append("Absolute pointer used: choose direct touch or a virtual pointer for gamepad play.")
    return {
        "path": str(root),
        "engines": engines,
        "signals": sorted(signals),
        "signalEvidence": signals,
        "genreGuess": {"profile": genre, "weight": weight, "evidence": evidence,
                       "confidence": "low" if weight < 3 else "medium"},
        "notes": notes,
        "next": f"python _PortStudioMain/tools/port_studio.py experience init <port> {genre}",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.path.is_dir():
        print(f"Error: {args.path} is not a directory.", file=sys.stderr)
        return 1
    report = analyze(args.path)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Engines   : {report['engines'] or 'none recognised'}")
        print(f"Signals   : {', '.join(report['signals']) or 'none'}")
        g = report["genreGuess"]
        print(f"Genre     : {g['profile']} ({g['confidence']} confidence) {g['evidence']}")
        for note in report["notes"]:
            print(f"- {note}")
        print(f"Next      : {report['next']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
