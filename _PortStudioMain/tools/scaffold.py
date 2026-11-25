"""Create a port skeleton from an assess report, or a new app from an idea (no source, no assess).

  python _PortStudioMain/tools/scaffold.py <game|software> <slug> <category> --from-assess report.json
         [--template NAME] [--allow-preview] [--dest WORKSPACE_ROOT]
  python _PortStudioMain/tools/scaffold.py new-app <lua|js|python3|native-app|game|emulator|decomp|web> <slug>
         [--name NAME] [--category CATEGORY] [--game] [--dest WORKSPACE_ROOT]

new-app: native-app and game use the port skeleton below with the kit `app` / `game` template; lua, js and
python3 use the SDK's `nxv new --store` (App Market layout, eight locales) and are checked and packed with `nxv`;
web writes an HTML5 starter for the OS browser (the public SDK has no packaged web runtime).

Runs `port_studio.py init` (records, SDK pin, store item), then adds CMakeLists.txt and src/ from the public
SDK snapshot template, lang/ skeletons, app.json, the port.json experience block and src/nx_port_rules.h.
Never overwrites an existing port folder.
"""

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import experience as xp
import port_studio as studio

TEMPLATES = studio.STUDIO / "templates" / "scaffold"
KIT_TEMPLATES = studio.STUDIO / "nexvyn_sdk" / "Languages" / "c" / "native-kit" / "sdk" / "native" / "templates"
LOCALES = ("en", "tr", "de", "es", "fr", "ja", "ko", "zh")
GENRE_PROFILE = {"strategy": "rts", "action": "fps", "racing": "generic", "developer": "editor", "productivity": "editor"}
SKIP_TEMPLATE_FILES = {"template.json", "README.md"}
EMULATOR_BLOCK = {
    "targets": {"play": {"handheld": [640, 600], "docked": [640, 600]}},
    "scenarios": {
        "gameplay": {
            "wait": 30, "timeout": 240,
            "steps": ["shot launcher", "tap play", "wait 40", "shot ingame_00s", "padhold a 2", "wait 10",
                      "shot ingame_10s", "stats ingame"],
            "gameplay": ["ingame_00s", "ingame_10s"],
            "motion": [["ingame_00s", "ingame_10s"]],
            "expectLog": [],
        },
        "update": {"steps": ["shot after_update"],
                   "note": "install the previous package, then this one over it; data must survive"},
        "clean_install": {"steps": ["shot first_launch"],
                          "note": "remove the app and its data, install, first launch"},
    },
}


def read(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def fill(text, slug):
    return text.replace("@NAME@", slug)


def template_name(report, requested, kind):
    if requested:
        return requested
    chosen = report.get("template")
    if isinstance(chosen, dict):
        chosen = chosen.get("name")
    return chosen or ("game" if kind == "game" else "app")


def pick_profile(report, category):
    named = (report.get("performance") or {}).get("profile")
    if named and (studio.STUDIO / "profiles" / f"{named}.json").is_file():
        return named  # assess already chose it from the tier and the source type
    if report.get("graphics", {}).get("level", 0) >= 4:
        return "heavy"
    return GENRE_PROFILE.get(category, "generic")


def copy_template(kit_template, port, slug):
    src_dir = KIT_TEMPLATES / kit_template
    if not (src_dir / "CMakeLists.txt").is_file():
        raise ValueError(f"No SDK snapshot template named '{kit_template}'.")
    for path in sorted(src_dir.rglob("*")):
        rel = path.relative_to(src_dir)
        if path.is_dir() or rel.name in SKIP_TEMPLATE_FILES or rel.parts[0] == "lang":
            continue
        target = port / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(fill(path.read_text(encoding="utf-8"), slug), encoding="utf-8", newline="\n")
        except UnicodeDecodeError:
            shutil.copyfile(path, target)


def builds_nro(kit_template):
    cmake = KIT_TEMPLATES / kit_template / "CMakeLists.txt"
    return cmake.is_file() and "nexvyn_add_nro(" in cmake.read_text(encoding="utf-8")


def windowed_base(kit_template):
    if kit_template == "vulkan" or builds_nro(kit_template):
        return "game"
    return kit_template


def add_skeleton_sources(kit_template, port):
    """Helper sources of an NRO skeleton (not its main loop), compiled into the windowed game template."""
    if not builds_nro(kit_template):
        return []
    added = []
    for path in sorted((KIT_TEMPLATES / kit_template / "src").iterdir()):
        if path.stem == "main" or path.suffix not in {".c", ".cpp", ".h"}:
            continue
        source = TEMPLATES / "jit_memory_nxn.cpp" if path.name == "jit_memory.cpp" else path  # libnx JIT -> nxn_jit
        (port / "src" / path.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        if path.suffix in {".c", ".cpp"}:
            added.append(f"src/{path.name}")
    cmake = port / "CMakeLists.txt"
    text = cmake.read_text(encoding="utf-8")
    if added and "SOURCES src/main.cpp" in text:
        cmake.write_text(text.replace("SOURCES src/main.cpp", "SOURCES src/main.cpp " + " ".join(added), 1),
                         encoding="utf-8", newline="\n")
    return added


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


def scaffold(args):
    report = json.loads(Path(args.from_assess).read_text(encoding="utf-8-sig"))
    root = Path(args.dest).resolve() if args.dest else studio.ROOT
    port_type = "GamePorts" if args.kind == "game" else "SoftwarePorts"
    port = root / port_type / args.slug
    if port.exists():
        raise ValueError(f"{port} already exists; scaffold never overwrites a port.")
    kit_template = template_name(report, args.template, args.kind)
    vk_status = studio_caps()["graphics"]["vulkan"]["status"]
    if kit_template == "vulkan" and vk_status != "released" and not args.allow_preview:
        raise ValueError("The vulkan template is private-preview. Pass --allow-preview to accept a GL fallback skeleton.")
    tier = (report.get("performance") or {}).get("tier", report.get("graphics", {}).get("level", 0))
    profile = pick_profile(report, args.category)
    xp.load_profile(profile)  # fail before anything is written
    (root / port_type).mkdir(parents=True, exist_ok=True)

    original_root = studio.ROOT
    studio.ROOT = root
    try:
        studio.init_port(SimpleNamespace(kind=args.kind, slug=args.slug, category=args.category, sdk=None))
    finally:
        studio.ROOT = original_root

    # vulkan keeps the GL game template (the kit's vulkan template has no GL fallback). Kit skeletons that build a
    # stand-alone NRO (emu-skeleton, decomp-skeleton) become windowed modules: game template plus their helper sources.
    copy_template(windowed_base(kit_template), port, args.slug)
    add_skeleton_sources(kit_template, port)
    src = port / "src"
    src.mkdir(exist_ok=True)
    write_text(src / "nx_port_rules.h", fill(read("nx_port_rules.h"), args.slug))
    if kit_template == "vulkan":
        write_text(src / "nx_vulkan_path.h", fill(read("nx_vulkan_path.h"), args.slug))

    english = json.loads(fill(read("lang_en.json"), args.slug))
    for locale in LOCALES:
        write_json(port / "lang" / f"{locale}.json", english)  # English text until translated; same keys
    write_text(port / "TODO_icon.txt", read("TODO_icon.txt"))
    write_text(port / "TODO_screenshots.txt", read("TODO_screenshots.txt"))

    lock = json.loads((port / "sdk.lock.json").read_text(encoding="utf-8"))
    settings = report.get("osSettings")
    memory = settings.get("memory") if isinstance(settings, dict) and isinstance(settings.get("memory"), int) else None
    names = {locale: args.slug for locale in LOCALES}
    app = {
        "id": f"com.example.{args.slug}", "name": names, "description": dict(names), "version": "0.1.0",
        "category": "games" if args.kind == "game" else "apps", "runtime": "native",
        "mode": "fullscreen" if args.kind == "game" else "window",
        "minSdk": lock["sdk"], "targetSdk": lock["sdk"], "minNative": "1.1", "targetNative": lock["native"],
        "main": f"{args.slug}.nxvmod", "gamepad": args.kind == "game", "permissions": [],
        "memory": memory or 512,
    }
    # Defaults for every new port: 120 s loading grace, and the compositor frees its memory while the port runs
    # fullscreen (fullscreenPause takes effect from OS 1.4.0).
    app["loadingHint"] = True
    app["fullscreenPause"] = True
    item = port / "AppMarket" / "Store" / studio.PORT_TYPES[port_type][1] / args.category / args.slug
    write_json(item / "source" / "app.json", app)
    for locale in LOCALES:  # stage/build refuse when the store copy of lang/ differs from the port's
        write_json(item / "source" / "lang" / f"{locale}.json", english)

    config = json.loads((port / "port.json").read_text(encoding="utf-8"))
    config["experience"] = {"schema": xp.CURRENT_SCHEMA, "profile": profile}
    errors = xp.validate(xp.resolve(copy.deepcopy(config)))
    if errors:
        raise ValueError("experience block invalid: " + "; ".join(errors))
    config["emulator"] = copy.deepcopy(EMULATOR_BLOCK)
    write_json(port / "port.json", config)

    notes = ["", "## Scaffold notes", "",
             f"- Created by scaffold.py from an assess report (verdict: {report.get('verdict', 'unknown')}, "
             f"graphics: {report.get('graphics', {}).get('api', 'unknown')}, tier {tier}).",
             f"- Kit template: `{kit_template}`. Experience profile: `{profile}`.",
             "- Platform rules for the code are in `src/nx_port_rules.h`.",
             "- app.json defaults: `loadingHint` (120 s loading grace) and `fullscreenPause` (from OS 1.4.0 the compositor "
             "frees its memory while the port runs fullscreen).",
             "- Performance: measure with the OS performance panel (Ctrl+Alt+P, or L+R+ZL+ZR; OS 1.4.0): frame time and its "
             "phases, skipped frames, RAM and GPU lock time. Record the numbers and the mode (handheld/docked) here.",
             "- SDL2-based templates (`port`, `sdl2`) link the windowed SDL2 sysroot: build it from the same SDK and "
             "build with `nxv_native build <port> --sysroot <dir>` (or `NEXVYN_SYSROOT`). Without it check-win reports "
             "missing `SDL_*` imports.",
             "- Icon and screenshots are placeholders: see `TODO_icon.txt` and `TODO_screenshots.txt`.",
             "- TODO: the `emulator` block in `port.json` (tap coordinates for the play button) holds placeholders. "
             "Replace them from a real screenshot; scenarios are run by `tools/scenario_run.py`."]
    libs = report.get("libraries", {})
    missing = sorted(libs.get("build_from_source", {})) if isinstance(libs, dict) else []
    notes += ["", "### Missing libraries (build from source)", ""]
    notes += [f"- `{name}`" for name in missing] or ["- None found by the scan."]
    if kit_template == "vulkan":
        notes += ["", "### Vulkan", "",
                  "- Vulkan needs OS 1.4.0 or later; OS 1.3.x has no Vulkan. Check `NXN_CAP_VULKAN` at start and keep the GL "
                  "path as the fallback (`src/nx_vulkan_path.h`).",
                  "- `nxn_vk.h` ships with SDK 1.16; include it through `src/nx_vulkan_path.h`. Ports that also target OS "
                  "1.3.x need the GL path there."]
    if report.get("previewOptions") or report.get("preview"):
        notes += ["", "### Preview", "",
                  "- A preview feature was suggested or chosen. Preview APIs exist on preview OS builds only: keep a GL "
                  "fallback (see `src/nx_vulkan_path.h` when present) and guard calls with the capability macro."]
    with (port / "PORT.md").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(notes) + "\n")
    return port


def studio_caps():
    return json.loads((studio.STUDIO / "platform" / "capabilities.json").read_text(encoding="utf-8"))


NEW_APP_RUNTIMES = ("lua", "js", "python3", "native-app", "game", "emulator", "decomp", "web")
NXV_LANG = {"lua": "lua", "js": "js", "python3": "py"}
NEW_APP_REPORT = {
    "native-app": {"template": "app", "graphics": {"api": "opengl-3.x/gles", "level": 2}},
    "game": {"template": "game", "graphics": {"api": "opengl-3.x/gles", "level": 2}},
    # Emulator: CPU core plus JIT-memory skeleton, interpreter first. Decomp: C game from decompiled source with PC types.
    "emulator": {"template": "emu-skeleton", "graphics": {"api": "2d-or-software", "level": 1}},
    "decomp": {"template": "decomp-skeleton", "graphics": {"api": "opengl-3.x/gles", "level": 2}},
}
WEB_INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@NAME@</title>
<style>
  html, body { margin: 0; height: 100%; background: #101418; color: #e8eef2; font: 16px system-ui, sans-serif; }
  canvas { display: block; width: 100vw; height: 100vh; touch-action: none; }
</style>
</head>
<body>
<canvas id="view"></canvas>
<script>
// @NAME@: starter for the Nexvyn OS browser (HTML5, WebGL2, WASM). Handheld 1280x720, docked 1920x1080.
const canvas = document.getElementById("view");
const gl = canvas.getContext("webgl2");
function frame() {
  canvas.width = canvas.clientWidth * devicePixelRatio;
  canvas.height = canvas.clientHeight * devicePixelRatio;
  if (gl) { gl.viewport(0, 0, canvas.width, canvas.height); gl.clearColor(0.06, 0.08, 0.1, 1); gl.clear(gl.COLOR_BUFFER_BIT); }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script>
</body>
</html>
"""


def new_app(args):
    """Create an app or game from an idea: no source folder and no assess report."""
    root = Path(args.dest).resolve() if args.dest else studio.ROOT
    is_game = args.runtime in ("game", "decomp") or args.game
    port_type = "GamePorts" if is_game else "SoftwarePorts"
    store_type = studio.PORT_TYPES[port_type][1]
    category = args.category or ("arcade" if is_game else "utilities")
    if category not in studio.STORE_CATEGORIES[store_type]:
        raise ValueError(f"Store categories for {store_type}: {', '.join(sorted(studio.STORE_CATEGORIES[store_type]))}")
    name = args.name or args.slug
    if args.runtime in NEW_APP_REPORT:
        report = dict(NEW_APP_REPORT[args.runtime], verdict="new app", performance={"tier": 2}, libraries={})
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "new_app.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            return scaffold(argparse.Namespace(kind="game" if is_game else "software", slug=args.slug, category=category,
                                               from_assess=str(path), template=None, allow_preview=False, dest=str(root)))
    app_dir = root / port_type / args.slug
    if app_dir.exists():
        raise ValueError(f"{app_dir} already exists; scaffold never overwrites an app.")
    if args.runtime == "web":
        (app_dir / "web").mkdir(parents=True)
        write_text(app_dir / "web" / "index.html", WEB_INDEX.replace("@NAME@", name))
        write_text(app_dir / "README.md", f"# {name}\n\nHTML5 app for the Nexvyn OS browser (WebGL2, WASM, workers).\n\n"
                   "- Open `web/index.html` in the OS browser, or serve the folder with `start.bat` on the PC.\n"
                   "- The public SDK has no packaged web runtime, so there is no `.nxvapp` step for this app yet.\n"
                   "- Test both modes: handheld 1280x720 and docked 1920x1080, touch and controller.\n")
        return app_dir
    nxv, _, _ = studio.sdk_paths(studio.SDK)
    (root / port_type).mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(nxv), "new", NXV_LANG[args.runtime], args.slug, "--dir", str(root / port_type), "--store",
               "--kind", "game" if is_game else "app", "--templates", str(studio.SDK / "Languages"), "--id", f"com.example.{args.slug.replace('-', '')}"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise ValueError("nxv new failed: " + (result.stderr or result.stdout).strip())
    manifest_path = app_dir / "source" / "app.json"
    if not manifest_path.is_file():
        raise ValueError(f"nxv new did not create {app_dir / 'source'}.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = {code: name for code in LOCALES}
    manifest["category"] = "games" if is_game else category
    if args.runtime == "python3":
        manifest["loadingHint"] = True  # CPython starts in the background; give it the 120 s loading grace
    # MB needed at start: a starting value per runtime, to be replaced by the measured peak (verify requires it).
    manifest.setdefault("memory", {"lua": 64, "js": 96, "python3": 160}[args.runtime])
    write_json(manifest_path, manifest)
    report = studio.sdk_report(studio.SDK)
    pin = {"repository": report["repository"], "commit": report["commit"],
           **{k: report["versions"][k] for k in ("sdk", "native")}}
    if report.get("prerelease"):
        pin["os"] = report["prerelease"].get("os")
    write_json(app_dir / "sdk.lock.json", pin)
    store_path = app_dir / "store.json"
    if store_path.is_file():  # eight locales are required; English text until translated (like the port scaffold)
        store = json.loads(store_path.read_text(encoding="utf-8"))
        summary = args.summary or f"TODO: one-line summary of {name}"
        for key in ("subtitle", "description"):
            text = {k: v for k, v in (store.get(key) or {}).items() if v} or {"en": summary}
            store[key] = {code: text.get(code) or text.get("en") or summary for code in LOCALES}
        write_json(store_path, store)
    public = sorted(p.relative_to(app_dir / "source").as_posix() for p in (app_dir / "source").rglob("*") if p.is_file())
    write_json(app_dir / "port.json", {
        "slug": args.slug, "kind": "script", "runtime": args.runtime, "storeCategory": category,
        "publicFiles": public, "localData": [],
        "emulator": {"targets": {}, "scenarios": {
            "gameplay": {"wait": 15, "timeout": 120, "steps": ["shot app_00s", "wclick 0.5 0.63", "wait 2", "shot app_05s", "stats app"],
                         "gameplay": ["app_00s", "app_05s"], "motion": [["app_00s", "app_05s"]], "expectLog": [],
                         "note": "wclick 0.5 0.63 presses the template's button (window-relative). Replace it with the app's real main task."},
            "update": {"steps": ["shot after_update"], "note": "install the previous package, then this one; data must survive"},
            "clean_install": {"steps": ["shot first_launch"], "note": "remove the app and its data, install, first launch"}}}})
    write_text(app_dir / "STUDIO.md", f"# {name}\n\nCreated by `scaffold.py new-app {args.runtime}`.\n\n"
               f"- Check: `python _PortStudioMain/nexvyn_sdk/Tools/nxv/nxv.py check {port_type}/{args.slug}/source`\n"
               f"- Package: `python _PortStudioMain/nexvyn_sdk/Tools/nxv/nxv.py pack {port_type}/{args.slug}/source`\n"
               f"- Or all at once: `python _PortStudioMain/tools/port_studio.py make {port_type}/{args.slug}`\n"
               "- Then test in the emulator in both modes and capture real screens for the store.\n")
    return app_dir


def main_new_app(argv):
    parser = argparse.ArgumentParser(prog="scaffold.py new-app", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runtime", choices=NEW_APP_RUNTIMES)
    parser.add_argument("slug")
    parser.add_argument("--name", help="Display name (default: the slug).")
    parser.add_argument("--summary", help="One-line store text (English; copied to all eight locales until translated).")
    parser.add_argument("--category", help="Store category (default: arcade for games, utilities for apps).")
    parser.add_argument("--game", action="store_true", help="Script or web runtime: make it a game.")
    parser.add_argument("--dest", help="Workspace root that holds GamePorts/ and SoftwarePorts/ (default: this repo).")
    args = parser.parse_args(argv)
    try:
        path = new_app(args)
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Created {path}")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "new-app":
        return main_new_app(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=("game", "software"))
    parser.add_argument("slug")
    parser.add_argument("category")
    parser.add_argument("--from-assess", required=True)
    parser.add_argument("--template")
    parser.add_argument("--allow-preview", action="store_true")
    parser.add_argument("--dest", help="Workspace root that holds GamePorts/ and SoftwarePorts/ (default: this repo).")
    args = parser.parse_args(argv)
    try:
        port = scaffold(args)
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Scaffolded {port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
