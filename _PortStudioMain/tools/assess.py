"""Port feasibility report: "can this game or application be ported to Nexvyn OS, and how well will it run?"

  python _PortStudioMain/tools/port_studio.py assess <source-or-game-dir> [--name NAME] [--json] [--out FILE]
  python _PortStudioMain/tools/port_studio.py assess <folder-of-sources> --batch [--json]

Reads source files, build files, licence files, executable import strings and file names. It never runs
anything and never touches the network. Facts about the platform live in platform/capabilities.json (one
place, each fact with its evidence level); source-type rules live in platform/source_types.json; the
rules that read them live here.

The report is a decision aid with its evidence, not a promise. Performance lines are estimates from
rules and the recorded port measurements; they are never device numbers. Anything the scan cannot see
is listed under "Unknown, prototype first".
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import analyze

STUDIO = Path(__file__).resolve().parents[1]
CAPABILITIES = STUDIO / "platform" / "capabilities.json"
SOURCE_TYPES = STUDIO / "platform" / "source_types.json"
PROFILES = STUDIO / "profiles"
SCHEMA_VERSION = 2
DATA_WALK_LIMIT = 500000
SNAPSHOT_INCLUDE = Path(__file__).resolve().parents[1] / "nexvyn_sdk" / "Languages" / "c" / "native-kit" / "sdk" / "native" / "include" / "nexvyn"
SKIP_DIRS = {".git", ".svn", ".hg", "node_modules", "build", "out", "dist", "__pycache__", ".vs", ".idea"}
TEXT_LIMIT = 400 * 1024
FILE_LIMIT = 6000

LANGUAGES = {
    ".c": "C", ".h": "C/C++ header", ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".m": "Objective-C", ".mm": "Objective-C++", ".rs": "Rust", ".go": "Go", ".cs": "C#", ".java": "Java",
    ".kt": "Kotlin", ".swift": "Swift", ".py": "Python", ".lua": "Lua", ".js": "JavaScript", ".ts": "TypeScript",
    ".pas": "Pascal", ".dpr": "Pascal", ".asm": "Assembly", ".s": "Assembly", ".gd": "GDScript", ".zig": "Zig",
    ".html": "HTML", ".htm": "HTML",
}
NATIVE_LANGS = {"C", "C++", "C/C++ header"}
COMPILED_EXTS = {".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".inl", ".m", ".mm", ".rs", ".go", ".cs", ".java",
                 ".kt", ".swift", ".pas", ".dpr", ".asm", ".s", ".zig"}
SOURCE_EXTS = set(LANGUAGES) | {".glsl", ".vert", ".frag", ".comp", ".hlsl", ".wgsl", ".cmake", ".inl"}
# Code under these folders builds, tests or ships alongside the program; it does not run in the port.
SECONDARY_DIRS = {"tools", "tool", "scripts", "script", "test", "tests", "testing", "docs", "doc", "examples", "example",
                  "samples", "bench", "benchmarks", "ci", ".github", "cmake", "third_party", "thirdparty", "3rdparty",
                  "external", "extern", "vendor", "deps", "contrib", "utils", "misc"}
# CMake/pkg-config names that are host tools or built into CMake, not libraries the port links.
BUILD_ONLY_PACKAGES = {"git", "pkgconfig", "threads", "python", "python3", "pythoninterp", "perl", "doxygen", "sphinx",
                       "gtest", "googletest", "catch2", "benchmark", "openmp"}

BUILD_FILES = {
    "CMakeLists.txt": "CMake", "Makefile": "make", "makefile": "make", "GNUmakefile": "make",
    "meson.build": "Meson", "configure.ac": "autotools", "configure": "autotools", "Cargo.toml": "Cargo (Rust)",
    "SConstruct": "SCons", "premake5.lua": "Premake", "build.gradle": "Gradle", "pom.xml": "Maven",
    "go.mod": "Go modules", "BUILD.bazel": "Bazel", "WORKSPACE": "Bazel", "vcpkg.json": "vcpkg", "conanfile.txt": "Conan",
    "conanfile.py": "Conan", "project.godot": "Godot project", "build.ninja": "Ninja",
}
BUILD_SUFFIXES = {".sln": "Visual Studio (needs a new build)", ".vcxproj": "Visual Studio (needs a new build)",
                  ".xcodeproj": "Xcode (needs a new build)", ".pro": "qmake", ".csproj": "C# project"}

# signal key -> (category, regex, extensions or None for all scanned text)
# category "graphics": api in use; "feature": a capability need; "risk": something that blocks or limits a port.
SIGNALS = {
    "gl_desktop": ("graphics", r"\b(glBegin|glEnd|glMatrixMode|glLoadIdentity|glVertex3f|GL_QUADS|glOrtho|glTexEnvi)\b", None),
    "gl_core": ("graphics", r"\b(glBindVertexArray|glGenVertexArrays|glVertexAttribPointer|glUseProgram|glCreateShader)\b", None),
    "gles": ("graphics", r"(GLES2/gl2|GLES3/gl3|EGL/egl\.h|OpenGL ES|GL_ES|SDL_GL_CONTEXT_PROFILE_ES)", None),
    "gl_4x": ("graphics", r"\b(glDispatchCompute|glMultiDrawElementsIndirect|glBindImageTexture|glTextureStorage2D|glCreateTextures|"
                          r"glNamedBufferStorage|glBindTextures|GL_COMPUTE_SHADER|GL_TESS_CONTROL_SHADER|glDrawElementsIndirect|glShaderStorageBlockBinding)\b", None),
    "gl_5x_dsa": ("graphics", r"\b(glCreateBuffers|glCreateVertexArrays|glNamedBufferData|glClipControl|GL_ARB_bindless_texture|GL_NV_mesh_shader)\b", None),
    "gl_geometry": ("graphics", r"\b(GL_GEOMETRY_SHADER|geometry_shader)\b", None),
    "vulkan": ("graphics", r"(vulkan/vulkan\.h|\bvkCreateInstance\b|\bvkCmdDraw\b|VK_KHR_swapchain|volk\.h)", None),
    "vulkan_rt": ("risk", r"\b(VK_KHR_ray_tracing|VK_KHR_acceleration_structure|vkCmdTraceRaysKHR|VK_EXT_mesh_shader)\b", None),
    "d3d9_11": ("graphics", r"(d3d9\.h|d3d11\.h|ID3D11Device|IDirect3DDevice9|D3D11CreateDevice)", None),
    "d3d12": ("graphics", r"(d3d12\.h|ID3D12Device|D3D12CreateDevice)", None),
    "directdraw": ("graphics", r"(ddraw\.h|IDirectDraw|DirectDrawCreate)", None),
    "metal": ("graphics", r"(<Metal/Metal\.h>|MTLDevice|MTLCreateSystemDefaultDevice)", None),
    "sdl_renderer": ("graphics", r"\b(SDL_CreateRenderer|SDL_RenderCopy|SDL_UpdateTexture)\b", None),
    "software_raster": ("graphics", r"(?i)\b(software[ _]render(er|ing)|framebuffer|put_?pixel|r_softrast)\b", None),
    "sdl2": ("feature", r"(SDL2/SDL\.h|<SDL\.h>|\bSDL_Init\b)", None),
    "sdl3": ("feature", r"(SDL3/SDL\.h|SDL3/SDL_main\.h)", None),
    "glfw": ("feature", r"(GLFW/glfw3\.h|glfwCreateWindow)", None),
    "sfml": ("feature", r"(SFML/Graphics|sf::RenderWindow)", None),
    "qt": ("feature", r"(<QApplication>|QT_VERSION|Q_OBJECT|find_package\(Qt)", None),
    "gtk": ("feature", r"(gtk/gtk\.h|gtk_init)", None),
    "imgui": ("feature", r"(imgui\.h|ImGui::Begin)", None),
    "x11_wayland": ("risk", r"(X11/Xlib\.h|XOpenDisplay|wayland-client\.h)", None),
    "win32_api": ("feature", r"(<windows\.h>|\bCreateWindowExA?W?\b|\bWinMain\b|\bHWND\b)", None),
    "win32_host_needed": ("feature", r"\b(RegOpenKeyEx|CreateFileMapping|CreateProcess|ShellExecute|GetModuleFileName)\b", None),
    "audio_openal": ("feature", r"(AL/al\.h|alcOpenDevice|OpenAL)", None),
    "audio_sdl_mixer": ("feature", r"(SDL_mixer\.h|Mix_OpenAudio)", None),
    "audio_miniaudio": ("feature", r"(miniaudio\.h|ma_engine_init)", None),
    "audio_fmod_wwise": ("risk", r"(fmod\.hpp?|FMOD_System_Create|AK/SoundEngine|AkSoundEngine)", None),
    "threads": ("feature", r"(pthread_create|std::thread|std::async|SDL_CreateThread|thrd_create|_beginthread)", None),
    "network": ("feature", r"(\bsocket\(|getaddrinfo|curl/curl\.h|WSAStartup|enet/enet\.h|asio::)", None),
    "tls": ("feature", r"(openssl/ssl\.h|mbedtls/|SSL_CTX_new|gnutls/)", None),
    "fork_exec": ("risk", r"\b(fork\(\)|execv?p?e?\(|posix_spawn|popen\(|system\()", None),
    "dlopen": ("risk", r"\b(dlopen|LoadLibraryA?W?|g_module_open)\b", None),
    "map_fixed": ("risk", r"(MAP_FIXED|VirtualAlloc\(\s*0x|mremap)", None),
    "jit_exec": ("risk", r"(PROT_EXEC|VirtualProtect\(.*EXECUTE|asmjit|xbyak|AsmJit|dynarec|DynaRec|libjit|lightning\.h|LLVMOrcJIT|sljit)", None),
    "x86_asm": ("risk", r"(__asm__\s*(__volatile__)?\s*\(\s*\"[^\"]*(mov[lq]?|%eax|%rax|xmm)|_mm_\w+|immintrin\.h|emmintrin\.h|xmmintrin\.h|__m128|__m256|\b__asm\s*\{)", None),
    "neon_path": ("feature", r"(arm_neon\.h|__ARM_NEON|vld1q_|sse2neon)", None),
    "arm_asm_ok": ("feature", r"(__aarch64__|__ARM_ARCH)", None),
    "ptr32_assumption": ("risk", r"(\(unsigned int\)\s*\(?\w*ptr|\(DWORD\)\s*\w*ptr|\(int\)\s*&\w+)", None),
    "x87_endian": ("risk", r"(__BYTE_ORDER__\s*==\s*__ORDER_BIG_ENDIAN__|BIG_ENDIAN_ONLY)", None),
    "drm_online": ("risk", r"(?i)(steam_api|SteamAPI_Init|eos_sdk|denuvo|epic online services|battleye|easyanticheat|uplay_r1|origin_sdk)", None),
    "video_codec": ("feature", r"(?i)(bink|libavcodec|libvpx|theora|smacker|ffmpeg)", None),
    "physics_middleware": ("feature", r"(?i)(PxPhysics|PhysX|btDiscreteDynamicsWorld|Havok|hkp[A-Z]\w+|JPH::|Jolt/)", None),
    "script_lua": ("feature", r"(lua\.h|luaL_newstate|LuaJIT)", None),
    "luajit": ("risk", r"(luajit\.h|LuaJIT)", None),
    "mono_clr": ("risk", r"(mono/jit|mono_jit_init|coreclr|hostfxr)", None),
    "python_embed": ("feature", r"(Python\.h|Py_Initialize)", None),
    "exceptions_rtti": ("feature", r"(\btry\s*\{|dynamic_cast<|typeid\()", {".cpp", ".cc", ".cxx", ".hpp"}),
    "audio_sdl": ("feature", r"\b(SDL_OpenAudioDevice|SDL_OpenAudio|SDL_QueueAudio)\b", None),
    "audio_windows": ("feature", r"(XAudio2Create|dsound\.h|DirectSoundCreate|waveOutOpen)", None),
    "input_gamepad": ("feature", r"\b(SDL_GameControllerOpen|SDL_JoystickOpen|XInputGetState|glfwGetGamepadState|IDirectInput8|navigator\.getGamepads)\b", None),
    "input_mouse": ("feature", r"\b(SDL_MOUSEMOTION|SDL_MOUSEWHEEL|WM_MOUSEMOVE|glfwGetCursorPos|GetCursorPos|mousemove)\b", None),
    "input_touch": ("feature", r"\b(SDL_FINGERDOWN|WM_TOUCH|touchstart)\b", None),
    "input_keyboard": ("feature", r"\b(SDL_KEYDOWN|WM_KEYDOWN|glfwGetKey|GetAsyncKeyState|keydown)\b", None),
    "tex_bc": ("feature", r"(GL_COMPRESSED_RGBA?_S3TC|DXGI_FORMAT_BC\d|\bDXT[135]\b)", None),
    "tex_etc2": ("feature", r"(GL_COMPRESSED_RGBA?8?_ETC2|\bETC2\b|ktxTexture)", None),
    "tex_astc": ("feature", r"(GL_COMPRESSED_RGBA_ASTC|\bASTC\b)", None),
    "big_alloc": ("feature", r"(?i)\b(malloc|new\s+\w+\[)\s*\(?\s*\(?\s*(\d+)\s*\*\s*1024\s*\*\s*1024", None),
}

# Regexes counted per site, not per file (thread estimate, memory hints).
THREAD_SITE = re.compile(r"(pthread_create|std::thread\b|std::jthread|std::async|SDL_CreateThread|thrd_create|_beginthread(ex)?|CreateThread\b)")
STATIC_ARRAY = re.compile(r"\b(?:char|int|short|float|double|u?int(?:8|16|32|64)_t|uint8|byte|BYTE)\s+\w+\s*\[\s*(\d+(?:\s*\*\s*\d+)*)\s*\]")
BIG_ALLOC = re.compile(r"\b(?:malloc|calloc|new\s+\w+\s*\[)\s*\(?\s*(\d+(?:\s*\*\s*\d+)+)")
BIG_ELEMENTS = 1 << 20
TEXTURE_EXTS = {".dds": "DDS (BCn)", ".ktx": "KTX", ".ktx2": "KTX2", ".astc": "ASTC", ".png": "PNG", ".tga": "TGA",
                ".pvr": "PVR", ".basis": "Basis", ".jpg": "JPEG", ".jpeg": "JPEG", ".bmp": "BMP"}
AUDIO_KEYS = ("audio_sdl", "audio_sdl_mixer", "audio_openal", "audio_miniaudio", "audio_fmod_wwise", "audio_windows")
INPUT_KEYS = ("input_gamepad", "input_mouse", "input_touch", "input_keyboard")
TEXTURE_KEYS = ("tex_bc", "tex_etc2", "tex_astc")

LICENSE_RULES = [
    ("AGPL", r"GNU AFFERO GENERAL PUBLIC LICENSE"), ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
    ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"), ("LGPL", r"GNU (LESSER|LIBRARY) GENERAL PUBLIC LICENSE"),
    ("MPL-2.0", r"Mozilla Public License"), ("Apache-2.0", r"Apache License\s+Version 2\.0"),
    ("MIT", r"Permission is hereby granted, free of charge"), ("BSD", r"Redistribution and use in source and binary forms"),
    ("zlib", r"This software is provided 'as-is', without any express or implied warranty"),
    ("Unlicense/CC0", r"(This is free and unencumbered software|CC0 1\.0)"),
]
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.txt", "UNLICENSE", "LICENCE")
# (regex over package name, sysroot or kit library). Names come from find_package / pkg_check_modules / link lines.
LIBRARY_MAP = {
    r"(?i)^sdl2?$|^sdl2main$": "sdl2", r"(?i)^sdl2_mixer": "sdl2-mixer", r"(?i)^openal": "openal", r"(?i)^zstd$": "zstd",
    r"(?i)^lz4$": "lz4", r"(?i)^(archive|libarchive)$": "libarchive", r"(?i)^sqlite3?$": "sqlite", r"(?i)^(iconv|libiconv)$": "libiconv",
    r"(?i)^pixman": "pixman", r"(?i)^glib": "glib", r"(?i)^pcre2": "pcre2", r"(?i)^(ffi|libffi)$": "libffi",
    r"(?i)^(zlib|z)$": "zlib", r"(?i)^(png|libpng)$": "libpng", r"(?i)^(jpeg|libjpeg)": "libjpeg",
    r"(?i)^freetype": "freetype", r"(?i)^(ogg|vorbis|vorbisfile)$": "ogg-vorbis", r"(?i)^(opus|opusfile)$": "opus",
    r"(?i)^(curl|libcurl)$": "curl", r"(?i)^(openssl|ssl|crypto)$": "openssl-or-mbedtls", r"(?i)^glm$": "glm (header-only)", r"(?i)^vulkan$|^vulkanheaders$": "vulkan-headers", r"(?i)^volk$": "volk",
    r"(?i)^(vulkanmemoryallocator|vma)$": "vulkan-memory-allocator", r"(?i)^expat$": "expat", r"(?i)^imgui$": "imgui",
}


def load_capabilities():
    return json.loads(CAPABILITIES.read_text(encoding="utf-8"))


def load_source_types():
    return json.loads(SOURCE_TYPES.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- scanning

def walk(root):
    files = []
    for path in root.rglob("*"):
        if len(files) >= FILE_LIMIT:
            break
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]) or not path.is_file():
            continue
        files.append(path)
    return files


def read_text(path):
    try:
        if path.stat().st_size > TEXT_LIMIT:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def is_secondary(rel):
    return any(part.lower() in SECONDARY_DIRS for part in rel.parts[:-1])


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def element_count(expr):
    total = 1
    for number in re.findall(r"\d+", expr):
        total *= int(number)
    return total


def type_regex_rules(types):
    """(type, index, compiled regex) for every regex signal in source_types.json."""
    rules = []
    for name, spec in types["types"].items():
        for index, rule in enumerate(spec.get("signals", [])):
            if rule["kind"] == "regex":
                rules.append((name, index, re.compile(rule["pattern"])))
    rules.append(("heavy", 0, re.compile(types["heavy"]["markers"])))
    return rules


def scan_text(text, rel, suffix, secondary, target, state):
    """Record signals, thread sites, memory hints and type regex hits for one file."""
    for key, (category, pattern, only) in SIGNALS.items():
        if key in target or (only and suffix not in only):
            continue
        # Risks are about code that runs in the port; a PC-side Python installer calling system() is not one.
        if category == "risk" and suffix not in COMPILED_EXTS:
            continue
        match = re.search(pattern, text)
        if match:
            target[key] = f"{rel.as_posix()}:{line_of(text, match.start())}"
    if secondary:
        return
    if suffix in COMPILED_EXTS:
        for match in THREAD_SITE.finditer(text):
            state["threadSites"].append(f"{rel.as_posix()}:{line_of(text, match.start())}")
        for regex, kind in ((STATIC_ARRAY, "static array"), (BIG_ALLOC, "allocation")):
            for match in regex.finditer(text):
                count = element_count(match.group(1))
                if count >= BIG_ELEMENTS:
                    state["memory"].append({"where": f"{rel.as_posix()}:{line_of(text, match.start())}", "kind": kind,
                                            "elements": count})
    for name, index, regex in state["typeRules"]:
        slot = (name, index)
        if slot in state["typeHits"]:
            continue
        match = regex.search(text)
        if match:
            state["typeHits"][slot] = f"{rel.as_posix()}:{line_of(text, match.start())}"


def scan(root, types=None):
    types = types or load_source_types()
    files = walk(root)
    languages, helper_languages, builds, hits, secondary_hits, libs, licenses = Counter(), Counter(), {}, {}, {}, {}, []
    state = {"threadSites": [], "memory": [], "typeRules": type_regex_rules(types), "typeHits": {}}
    scanned = 0
    for path in files:
        suffix = path.suffix.lower()
        rel = path.relative_to(root)
        secondary = is_secondary(rel)
        if suffix in LANGUAGES:
            (helper_languages if secondary else languages)[LANGUAGES[suffix]] += 1
        if path.name in BUILD_FILES:
            builds.setdefault(BUILD_FILES[path.name], rel.as_posix())
        if suffix in BUILD_SUFFIXES:
            builds.setdefault(BUILD_SUFFIXES[suffix], rel.as_posix())
        if path.name in LICENSE_NAMES and len(licenses) < 4:
            licenses.append(path)
        if suffix not in SOURCE_EXTS and path.name not in BUILD_FILES:
            continue
        text = read_text(path)
        if not text:
            continue
        scanned += 1
        scan_text(text, rel, suffix, secondary, secondary_hits if secondary else hits, state)
        if path.name in ("CMakeLists.txt", "vcpkg.json", "conanfile.txt", "meson.build") or suffix == ".cmake":
            for name in re.findall(r"find_package\(\s*([A-Za-z0-9_+.-]+)|pkg_check_modules\([^ )]+\s+(?:REQUIRED\s+)?([A-Za-z0-9_+.-]+)|dependency\(\s*'([A-Za-z0-9_+.-]+)'", text):
                for item in name:
                    in_cmake_dir = rel.parts[0].lower() == "cmake"
                    if item and item.lower() not in BUILD_ONLY_PACKAGES and (not secondary or in_cmake_dir):
                        libs.setdefault(item, rel.as_posix())
    license_ids = []
    for path in licenses:
        head = read_text(path)[:6000]
        found = next((name for name, pattern in LICENSE_RULES if re.search(pattern, head, re.I)), "unknown")
        license_ids.append({"file": path.relative_to(root).as_posix(), "license": found})
    return {"files": len(files), "scanned": scanned, "languages": dict(languages.most_common()),
            "helperLanguages": dict(helper_languages.most_common()), "builds": builds,
            "hits": hits, "secondaryHits": secondary_hits, "libraries": libs, "licenses": license_ids,
            "truncated": len(files) >= FILE_LIMIT, "threadSites": state["threadSites"],
            "memory": sorted(state["memory"], key=lambda m: -m["elements"])[:8], "typeHits": state["typeHits"]}


def data_stats(root, caps, types):
    """Size and shape of everything that is not code: what a package would carry."""
    total_bytes, count, by_ext, textures, paths, truncated = 0, 0, Counter(), Counter(), [], False
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if count >= DATA_WALK_LIMIT:
                truncated = True
                break
            path = Path(folder) / name
            suffix = path.suffix.lower()
            rel = path.relative_to(root).as_posix()
            if len(paths) < FILE_LIMIT:
                paths.append(rel)
            if suffix in SOURCE_EXTS or name in BUILD_FILES:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            count += 1
            total_bytes += size
            by_ext[suffix or "(none)"] += size
            if suffix in TEXTURE_EXTS:
                textures[TEXTURE_EXTS[suffix]] += 1
    limits = caps["limits"]
    warn = types["dataLimits"]
    flags = []
    if total_bytes > min(warn["warnBytes"], limits["packageUnpackedBytesMax"]):
        flags.append(f"data is {total_bytes / 2**30:.2f} GiB; packages hold at most {limits['packageUnpackedBytesMax'] / 2**30:.0f} GiB "
                     "unpacked: ship data separately (user-supplied) or repack it")
    if count > min(warn["warnFiles"], limits["packageFilesMax"]):
        flags.append(f"{count} data files; packages hold at most {limits['packageFilesMax']} files: pack them into archives")
    top = [{"ext": ext, "bytes": size} for ext, size in by_ext.most_common(5)]
    return {"files": count, "bytes": total_bytes, "topExtensions": top, "textures": dict(textures),
            "flags": flags, "truncated": truncated, "paths": paths}


# ---------------------------------------------------------------- classification

def classify(found, data, langs, types):
    """Score every source type from source_types.json; return the winner with its evidence."""
    scores, evidence = {}, {}
    runtime_total = sum(langs.values()) or 1
    for name, spec in types["types"].items():
        score, seen = 0, []
        for index, rule in enumerate(spec.get("signals", [])):
            where = rule_hit(rule, name, index, found, data, langs, runtime_total)
            if where:
                score += rule["weight"]
                seen.append(f"{rule['kind']} {rule.get('key') or rule.get('pattern') or rule.get('name')} "
                            f"({rule['weight']:+d}) at {where}")
        scores[name] = score
        evidence[name] = seen
    best = max(scores, key=lambda n: scores[n])  # dict order breaks ties
    if scores[best] < types["minScore"]:
        # Any compiled or scripted program code counts as software; only data or text stays unknown.
        program = any(lang in LANGUAGES.values() and lang != "HTML" for lang in langs)
        best = types["fallback"]["native" if program else "other"]
        return {"type": best, "score": scores.get(best, 0), "evidence": ["no type reached the minimum score; fallback"],
                "label": types["types"][best]["label"], "scores": scores}
    return {"type": best, "score": scores[best], "evidence": evidence[best], "label": types["types"][best]["label"],
            "scores": scores}


def rule_hit(rule, type_name, index, found, data, langs, runtime_total):
    kind = rule["kind"]
    if kind == "signal":
        return found["hits"].get(rule["key"])
    if kind == "regex":
        return found["typeHits"].get((type_name, index))
    if kind == "path":
        regex = re.compile(rule["pattern"])
        return next((p for p in data["paths"] if regex.search(p)), None)
    if kind == "build":
        return found["builds"].get(rule["name"])
    if kind == "lang":
        return f"{langs[rule['name']]} files" if langs.get(rule["name"], 0) / runtime_total >= 0.25 else None
    return None


def condition_holds(when, hits, builds):
    if not when:
        return True
    kind, _, value = when.partition(":")
    return value in hits if kind == "signal" else value in builds if kind == "build" else False


# ---------------------------------------------------------------- platform matching

def snapshot_apis(caps, include=None):
    """Which platform APIs the SDK snapshot ports build against actually declares."""
    include = include or SNAPSHOT_INCLUDE
    present, missing = [], []
    for api in caps.get("newApis", []):
        header = include / api["header"]
        declared = header.is_file() and api["symbol"] in header.read_text(encoding="utf-8", errors="ignore")
        (present if declared else missing).append(api)
    return {"include": str(include), "present": present, "missing": missing}


def map_libraries(found, caps):
    available = set(caps["libraries"]["released"])
    preview = set(caps["libraries"].get("preview", []))
    result = {"available": {}, "preview": {}, "build_from_source": {}}
    for name, where in found.items():
        mapped = next((lib for pattern, lib in LIBRARY_MAP.items() if re.search(pattern, name)), None)
        base = (mapped or "").split(" ")[0]
        if mapped and base in available:
            result["available"][name] = {"kit": base, "seen": where, "status": "released",
                                         "version": caps["libraries"].get("versions", {}).get(base)}
        elif mapped and base in preview:
            result["preview"][name] = {"kit": base, "seen": where, "status": "private-preview"}
        else:
            result["build_from_source"][name] = {"hint": mapped, "seen": where}
    return result


def graphics_need(hits):
    """Return (api, level, notes). level is the heaviest requirement seen."""
    if "d3d12" in hits or "vulkan_rt" in hits:
        return "d3d12-or-vulkan-rt", 5, ["Ray tracing or D3D12-class features: no evidence on this GPU/driver."]
    if "vulkan" in hits:
        return "vulkan", 4, ["Needs the host Vulkan subset; activation and device evidence are required (see capabilities)."]
    if "gl_5x_dsa" in hits or "gl_4x" in hits:
        return "opengl-4.x", 4, ["GL 4.3 core is the ceiling; check each extension and compute use."]
    if "d3d9_11" in hits:
        return "direct3d-9/11", 4, ["Direct3D needs a translation layer (GL via a wrapper) or a renderer rewrite."]
    if "gl_core" in hits or "gles" in hits:
        return "opengl-3.x/gles", 3, ["GL 3.x core or GLES maps directly onto the windowed SDL2 or nxn_display path."]
    if "gl_desktop" in hits:
        return "opengl-1.x/2.x (fixed function)", 2, ["Fixed-function GL needs a shim (gl4es-class) or a renderer port."]
    if "directdraw" in hits or "sdl_renderer" in hits or "software_raster" in hits:
        return "2d-or-software", 1, ["Software or 2D surfaces: present through dirty rectangles, no GPU risk."]
    if "metal" in hits:
        return "metal", 4, ["Metal has no counterpart; the renderer needs a GL/Vulkan backend."]
    return "unknown", 0, ["No graphics API found in source. If only binaries exist, use `analyze` on the data folder."]


GL_APIS = ("opengl-3.x/gles", "opengl-4.x", "opengl-1.x/2.x (fixed function)")


def run_mode(caps, types, source_type, api, hits, main_lang, vk_ok=True):
    """How the port runs on the OS. Returns {mode, runtime, status, why}."""
    runtimes = caps["runtimes"]
    runtime = types["types"][source_type].get("runtime") or types["runtimeForLanguage"].get(main_lang)
    lang_rule = caps["languages"].get(main_lang or "", {})
    if runtime and runtime in runtimes:
        return {"mode": f"{runtime} runtime (non-native)", "runtime": runtime, "status": runtimes[runtime]["status"],
                "why": runtimes[runtime]["chooseWhen"]}
    if lang_rule.get("status") == "blocked":
        return {"mode": "none until the language blocker is worked around", "runtime": None, "status": "blocked",
                "why": lang_rule["note"]}
    native = runtimes["native"]
    gl = caps["graphics"]["gl"]
    window = "windowed SDL2" if "sdl2" in hits else "nxn_display"
    if api in GL_APIS:
        mode, status, why = f"native, {window} + GL", gl["status"], gl["note"]
    elif api == "2d-or-software":
        mode, status, why = f"native, {window} + CPU surface", caps["graphics"]["present"]["status"], caps["graphics"]["present"]["value"]
    elif api == "vulkan" and vk_ok:
        vk = caps["graphics"]["vulkan"]
        mode, status = f"native, {window} + Vulkan (GL fallback)", vk["status"]
        why = "Vulkan is on by default; check NXN_CAP_VULKAN at start and keep the GL path as the fallback. " + vk["note"]
    elif api in ("vulkan", "direct3d-9/11", "metal", "d3d12-or-vulkan-rt"):
        mode, status = f"native, {window} + GL (renderer port)", gl["status"]
        why = f"{api} is not on the released path; port to GL 4.3/GLES 3.2. " + gl["note"]
    elif source_type in ("tool", "library"):
        mode, status, why = "native, no window needed (console output or library)", native["status"], native["chooseWhen"]
    else:
        mode, status, why = "native; graphics path decided by the first prototype", native["status"], native["chooseWhen"]
    return {"mode": mode, "runtime": "native", "status": status, "why": why}


def pick_template(caps, types, source_type, hits, builds):
    """First released template in the type's preference list whose condition holds; preview ones separately."""
    templates = caps["templates"]
    spec = types["types"][source_type]
    chosen = None
    for option in spec.get("templates", []):
        info = templates.get(option["template"])
        if info and info["status"] == "released" and condition_holds(option.get("when"), hits, builds):
            chosen = {"name": option["template"], "status": info["status"], "use": info["use"], "fits": info["fits"]}
            break
    preview = []
    for option in spec.get("previewTemplates", []):
        info = templates.get(option["template"])
        if info and info["status"] != "released" and condition_holds(option.get("when"), hits, builds):
            preview.append({"name": option["template"], "status": info["status"], "use": info["use"]})
    return chosen, preview


def heavy_check(types, source_type, level, native_files, found):
    rule = types["heavy"]
    reasons = []
    if level >= rule["minTier"]:
        reasons.append(f"performance tier {level} >= {rule['minTier']}")
    if native_files > rule["minNativeFiles"]:
        reasons.append(f"{native_files} native files > {rule['minNativeFiles']}")
    if source_type in rule["types"] and "heavyMarker" in found["hits"]:
        reasons.append(f"heavy application component at {found['hits']['heavyMarker']}")
    return reasons


def os_settings(caps, hits, level, data, heavy, source_type):
    """App and user settings the port should set, each with why and its status."""
    settings = caps["osSettings"]
    picks = [("app.json memory", "always: set it to the measured need")]
    if level >= 3 or data["bytes"] > 64 * 2**20 or heavy:
        picks.append(("app.json loadingHint", "large data or heavy start-up"))
    needs_11 = "exceptions_rtti" in hits or source_type in ("app", "software", "engine")
    if needs_11:
        picks.append(("app.json minNative", "set to 1.1: C++ exceptions/RTTI, own heap, TLS or live resize"))
    if source_type in ("app", "software", "tool", "engine"):
        picks.append(("app.json liveResize", "windowed application: follow window size changes"))
    if "dlopen" in hits:
        picks.append(("native.windowedLibs", f"plugins loaded at run time ({hits['dlopen']})"))
    if "jit_exec" in hits:
        picks.append(("native.windowedJit", f"JIT/dynarec ({hits['jit_exec']})"))
        picks.append(("native.windowedFaultHandler", "fastmem-style JITs recover faults"))
    result = {"released": [], "preview": []}
    for name, why in picks:
        info = settings.get(name)
        if info:
            result["released" if info["status"] == "released" else "preview"].append(
                {"name": name, "why": why, "use": info["use"], "status": info["status"]})
    if heavy:
        for name, info in settings.items():
            if info["status"] != "released":
                result["preview"].append({"name": name, "why": "heavy source: memory headroom", "use": info["use"],
                                          "status": info["status"]})
    return result


def os_apis(caps, hits, heavy, thread_sites, api):
    """Platform APIs worth using, split into released and preview."""
    wanted = {"nxn_capability_query": "check JIT/GL/TLS support at start"}
    if "jit_exec" in hits:
        wanted["nxn_jit_create"] = "W^X code buffers for the JIT"
        wanted["nxn_fault_handler_set"] = "recover data aborts in JIT code"
    if api == "vulkan":
        wanted["nxn_vk_proc"] = "optional Vulkan path next to GL"
    if heavy:
        wanted["nxn_memory_budget_get"] = "check free memory before big loads"
    if len(thread_sites) > caps["limits"]["workerCores"]:
        wanted["nxn_thread_hint_request"] = f"{len(thread_sites)} thread-creation sites"
    result = {"released": [], "preview": []}
    for entry in caps["newApis"]:
        if entry["symbol"] in wanted:
            result["released" if entry["status"] == "released" else "preview"].append(
                {"symbol": entry["symbol"], "header": entry["header"], "why": wanted[entry["symbol"]],
                 "status": entry["status"], "evidence": entry["evidence"]})
    return result


def pick_profile(types, source_type, heavy, genre):
    """Experience profile name: heavy wins, then the scanned genre for games, then the type default."""
    if heavy:
        name = types["heavy"]["profile"]
    elif source_type == "game" and genre and genre != "generic":
        name = genre
    else:
        name = types["types"][source_type]["profile"]
    exists = (PROFILES / f"{name}.json").is_file()
    return {"name": name, "exists": exists,
            "note": "" if exists else f"profiles/{name}.json is missing; run the tests"}


def reference_port(caps, source_type, api):
    refs = caps["referencePorts"]
    key = source_type if source_type in refs else api
    return {"key": key, "port": refs[key]} if key in refs else None


# ---------------------------------------------------------------- blockers, work and plan

def ways_around(types, blocker_id):
    table = types["workarounds"]
    return table.get(blocker_id) or table["default"]


def work_list(types, found, api, level, libraries, blocker_ids, limits, hits, data):
    effort = types["effort"]
    items = []

    def add(task, difficulty, status="released"):
        items.append({"task": task, "difficulty": difficulty, "duration": effort[difficulty], "status": status})

    add("Build system for devkitA64 (" + (", ".join(found["builds"]) or "none found: write one") + ")",
        "easy" if "CMake" in found["builds"] else "medium")
    gfx = {0: "medium", 1: "easy", 2: "medium", 3: "easy", 4: "hard", 5: "hard"}[min(level, 5)]
    add(f"Graphics path from {api}", gfx)
    for name in libraries["build_from_source"]:
        add(f"Build library {name} for AArch64", "medium")
    for name, info in libraries["preview"].items():
        add(f"Library {name} ({info['kit']}) is preview only: keep it off the production path", "medium", info["status"])
    if "audio_fmod_wwise" in hits:
        add("Replace FMOD/Wwise with SDL2 audio, OpenAL Soft or miniaudio", "medium")
    if "input_gamepad" not in hits:
        add("Map controller and touch to the program's keyboard/mouse input", "easy")
    for blocker in blocker_ids:
        add(f"Work around blocker {blocker}", "hard")
    for limit in limits:
        add(f"Limit: {limit.split(':')[0]}", "medium")
    if data["flags"]:
        add("Repack or split the data to fit package limits", "medium")
    return items


def staged_plan(types):
    return [dict(stage) for stage in types["stagedPlan"]]


# ---------------------------------------------------------------- report

def merge_binary_hits(found, binary):
    hits = dict(found["hits"])
    for signal, where in binary["signalEvidence"].items():
        key = {"graphics:direct3d": "d3d9_11", "graphics:directdraw": "directdraw", "graphics:opengl": "gl_desktop",
               "graphics:vulkan": "vulkan"}.get(signal)
        if key:
            hits.setdefault(key, where)
    return hits


def detections(found, hits, data, caps):
    """Grouped findings with file:line evidence."""
    sites = found["threadSites"]
    return {
        "audio": {k: hits[k] for k in AUDIO_KEYS if k in hits},
        "input": {k: hits[k] for k in INPUT_KEYS if k in hits},
        "network": {k: hits[k] for k in ("network", "tls") if k in hits},
        "drm": hits.get("drm_online"),
        "threads": {"sites": len(sites), "evidence": sites[:8],
                    "note": f"about {len(sites)} creation sites for {caps['limits']['workerCores']} worker cores (1-2) beside the main thread" if sites else "none found"},
        "memory": found["memory"],
        "textures": {"files": data["textures"], "code": {k: hits[k] for k in TEXTURE_KEYS if k in hits},
                     "platform": caps["graphics"]["textures"]["value"]},
        "data": {k: data[k] for k in ("files", "bytes", "topExtensions", "flags", "truncated")},
    }


def os_tuple(text):
    """'1.3.28-beta.2' -> (1, 3, 28); missing parts count as 0."""
    numbers = [int(n) for n in re.findall(r"\d+", str(text or "").split("-")[0])[:3]]
    return tuple(numbers + [0] * (3 - len(numbers)))


def snapshot_os():
    """OS version of the locked SDK snapshot: the default target OS."""
    version = SNAPSHOT_INCLUDE.parents[6] / "VERSION.json"
    return json.loads(version.read_text(encoding="utf-8")).get("os") if version.is_file() else None


def vulkan_on_os(caps, target_os):
    """Vulkan is released (owner decision) from graphics.vulkan.minOs on; older OS builds have no Vulkan."""
    vk = caps["graphics"]["vulkan"]
    need = vk.get("minOs")
    ok = vk["status"] == "released" and (not need or (target_os is not None and os_tuple(target_os) >= os_tuple(need)))
    note = None if ok else (f"Vulkan is not in OS {target_os or 'unknown'} (needs {need}); use the GL path." if need
                            else "Vulkan is not released; use the GL path.")
    return {"available": ok, "minOs": need, "targetOs": target_os, "note": note}


def build_report(root, name, target_os=None):
    caps = load_capabilities()
    vulkan = vulkan_on_os(caps, target_os or snapshot_os())
    types = load_source_types()
    found = scan(root, types)
    data = data_stats(root, caps, types)
    binary = analyze.analyze(root)
    hits = merge_binary_hits(found, binary)
    heavy_marker = re.compile(types["heavy"]["markers"])
    found["hits"] = hits
    langs = found["languages"]
    if ("heavy", 0) in found["typeHits"]:
        hits["heavyMarker"] = found["typeHits"][("heavy", 0)]
    for item, where in found["libraries"].items():
        if heavy_marker.search(item):
            hits.setdefault("heavyMarker", where)
    native_files = sum(count for lang, count in langs.items() if lang in NATIVE_LANGS)
    api, level, graphic_notes = graphics_need(hits)
    blockers, blocker_ids, limits, unknown, uses = [], [], [], [], []

    def block(blocker_id, text):
        blockers.append(text)
        blocker_ids.append(blocker_id)

    has_source = bool(langs)
    if not has_source:
        unknown.append("No source files found. Without source, the route is static recompilation or a compatible engine; "
                       "see the playbook table and record redistribution rights.")
    main_lang = max(langs, key=langs.get) if langs else None
    runtime_files = sum(langs.values()) or 1
    for lang, rule in caps["languages"].items():
        if lang not in langs or rule["status"] == "native":
            continue
        # A language with a small share next to native code is usually build or editor scripting, not the runtime.
        if lang == main_lang or langs[lang] / runtime_files >= 0.25:
            text = f"{lang}: {rule['note']} ({rule['source']})"
            if rule["status"] == "blocked":
                block(f"language:{lang}", text)
            else:
                limits.append(text)
        else:
            unknown.append(f"{lang} ({langs[lang]} files) beside the main code: confirm it is not needed at run time; if it is: {rule['note']}")
    if main_lang and main_lang not in NATIVE_LANGS and main_lang in caps["languages"] and caps["languages"][main_lang]["status"] == "native":
        uses.append(f"{main_lang}: {caps['languages'][main_lang]['note']}")
    for key, (category, _, _) in SIGNALS.items():
        if category != "risk" or key not in hits:
            continue
        rule = caps["risks"].get(key)
        if rule:
            text = f"{rule['title']}: {rule['note']} (seen in {hits[key]})"
            if rule["severity"] == "blocker":
                block(key, text)
            else:
                limits.append(text)
    if "x86_asm" in hits and ("neon_path" in hits or "arm_asm_ok" in hits):
        limits = [item for item in limits if not item.startswith(caps["risks"]["x86_asm"]["title"])]
        limits.append("x86 intrinsics present but an ARM path also exists: build with the ARM path or `sse2neon`.")
    if "jit_exec" in hits:
        lim = caps["limits"]
        uses.append(f"JIT: code memory is capped ({lim['codeMemoryObjectsSystemWide']} objects system-wide, "
                    f"{lim['codeMemoryPerModule']} per module); budget it with the code-memory API.")
    if "fork_exec" in hits:
        uses.append("Replace child processes with functions or threads (one window, one process).")
    if "sdl3" in hits:
        limits.append("SDL3 found: the kit ships SDL " + caps["libraries"]["versions"]["sdl2"] + " only; use an SDL2 branch or an SDL3-to-SDL2 shim.")

    if level >= 5 and "vulkan_rt" not in blocker_ids:
        # Not proven impossible: a limit to try with a prototype, not a blocker (performance tier 5).
        limits.append(graphic_notes[0] + " " + caps["performance"]["tiers"]["5"]["expectation"])
    if "tls" in hits or "network" in hits:
        unknown.append("Network/TLS: verify the OS network API and certificate store with a small prototype.")
    if "drm_online" in hits:
        limits.append(f"Online services or DRM: they cannot be redistributed or replaced by this port; preserve checks and document the impact (seen in {hits['drm_online']}).")
    if "win32_api" in hits and not found["builds"].get("CMake") and "sdl2" not in hits:
        limits.append("Win32-only code: needs a host layer (see docs/PORTING_LARGE_GAMES.md) or a cross-platform branch.")
    limits += [f"Data size: {flag}" for flag in data["flags"]]

    lic = found["licenses"]
    license_names = {item["license"] for item in lic}
    if not lic:
        unknown.append("No licence file: redistribution rights unknown. Treat as personal-package-only until a licence is found.")
    elif license_names & {"GPL-2.0", "GPL-3.0", "AGPL"}:
        uses.append("Copyleft licence: the package ships the source link and licence text; host-layer code is published with it.")
    if "unknown" in license_names:
        unknown.append("Licence text not recognised: read it and record the redistribution terms in PORT.md.")
    libraries = map_libraries(found["libraries"], caps)
    if libraries["build_from_source"]:
        unknown.append("Libraries not in the kit sysroot: " + ", ".join(sorted(libraries["build_from_source"])) +
                       ". Each needs an AArch64 build (devkitPro portlib or a sysroot recipe).")

    sdk = snapshot_apis(caps)
    missing = {entry["symbol"] for entry in sdk["missing"]}
    if api == "vulkan" and not vulkan["available"]:
        limits.append(vulkan["note"])
    if api == "vulkan" and "nxn_vk_proc" in missing:
        limits.append("Vulkan headers (nxn_vk.h) are not in the active SDK snapshot: run `port_studio.py sdk-update` (SDK 1.16 or later); "
                      "until then resolve Vulkan entry points by weak import, and keep the GL fallback.")
    if "jit_exec" in hits and "nxn_jit_create" in missing:
        limits.append("nxn_jit.h is not in the Studio SDK snapshot: take an SDK update before planning a JIT.")

    verdict = "blocked" if blockers else ("limited" if limits or level >= 4 else "viable")
    known_langs = [lang for lang in langs if lang in caps["languages"]]
    if not blockers and level == 0 and not known_langs and not binary["engines"]:
        verdict = "unknown"  # nothing in a language the platform rules know: the program's own code is not here

    source_type = classify(found, data, langs, types)
    stype = source_type["type"]
    heavy_reasons = heavy_check(types, stype, level, native_files, found)
    heavy = bool(heavy_reasons)
    template, preview_templates = pick_template(caps, types, stype, hits, found["builds"])
    mode = run_mode(caps, types, stype, api, hits, main_lang, vulkan["available"])
    profile = pick_profile(types, stype, heavy, binary.get("genreGuess", {}).get("profile"))
    perf = performance(caps, level, hits, native_files, profile)
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "name": name or root.name, "date": date.today().isoformat(), "path": str(root),
        "capabilitiesAsOf": caps["asOf"], "capabilitiesSource": caps["source"],
        "verdict": verdict,
        "verdictBasis": "viable = no blocker or limit found by the scan; limited = works with named work or reduced scope; "
                        "blocked = a hard blocker today, with ways around listed; unknown = nothing readable. A scan is not a prototype.",
        "sourceType": source_type,
        "heavy": {"heavy": heavy, "reasons": heavy_reasons},
        "scan": {k: found[k] for k in ("files", "scanned", "truncated", "languages", "builds", "licenses")},
        "license": sorted(license_names) or ["unknown"],
        "engines": binary["engines"], "binarySignals": binary["signals"],
        "graphics": {"api": api, "level": level, "notes": graphic_notes},
        "runMode": mode,
        "template": template,
        "route": route(caps, api, hits, found["builds"], vulkan),
        "vulkan": vulkan,
        "blockers": blockers, "limits": limits, "use": uses, "unknown": unknown,
        "blockerDetails": [{"id": bid, "reason": text, "waysAround": ways_around(types, bid)} for bid, text in zip(blocker_ids, blockers)],
        "sdkSnapshot": {"present": [a["symbol"] for a in sdk["present"]], "missing": [a["symbol"] for a in sdk["missing"]]},
        "libraries": libraries,
        "osSettings": os_settings(caps, hits, level, data, heavy, stype),
        "osApis": os_apis(caps, hits, heavy, found["threadSites"], api),
        "detections": detections(found, hits, data, caps),
        "signals": {k: v for k, v in hits.items() if k != "heavyMarker"}, "toolingSignals": found["secondaryHits"],
        "helperLanguages": found["helperLanguages"],
        "performance": perf,
        "referencePort": reference_port(caps, stype, api),
        "workList": work_list(types, found, api, level, libraries, blocker_ids, limits, hits, data),
        "stagedPlan": staged_plan(types) if heavy or native_files > types["heavy"]["minNativeFiles"] else [],
        "nextSteps": next_steps(verdict, api, bool(lic), has_source),
    }
    report["previewOptions"] = preview_options(caps, report, preview_templates)
    return report


def preview_options(caps, report, preview_templates):
    """Everything not released that could help, kept apart from the production route."""
    options = []
    vk = caps["graphics"]["vulkan"]
    if vk["status"] != "released" and report["graphics"]["api"] in ("vulkan", "opengl-4.x", "d3d12-or-vulkan-rt", "direct3d-9/11"):
        options.append({"item": "Vulkan path (bonus next to GL)", "status": vk["status"], "evidence": vk["evidence"], "note": vk["note"]})
    for template in preview_templates:
        options.append({"item": f"template {template['name']}", "status": template["status"], "note": template["use"]})
    for name, info in report["libraries"]["preview"].items():
        options.append({"item": f"library {info['kit']} (for {name})", "status": info["status"], "note": "not in a public release"})
    for entry in report["osApis"]["preview"]:
        options.append({"item": f"API {entry['symbol']}", "status": entry["status"], "evidence": entry["evidence"], "note": entry["why"]})
    for entry in report["osSettings"]["preview"]:
        options.append({"item": f"setting {entry['name']}", "status": entry["status"], "note": entry["use"]})
    if report["graphics"]["api"] == "opengl-4.x":
        for tool in caps["tools"]["nxv_native"].get("preview", []):
            if tool == "shader":
                options.append({"item": "nxv_native shader (offline shader check)", "status": "private-preview", "note": "preview tool"})
    nexgfx = caps["graphics"]["nexgfx"]
    if report["graphics"]["level"] >= 3 and (report["detections"]["textures"]["files"].get("DDS (BCn)") or "tex_bc" in report["signals"]):
        # NexGFX is released; it is listed as an option because baked scenes replace the engine's own renderer.
        options.append({"item": "NexGFX baked scenes (option, not a drop-in)", "status": nexgfx["status"],
                        "evidence": nexgfx["evidence"], "note": nexgfx["note"]})
    return options


def route(caps, api, hits, builds, vulkan=None):
    gfx = caps["graphics"]
    if api in GL_APIS:
        window = "SDL2 windowed (kit sdl2-nexvyn) with SDL_GL_CreateContext" if "sdl2" in hits else "nxn_display_* directly"
        steps = [f"Window and GL context: {window}.", gfx["gl"]["note"]]
        if api.startswith("opengl-1"):
            steps.append("Fixed-function calls: add a shim or port the renderer; do not expect them to run unchanged.")
        if api == "opengl-4.x":
            steps.append("Validate shaders offline: `python tools/nxv_native shader <file> --target gl` in the SDK.")
        return steps
    if api == "vulkan":
        if vulkan is None or vulkan["available"]:
            return ["Keep the Vulkan renderer: check NXN_CAP_VULKAN (nxn_caps_has_gfx_api) at start. " + gfx["vulkan"]["note"],
                    "Keep a GL 4.3/GLES 3.2 fallback for hosts where the driver check fails or native.vulkanOff=1."]
        if vulkan and vulkan.get("minOs") and gfx["vulkan"]["status"] == "released":
            return ["Production path on this OS: port the renderer to GL 4.3/GLES 3.2 (released). " + vulkan["note"],
                    f"Keep the Vulkan renderer behind NXN_CAP_VULKAN for OS {vulkan['minOs']} and later."]
        return ["Production path: port the renderer to GL 4.3/GLES 3.2 (released).",
                "Vulkan stays a preview bonus: " + gfx["vulkan"]["note"]]
    if api == "2d-or-software":
        return ["Draw into a CPU surface and present with dirty rectangles (docs/PORTING_LARGE_GAMES.md section 4)."]
    if api.startswith("direct3d"):
        return ["Translate D3D to GL (wrapper) or port the renderer to GL 3.x/GLES; record the choice and a measured prototype in PORT.md."]
    return ["Choose the route after the first prototype; record it in PORT.md."]


def performance(caps, level, hits, native_files, profile):
    tiers = caps["performance"]["tiers"]
    tier = tiers[str(min(level, 5))]
    notes = list(caps["performance"]["rules"])
    if "threads" in hits:
        notes.append(caps["performance"]["threadRule"])
    if "jit_exec" in hits:
        notes.append(caps["performance"]["jitRule"])
    if "big_alloc" in hits:
        notes.append("Large fixed allocations found: set `memory` in app.json and check allocation results.")
    if native_files > 2000:
        notes.append("Large code base: first build and link time on the host will be long; keep sdk.lock.json and the toolchain fixed.")
    return {"tier": min(level, 5), "profile": profile["name"], "profileExists": profile["exists"], "profileNote": profile["note"],
            "expectation": tier["expectation"], "start": tier["start"], "confidence": "estimate, no device measurement",
            "evidenceLevel": tier["evidence"], "recommendations": notes, "references": caps["performance"]["references"]}


def next_steps(verdict, api, has_license, has_source):
    steps = []
    if verdict == "blocked":
        steps.append("Record the blocker evidence in PORT.md; test the narrowest way around (listed per blocker) with a native prototype.")
    if not has_license:
        steps.append("Find the licence and redistribution terms before packaging anything.")
    steps.append("`init game|software <slug> <category>` and paste this report into PORT.md under Research and feasibility.")
    steps.append("Build a one-scene prototype (window, graphics context, one frame) on the locked SDK before the full port.")
    steps.append("Declare controls with `experience init <port> <profile>`, then measure handheld and docked in the emulator.")
    return steps


# ---------------------------------------------------------------- rendering

def bullets(items, empty="- none found by the scan"):
    return [f"- {item}" for item in items] or [empty]


def human_bytes(count):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if count < 1024 or unit == "GiB":
            return f"{count:.0f} {unit}" if unit == "B" else f"{count:.1f} {unit}"
        count /= 1024
    return str(count)


def render_found(report):
    scan_info = report["scan"]
    langs = ", ".join(f"{k} {v}" for k, v in scan_info["languages"].items()) or "none"
    st = report["sourceType"]
    lines = ["## What was found",
             f"- Source type: **{st['type']}** ({st['label']}, score {st['score']})" + ("; heavy: " + "; ".join(report["heavy"]["reasons"]) if report["heavy"]["heavy"] else ""),
             *[f"  - {item}" for item in st["evidence"][:6]],
             f"- Files read: {scan_info['scanned']} of {scan_info['files']}" + (" (scan limit hit)" if scan_info["truncated"] else ""),
             f"- Languages (file count): {langs}",
             f"- In tools/tests/vendored folders (not counted as runtime): "
             f"{', '.join(f'{k} {v}' for k, v in report['helperLanguages'].items()) or 'none'}",
             f"- Build systems: {', '.join(f'{k} ({v})' for k, v in scan_info['builds'].items()) or 'none found'}",
             f"- Licence: {', '.join(report['license'])}" + (" (" + ", ".join(i["file"] for i in scan_info["licenses"]) + ")" if scan_info["licenses"] else ""),
             f"- Engines: {', '.join(f'{k} ({v})' for k, v in report['engines'].items()) or 'none recognised'}",
             f"- Graphics: **{report['graphics']['api']}**; " + " ".join(report["graphics"]["notes"])]
    det = report["detections"]
    group = lambda d: ", ".join(f"{k} ({v})" for k, v in d.items()) or "none found"
    lines += [f"- Audio: {group(det['audio'])}", f"- Input: {group(det['input'])}", f"- Network: {group(det['network'])}",
              f"- DRM/online: {det['drm'] or 'none found'}",
              f"- Threads: {det['threads']['note']}" + (" (" + ", ".join(det["threads"]["evidence"][:4]) + ")" if det["threads"]["evidence"] else ""),
              "- Memory hints: " + (", ".join(f"{m['kind']} {m['elements']} elements at {m['where']}" for m in det["memory"][:4]) or "none found"),
              "- Textures: files " + (", ".join(f"{k} {v}" for k, v in det["textures"]["files"].items()) or "none") +
              "; code " + group(det["textures"]["code"]) + f"; platform: {det['textures']['platform']}"]
    data = det["data"]
    lines.append(f"- Data: {data['files']} files, {human_bytes(data['bytes'])}; top: " +
                 (", ".join(f"{e['ext']} {human_bytes(e['bytes'])}" for e in data["topExtensions"]) or "none"))
    return lines + [""]


def render_recommendation(report):
    mode, tpl, perf = report["runMode"], report["template"], report["performance"]
    lines = ["## Recommended route (released only)",
             f"- Run mode: **{mode['mode']}** [{mode['status']}]: {mode['why']}",
             f"- Template: " + (f"**{tpl['name']}** [{tpl['status']}]: {tpl['use']}" if tpl else "none fits; start from the run mode above"),
             f"- Profile: **{perf['profile']}**" + (f" ({perf['profileNote']})" if perf["profileNote"] else "")]
    ref = report["referencePort"]
    if ref:
        lines.append(f"- Reference port: {ref['port']}")
    lines += [f"- {item}" for item in report["route"]]
    lines += ["", "## OS settings to set"]
    lines += bullets([f"`{s['name']}` [{s['status']}]: {s['why']} ({s['use']})" for s in report["osSettings"]["released"]], "- none")
    lines += ["", "## OS APIs to use"]
    lines += bullets([f"`{a['symbol']}` ({a['header']}) [{a['status']}, {a['evidence']}]: {a['why']}" for a in report["osApis"]["released"]], "- none")
    return lines + [""]


def render_blockers(report):
    lines = ["## Blockers (not a final no)"]
    if not report["blockerDetails"]:
        return lines + ["- none found by the scan", ""]
    for item in report["blockerDetails"]:
        lines.append(f"- {item['reason']}")
        lines += [f"  - way around: {way}" for way in item["waysAround"]]
    return lines + [""]


def render_work(report):
    lines = ["## Work list (rough estimate)", "| Task | Difficulty | Duration | Status |", "| --- | --- | --- | --- |"]
    lines += [f"| {w['task']} | {w['difficulty']} | {w['duration']} | {w['status']} |" for w in report["workList"]]
    if report["stagedPlan"]:
        lines += ["", "## Staged port plan", "| Stage | Acceptance | Duration | Risk |", "| --- | --- | --- | --- |"]
        lines += [f"| {s['stage']} | {s['acceptance']} | {s['duration']} | {s['risk']} |" for s in report["stagedPlan"]]
    return lines + [""]


def render(report):
    lines = [f"# Port assessment: {report['name']}", "",
             f"Date {report['date']} · platform facts as of {report['capabilitiesAsOf']} ({report['capabilitiesSource']})", "",
             f"**Verdict: {report['verdict'].upper()}**  ", f"_{report['verdictBasis']}_", ""]
    lines += render_found(report)
    lines += render_blockers(report)
    for title, key in (("Limits and work needed", "limits"), ("Plan around", "use"), ("Unknown, prototype first", "unknown")):
        lines += [f"## {title}", *bullets(report[key]), ""]
    lines += render_recommendation(report)
    libs = report["libraries"]
    lines += ["## Libraries",
              "- Ready in the kit [released]: " + (", ".join(f"{n} -> {v['kit']}" for n, v in libs["available"].items()) or "none matched"),
              "- To build from source: " + (", ".join(libs["build_from_source"]) or "none"), "",
              "## Platform APIs in the Studio SDK snapshot",
              "- Declared: " + (", ".join(report["sdkSnapshot"]["present"]) or "none"),
              "- Not in the public snapshot yet (private-preview, wait for the next public SDK): " + (", ".join(report["sdkSnapshot"]["missing"]) or "none"), ""]
    lines += ["## Preview options (never the production path)"]
    lines += bullets([f"{o['item']} [{o['status']}]: {o['note']}" for o in report["previewOptions"]], "- none")
    lines.append("")
    perf = report["performance"]
    lines += ["## Performance (" + perf["confidence"] + ")", f"- Tier {perf['tier']}: {perf['expectation']}", f"- Start with: {perf['start']}",
              f"- Evidence level behind this tier: {perf['evidenceLevel']}"]
    lines += [f"- {item}" for item in perf["recommendations"]]
    lines += ["- Recorded references: " + "; ".join(perf["references"]), ""]
    lines += render_work(report)
    lines += ["## Next steps"] + [f"{i}. {item}" for i, item in enumerate(report["nextSteps"], 1)]
    if report["toolingSignals"]:
        lines += ["", "## Seen only in tools/tests/vendored code (check they stay off the runtime path)",
                  ", ".join(f"{k} ({v})" for k, v in report["toolingSignals"].items())]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- batch

BATCH_COLUMNS = ("name", "type", "verdict", "api", "tier", "template")


def batch_row(report):
    return {"name": report["name"], "type": report["sourceType"]["type"], "verdict": report["verdict"],
            "api": report["graphics"]["api"], "tier": report["performance"]["tier"],
            "template": report["template"]["name"] if report["template"] else "-"}


def batch(folder):
    return [batch_row(build_report(sub, None)) for sub in sorted(folder.iterdir()) if sub.is_dir() and sub.name not in SKIP_DIRS]


def render_batch(rows):
    lines = ["| " + " | ".join(BATCH_COLUMNS) + " |", "| " + " | ".join("---" for _ in BATCH_COLUMNS) + " |"]
    lines += ["| " + " | ".join(str(row[c]) for c in BATCH_COLUMNS) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--batch", action="store_true", help="Assess each subfolder and print a comparison table.")
    parser.add_argument("--out", type=Path, help="Write the Markdown report to this file.")
    parser.add_argument("--os", dest="target_os", help="Target OS version (default: the locked SDK snapshot's OS).")
    args = parser.parse_args(argv)
    if not args.path.is_dir():
        print(f"Error: {args.path} is not a directory.", file=sys.stderr)
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.batch:
        rows = batch(args.path)
        text = json.dumps({"schemaVersion": SCHEMA_VERSION, "rows": rows}, indent=2) if args.json else render_batch(rows)
    else:
        report = build_report(args.path, args.name, args.target_os)
        text = json.dumps(report, indent=2) if args.json else render(report)
    if args.out:
        args.out.write_text(text if args.batch else render(report), encoding="utf-8")
        print(f"Report written: {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
