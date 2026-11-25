"""One command that runs every available check of a port and prints one PASS / FAIL / NOT_RUN table.

  python _PortStudioMain/tools/verify.py <port-dir> [--module <file.nxvmod>] [--sdk <snapshot>] [--json]

Read-only: it never writes into the port folder. Exit code 1 when any row is FAIL (WARN and NOT_RUN do not fail).
Checks: native module (check-win, exports, check-design, check-lib), ABI imports against the SDK snapshot,
app.json fields and locales, package limits and personal-data separation, shaders, sizes, update and
clean-install emulator scenarios.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import port_studio as studio
from studio_files import app_runtime

PASS, FAIL, NOT_RUN, WARN = "PASS", "FAIL", "NOT_RUN", "WARN"
LOCALES = ("en", "tr", "de", "es", "fr", "ja", "ko", "zh")
TIMEOUT = 180
SHADER_SUFFIXES = {".glsl", ".vert", ".frag"}
SKIP_DIRS = {"build", "dist", "work", "node_modules", ".git", "_realesedbuilds", "appmarket", ".emulator_profile",
             "build_nx", "build_nx_studio", "screenshots"}
DEFAULT_LIMITS = {"packageFilesMax": 20000, "packageUnpackedBytesMax": 1 << 30}
SCENARIO_NOTES = {
    "update": "Setup before the run: install the previous version of the package, then this version over it (same app ID, higher version). The save and settings must survive.",
    "clean_install": "Setup before the run: remove the app and its data folder from the emulator profile, then install this version. First run must reach the data-folder prompt or the menu.",
}


def scenario_template(name):
    return {"note": SCENARIO_NOTES[name], "wait": 25, "timeout": 240,
            "steps": ["shot launcher", "tap play", "wait 30", "shot ingame_00s", "wait 10", "shot ingame_10s", "stats ingame"],
            "gameplay": ["ingame_00s", "ingame_10s"], "motion": [["ingame_00s", "ingame_10s"]]}


class NotRun(Exception):
    """A tool could not run (no devkitPro, timeout, missing file); the row becomes NOT_RUN, never a crash."""


def row(check, status, detail="", fix=""):
    return {"check": check, "status": status, "detail": detail, "fix": fix}


def version_tuple(text):
    return tuple(int(p) for p in re.findall(r"\d+", str(text))[:3])


def load_caps():
    path = studio.STUDIO / "platform" / "capabilities.json"
    try:
        return studio.read_json(path)
    except (OSError, ValueError):
        return {}


def tool_env():
    env = dict(os.environ)
    kit = studio.devkit_path()
    if os.name == "nt":
        env.setdefault("DEVKITPRO_WIN", str(kit))
        bash = kit / "msys2/usr/bin/bash.exe"
        if bash.is_file():
            env.setdefault("DKP_BASH", str(bash))
    else:
        env.setdefault("DEVKITPRO", str(kit))
    return env


def devkit_missing():
    kit = studio.devkit_path()
    return None if (kit / "devkitA64").is_dir() else f"devkitPro not found at {kit} (set DEVKITPRO_WIN / DEVKITPRO)."


def run_tool(script, args, *, devkit=True, timeout=TIMEOUT):
    """Run a snapshot Python tool. Returns (exit code, combined output). Raises NotRun when it cannot run."""
    if not Path(script).is_file():
        raise NotRun(f"SDK tool missing: {script}")
    if devkit:
        reason = devkit_missing()
        if reason:
            raise NotRun(reason)
    try:
        done = subprocess.run([sys.executable, "-B", str(script), *map(str, args)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=tool_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        raise NotRun(f"{Path(script).name} timed out after {timeout} s.")
    except OSError as error:
        raise NotRun(f"{Path(script).name} could not start: {error}")
    return done.returncode, (done.stdout + done.stderr).strip()


def tail(text, lines=6):
    return " | ".join(text.splitlines()[-lines:])


def find_files(base, suffixes):
    found = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        found += [Path(root) / f for f in files if Path(f).suffix.lower() in suffixes]
    return sorted(found)


def flatten(value, prefix=""):
    if isinstance(value, dict):
        return {k for key, sub in value.items() for k in flatten(sub, f"{prefix}{key}.")}
    return {prefix.rstrip(".")}


def source_dir(port):
    if (port / "source" / "app.json").is_file():  # App Market item layout of script apps (nxv new --store)
        return port / "source"
    try:
        slug, category, _, _ = studio.config_for(port)
        item = studio.store_item(port, slug, category)
        if (item / "source").is_dir():
            return item / "source"
    except (ValueError, OSError):
        pass
    return port


def check_module(rows, snapshot, module):
    if module is None:
        for name in ("module/check-win", "abi"):
            rows.append(row(name, NOT_RUN, "no .nxvmod found (build and stage it, or pass --module)."))
        return
    native = snapshot / studio.NATIVE.relative_to(studio.SDK)
    imports = snapshot / studio.NATIVE_TOOLS.relative_to(studio.SDK) / "nxwin_imports.py"
    try:
        code, out = run_tool(native, ["check-win", module])
        rows.append(row("module/check-win", PASS if code == 0 else FAIL, tail(out) if code else module.name,
                        "" if code == 0 else ("SDL symbols are missing: build the windowed SDL2 sysroot from the same SDK and pass "
                                              "--sysroot <dir> (or set NEXVYN_SYSROOT)." if "SDL_" in out else
                                              "Rebuild with the windowed kit (-fPIC, libnexvyn_window.a); drop or replace the imports listed.")))
    except NotRun as error:
        rows.append(row("module/check-win", NOT_RUN, str(error)))
    preview = {a["symbol"] for a in load_caps().get("newApis", []) if a.get("status") == "private-preview"}
    try:
        code, out = run_tool(imports, ["imports", module])
        missing = re.findall(r"not in the host import set: (\S+)", out)
        if not missing and code:
            rows.append(row("abi", NOT_RUN, "nxwin_imports failed: " + tail(out)))
        elif not missing:
            rows.append(row("abi", PASS, "every undefined symbol is in the snapshot host table."))
        else:
            labelled = [f"{m} (private preview: needs a newer public SDK)" if m in preview else m for m in missing]
            only_preview = all(m in preview for m in missing)
            rows.append(row("abi", FAIL, f"{len(missing)} symbols missing: " + ", ".join(labelled),
                            "Needs a newer public SDK: build against a snapshot that lists these symbols (see SDK_UPDATES.md)."
                            if only_preview else
                            "Remove or replace the unlisted imports, or select a newer public SDK snapshot with --sdk."))
    except NotRun as error:
        rows.append(row("abi", NOT_RUN, str(error)))


def is_imgui_app(port):
    if (port / "LICENSE-IMGUI.txt").is_file():
        return True
    return any("imgui" in p.name.lower() for p in find_files(port / "src", {".h", ".hpp", ".cpp", ".c"})) \
        if (port / "src").is_dir() else False


def check_native_extras(rows, snapshot, port):
    native = snapshot / studio.NATIVE.relative_to(studio.SDK)
    libs = find_files(port, {".nxvlib"})
    if not libs:
        rows.append(row("module/exports", NOT_RUN, "no .nxvlib in the port."))
        rows.append(row("module/check-lib", NOT_RUN, "no .nxvlib in the port."))
    else:
        try:
            with tempfile.TemporaryDirectory(prefix="verify-") as work:
                code, out = run_tool(native, ["exports", *libs, "-o", Path(work) / "exports.ld"])
            rows.append(row("module/exports", PASS if code == 0 else FAIL, tail(out),
                            "" if code == 0 else "Rebuild the .nxvlib files; they must be readable shared objects."))
        except NotRun as error:
            rows.append(row("module/exports", NOT_RUN, str(error)))
        for lib in libs:
            try:
                code, out = run_tool(native, ["check-lib", lib])
                rows.append(row(f"module/check-lib {lib.name}", PASS if code == 0 else FAIL, tail(out),
                                "" if code == 0 else "Compile the library with -fPIC and no TLS; export what the app imports."))
            except NotRun as error:
                rows.append(row(f"module/check-lib {lib.name}", NOT_RUN, str(error)))
    if not is_imgui_app(port):
        rows.append(row("module/check-design", NOT_RUN, "not an ImGui app."))
        return
    try:
        code, out = run_tool(native, ["check-design", port], devkit=False)
        lines = [l for l in out.splitlines() if l.startswith("FAIL") or l.startswith("design:")]
        rows.append(row("module/check-design", PASS if code == 0 else FAIL, tail("\n".join(lines)),
                        "" if code == 0 else "Fix the FAIL lines: frame layer, nxn_os_* widgets, NXN_S strings."))
    except NotRun as error:
        rows.append(row("module/check-design", NOT_RUN, str(error)))


def check_manifest(rows, src):
    try:
        manifest = studio.read_json(src / "app.json")
    except (OSError, ValueError) as error:
        rows.append(row("app.json", FAIL, f"unreadable: {error}", f"Create a valid app.json in {src}."))
        return
    native = app_runtime(manifest) == "native"
    missing = [k for k in (("minNative", "minSdk") if native else ("minSdk",)) if not manifest.get(k)]
    memory = manifest.get("memory")
    if not isinstance(memory, int) or isinstance(memory, bool) or memory <= 0:
        missing.append("memory")
    rows.append(row("app.json/fields", FAIL if missing else PASS,
                    "missing: " + ", ".join(missing) if missing else ("minNative, " if native else "") + "minSdk, memory set.",
                    'Add the fields to app.json, e.g. "minNative": "1.1", "minSdk": "1.13", "memory": 256 (MB needed at start).'
                    if missing else ""))
    if manifest.get("loadingHint"):
        rows.append(row("app.json/loadingHint", PASS, "set."))
    else:
        rows.append(row("app.json/loadingHint", WARN, "loadingHint is not set.",
                        'If startup or level loads take longer than 5 s, add "loadingHint": true (minSdk 1.13) so the OS waits 120 s.'))
    if manifest.get("liveResize"):
        ok = version_tuple(manifest.get("minNative", "0")) >= (1, 1)
        rows.append(row("app.json/liveResize", PASS if ok else FAIL,
                        "minNative >= 1.1." if ok else "liveResize needs minNative >= 1.1.",
                        "" if ok else 'Set "minNative": "1.1" or higher, or remove liveResize.'))
    problems, key_sets = [], {}
    for code in LOCALES:
        path = src / "lang" / f"{code}.json"
        if not path.is_file():
            problems.append(f"missing lang/{code}.json")
            continue
        try:
            key_sets[code] = flatten(studio.read_json(path))
        except (OSError, ValueError) as error:
            problems.append(f"lang/{code}.json unreadable ({error})")
    if key_sets:
        reference = key_sets.get("en") or next(iter(key_sets.values()))
        for code, keys in key_sets.items():
            if keys != reference:
                gone, extra = sorted(reference - keys), sorted(keys - reference)
                parts = [f"missing {', '.join(gone[:5])}" if gone else "", f"extra {', '.join(extra[:5])}" if extra else ""]
                problems.append(f"lang/{code}.json: " + "; ".join(p for p in parts if p))
    rows.append(row("app.json/locales", FAIL if problems else PASS,
                    "; ".join(problems) if problems else "8 locales, identical keys.",
                    "Add or translate the listed keys so all 8 files (en tr de es fr ja ko zh) share the keys of en.json."
                    if problems else ""))


def check_limits(rows, port, src):
    limits = {**DEFAULT_LIMITS, **load_caps().get("limits", {})}
    try:
        files = list(studio.list_files(src))
    except (OSError, ValueError) as error:
        rows.append(row("limits/package", FAIL, str(error), "Fix the package folder layout."))
        return 0
    size = sum((src / f).stat().st_size for f in files)
    count = len(files)
    detail = f"{count:,} files, {size / (1 << 20):,.0f} MiB unpacked."
    if count > limits["packageFilesMax"] or size > limits["packageUnpackedBytesMax"]:
        rows.append(row("limits/package", FAIL, detail,
                        f"Nexvyn OS refuses more than {limits['packageFilesMax']:,} files or "
                        f"{limits['packageUnpackedBytesMax'] >> 20} MiB. Merge small files into archives or let the player pick the data folder."))
    elif count > 1000:
        rows.append(row("limits/package", WARN, detail,
                        'Above 1,000 files the install sheet can look frozen on "Checking the package". Merge files or drop bundled data.'))
    else:
        rows.append(row("limits/package", PASS, detail))
    try:
        _, _, public, mappings = studio.config_for(port)
        issues, listed = [], {p.as_posix() for p in public}
        for rel in files:
            try:
                studio.check_payload_name(rel, public=True)
            except ValueError as error:
                issues.append(f"{rel}: {error}")
            if rel.as_posix() not in listed:
                issues.append(f"{rel} is not in publicFiles")
            for _, target in mappings:
                a, b = rel.as_posix().casefold(), target.as_posix().casefold()
                if a == b or a.startswith(b + "/"):
                    issues.append(f"{rel} is personal game data (localData target)")
        rows.append(row("limits/personal-data", FAIL if issues else PASS,
                        "; ".join(issues[:6]) if issues else "no personal data in the Store source.",
                        "Remove the file from AppMarket/.../source and keep it in localData (personal packages only)."
                        if issues else ""))
    except (ValueError, OSError) as error:
        rows.append(row("limits/personal-data", FAIL, f"port.json: {error}",
                        "Fix port.json (slug, storeCategory, publicFiles, localData)."))
    return size


def check_shaders(rows, snapshot, port):
    shaders = find_files(port, SHADER_SUFFIXES)
    if not shaders:
        rows.append(row("shaders", NOT_RUN, "no *.glsl, *.vert or *.frag files in the port."))
        return
    native = snapshot / studio.NATIVE.relative_to(studio.SDK)
    try:
        _, out = run_tool(native, ["--help"], devkit=False)
    except NotRun as error:
        rows.append(row("shaders", NOT_RUN, str(error)))
        return
    if not re.search(r"[{,]shader[,}]|^\s+shader\s", out, re.M):
        rows.append(row("shaders", NOT_RUN, "shader tool is preview-only (the snapshot nxv_native has no `shader` subcommand)."))
        return
    try:
        code, out = run_tool(native, ["shader", *shaders])
        rows.append(row("shaders", PASS if code == 0 else FAIL, tail(out), "" if code == 0 else "Fix the shader errors above."))
    except NotRun as error:
        rows.append(row("shaders", NOT_RUN, str(error)))


def check_scenarios(rows, port):
    try:
        scenarios = studio.read_json(port / "port.json").get("emulator", {}).get("scenarios", {})
    except (OSError, ValueError) as error:
        rows.append(row("scenarios", FAIL, f"port.json unreadable: {error}"))
        return
    for name in ("update", "clean_install"):
        block = scenarios.get(name) if isinstance(scenarios, dict) else None
        if isinstance(block, dict) and any(str(s).split()[:1] == ["shot"] for s in block.get("steps", [])):
            rows.append(row(f"scenario/{name}", PASS, "declared in port.json emulator.scenarios."))
        else:
            snippet = json.dumps({"emulator": {"scenarios": {name: scenario_template(name)}}})
            rows.append(row(f"scenario/{name}", FAIL, f"emulator.scenarios.{name} is missing or takes no screenshot.",
                            "Add (adapt the steps to the port):\n" + snippet))


# A port must show the real program's output. A built-in or synthetic program, a generated scene, a test pattern or
# a pre-rendered picture shown in its place is a fake (forbidden). A labelled status screen that says what it is may
# stay when the line (or the line above) carries `nx-allow-standin: <reason>`; it is then reported as WARN.
STAND_IN = re.compile(
    r"(?i)(?<![a-z0-9])(load_?built_?in_?rom|built[-_ ]?in[-_ ]?(rom|program|demo|game)|fake[-_ ]?(frame|scene|game|render|output|screen)"
    r"|demo[-_ ]?scene|test[-_ ]?pattern|synthetic[-_ ]?(frame|scene|game|program|output)"
    r"|placeholder[-_ ]?(scene|game|frame|render|output)|pre[-_ ]?rendered[-_ ]?(menu|game|scene))(?![a-z0-9])")
STAND_IN_ALLOW = "nx-allow-standin:"
STAND_IN_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".lua", ".js", ".mjs", ".py", ".ts"}
STAND_IN_SKIP = {"gen", "generated", "vendor", "third_party", "thirdparty", "external", "extern", "deps", "upstream"}
STAND_IN_MAX_BYTES = 512 * 1024
PERSONAL_PATH = re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+[^\\/\s`'\"]+|/home/[^/\s`'\"]+/|/Users/[^/\s`'\"]+/")
RECORDS = ("PORT.md", "KNOWN_ISSUES.md", "CHANGELOG.md", "DISTRIBUTION.md", "README.md")


def check_stand_in(rows, port):
    hits, allowed = [], []
    for path in find_files(port, STAND_IN_SUFFIXES):
        rel = path.relative_to(port)
        if STAND_IN_SKIP & {part.lower() for part in rel.parts[:-1]} or path.stat().st_size > STAND_IN_MAX_BYTES:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines, 1):
            match = STAND_IN.search(line)
            if not match:
                continue
            context = line + (lines[number - 2] if number > 1 else "")
            target = allowed if STAND_IN_ALLOW in context else hits
            target.append(f"{rel.as_posix()}:{number} ({match.group(0)})")
    if hits:
        rows.append(row("content/stand-in", FAIL, "; ".join(hits[:6]) + (" ..." if len(hits) > 6 else ""),
                        "Show only the real program's output. Remove the built-in/synthetic content, or, for a labelled "
                        "status screen, add `nx-allow-standin: <reason>` and say so in PORT.md."))
    elif allowed:
        rows.append(row("content/stand-in", WARN, "declared stand-ins: " + "; ".join(allowed[:6]),
                        "Make sure the screen says what it is and never counts as gameplay."))
    else:
        rows.append(row("content/stand-in", PASS, "no built-in, synthetic or fake content markers in the port's code."))


def check_record_paths(rows, port):
    hits = []
    for name in RECORDS:
        path = port / name
        if path.is_file():
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if PERSONAL_PATH.search(line):
                    hits.append(f"{name}:{number}")
    if hits:
        rows.append(row("records/personal-paths", WARN, "machine paths in records: " + ", ".join(hits[:8]),
                        "Write paths relative to the port or as <game-dir>; never a user folder."))
    else:
        rows.append(row("records/personal-paths", PASS, "no user-folder paths in the port records."))


def verify_script(port, src, runtime, snapshot, rows):
    """Script app (Lua, JavaScript, Python 3 ...): the SDK's own `nxv check` replaces the native module checks."""
    if snapshot is None:
        rows.append(row("script/nxv-check", NOT_RUN, "SDK snapshot unusable (see the sdk row)."))
    else:
        try:
            code, out = run_tool(snapshot / studio.NXV.relative_to(studio.SDK), ["check", src], devkit=False)
            rows.append(row("script/nxv-check", PASS if code == 0 else FAIL, f"{runtime} app" if code == 0 else tail(out),
                            "" if code == 0 else "Fix the problems nxv check lists."))
        except NotRun as error:
            rows.append(row("script/nxv-check", NOT_RUN, str(error)))
    for name in ("module/check-win", "abi", "module/exports", "module/check-lib", "module/check-design", "shaders"):
        rows.append(row(name, NOT_RUN, f"{runtime} app: no native module."))
    check_manifest(rows, src)
    package_size = check_limits(rows, port, src)
    rows.append(row("size", PASS, f"package {package_size / (1 << 20):,.2f} MiB unpacked."))
    check_scenarios(rows, port)
    check_stand_in(rows, port)
    check_record_paths(rows, port)
    return rows


def verify(port, module=None, sdk=None):
    port = Path(port).resolve()
    rows = []
    try:
        snapshot = studio.port_sdk(port, Path(sdk) if sdk else None)
        snapshot_ok = True
    except (ValueError, OSError) as error:
        snapshot, snapshot_ok = None, False
        rows.append(row("sdk", FAIL, str(error),
                        "Select the matching snapshot with --sdk or run bootstrap --port <port> --fetch."))
    src = source_dir(port)
    try:
        runtime = app_runtime(studio.read_json(src / "app.json"))
    except (OSError, ValueError):
        runtime = "native"
    if runtime != "native":
        return verify_script(port, src, runtime, snapshot if snapshot_ok else None, rows)
    if module is None:
        try:
            main = studio.read_json(src / "app.json").get("main")
            candidate = src / main if isinstance(main, str) else None
        except (OSError, ValueError):
            candidate = None
        module = candidate if candidate and candidate.is_file() else None
    else:
        module = Path(module).resolve()
        if not module.is_file():
            rows.append(row("module/check-win", FAIL, f"{module} does not exist.", "Pass an existing .nxvmod."))
            module = None
    if snapshot_ok:
        check_module(rows, snapshot, module)
        check_native_extras(rows, snapshot, port)
    else:
        for name in ("module/check-win", "abi", "module/exports", "module/check-lib", "module/check-design"):
            rows.append(row(name, NOT_RUN, "SDK snapshot unusable (see the sdk row)."))
    check_manifest(rows, src)
    package_size = check_limits(rows, port, src)
    if snapshot_ok:
        check_shaders(rows, snapshot, port)
    else:
        rows.append(row("shaders", NOT_RUN, "SDK snapshot unusable (see the sdk row)."))
    package = f"package {package_size / (1 << 20):,.2f} MiB unpacked."
    if module:
        rows.append(row("size", PASS, f"module {module.stat().st_size / (1 << 20):,.2f} MiB; {package}"))
    else:
        rows.append(row("size", NOT_RUN, f"module not built yet; {package}"))
    check_scenarios(rows, port)
    check_stand_in(rows, port)
    check_record_paths(rows, port)
    return rows


def render(rows):
    width = max(len(r["check"]) for r in rows)
    lines = [f"{'CHECK':<{width}}  {'STATUS':<7}  DETAIL"]
    for r in rows:
        lines.append(f"{r['check']:<{width}}  {r['status']:<7}  {r['detail']}")
        if r["fix"] and r["status"] in (FAIL, WARN):
            lines += [f"{'':<{width}}           fix: {part}" for part in r["fix"].splitlines()]
    counts = {s: sum(r["status"] == s for r in rows) for s in (PASS, FAIL, WARN, NOT_RUN)}
    lines.append(f"Result: {counts[PASS]} PASS, {counts[FAIL]} FAIL, {counts[WARN]} WARN, {counts[NOT_RUN]} NOT_RUN")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run every available port check and print one table.")
    parser.add_argument("port")
    parser.add_argument("--module", help="native module to check (default: app.json main in the Store source)")
    parser.add_argument("--sdk", help="SDK snapshot folder (default: the one the port pins)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = verify(args.port, args.module, args.sdk)
    except (ValueError, OSError) as error:
        rows = [row("verify", FAIL, str(error), "Pass a port folder.")]
    print(json.dumps(rows, indent=2) if args.json else render(rows))
    return 1 if any(r["status"] == FAIL for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
