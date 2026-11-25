"""Tests for the port feasibility report (assess.py)."""

import json
import re
import tempfile
import unittest
from pathlib import Path

import assess

FIXTURES = Path(assess.__file__).resolve().parent / "fixtures" / "assess"
# name -> (type, verdict, api, template, tier); synthetic sources under tools/fixtures/assess.
EXPECTED = {
    "sdl2_game": ("game", "viable", "2d-or-software", "sdl2", 1),
    "gl_game": ("game", "viable", "opengl-3.x/gles", "port", 3),
    "vulkan_game": ("game", "limited", "vulkan", "port", 4),
    "d3d_game": ("game", "limited", "direct3d-9/11", "game", 4),
    "rust_python": ("software", "limited", "unknown", "app", 0),
    "soft2d": ("game", "viable", "2d-or-software", "game", 1),
    "emulator_dynarec": ("emulator", "limited", "2d-or-software", "emu-skeleton", 1),
    "decomp_project": ("decomp", "limited", "2d-or-software", "decomp-skeleton", 1),
}


def make(root, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class AssessTest(unittest.TestCase):
    def report(self, files):
        with tempfile.TemporaryDirectory() as root:
            make(root, files)
            return assess.build_report(Path(root), "t")

    def test_capabilities_file_is_complete(self):
        caps = assess.load_capabilities()
        for key in ("asOf", "source", "languages", "risks", "graphics", "libraries", "performance"):
            self.assertIn(key, caps)
        for level in "012345":
            self.assertIn(level, caps["performance"]["tiers"])
        for key, (category, _, _) in assess.SIGNALS.items():
            if category == "risk":
                self.assertIn(key, caps["risks"], f"risk signal {key} has no capability rule")

    def test_every_fact_has_status_and_evidence(self):
        caps = assess.load_capabilities()
        allowed = set(caps["statusLevels"])
        facts = list(caps["platform"].values()) + [v for v in caps["graphics"].values() if isinstance(v, dict)] + caps["newApis"]
        for fact in facts:
            self.assertIn(fact.get("status"), allowed, fact)
            self.assertTrue(fact.get("evidence"), fact)
        self.assertFalse(set(caps["libraries"]["released"]) & set(caps["libraries"]["preview"]))

    def test_public_files_carry_no_private_markers(self):
        # The Studio repository is public; the OS source repository is private.
        studio = Path(assess.__file__).resolve().parents[1]
        files = [studio / "platform" / "capabilities.json", studio / "platform" / "source_types.json",studio / "docs" / "PORT_ASSESSMENT.md", studio / "tools" / "assess.py"]
        from test_public_hygiene import private_pattern  # names come from the git-ignored local marker file
        pattern = private_pattern()
        for path in files:
            self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path)

    def test_sdl_gl_game_is_viable(self):
        report = self.report({
            "CMakeLists.txt": "find_package(SDL2 REQUIRED)\nfind_package(zstd)\n",
            "main.c": "#include <SDL2/SDL.h>\nvoid f(){ glUseProgram(1); glBindVertexArray(0); }\n",
            "LICENSE": "Permission is hereby granted, free of charge, to any person",
        })
        self.assertEqual(report["verdict"], "viable")
        self.assertEqual(report["graphics"]["api"], "opengl-3.x/gles")
        self.assertIn("SDL2", report["libraries"]["available"])
        self.assertEqual(report["scan"]["licenses"][0]["license"], "MIT")

    def test_vulkan_raytracing_blocks(self):
        report = self.report({"r.cpp": "#include <vulkan/vulkan.h>\nvoid f(){ vkCmdTraceRaysKHR(); }\n"})
        self.assertEqual(report["verdict"], "blocked")

    def test_x86_only_asm_limits_but_arm_path_clears_it(self):
        only_x86 = self.report({"a.c": "#include <immintrin.h>\nvoid f(){ _mm_add_ps(a,b); }\n"})
        self.assertIn("x86_asm", only_x86["signals"])
        self.assertTrue(any("x86" in item.lower() for item in only_x86["blockers"] + only_x86["limits"]))
        with_arm = self.report({"a.c": "#include <immintrin.h>\n#ifdef __ARM_NEON\n#include <arm_neon.h>\n#endif\nvoid f(){ _mm_add_ps(a,b); }\n"})
        self.assertTrue(any("ARM path" in item for item in with_arm["limits"]))

    def test_csharp_unity_is_not_viable(self):
        report = self.report({"Game.cs": "class A {}\n"})
        self.assertNotEqual(report["verdict"], "viable")

    def test_tool_scripts_and_build_packages_do_not_limit(self):
        report = self.report({
            "CMakeLists.txt": "find_package(SDL2)\nfind_package(Git)\nfind_package(Threads)\nfind_package(Python3)\n",
            "src/main.c": "#include <SDL2/SDL.h>\nvoid f(){ glUseProgram(1); }\n",
            "src/b.c": "int b;\n", "src/c.c": "int c;\n",
            "tools/gen.c": "void g(void){ fork(); }\n", "tools/x.py": "", "tools/y.py": "", "tools/z.py": "", "tools/w.py": "",
            "notes.txt": "fork() later",
            "LICENSE": "Permission is hereby granted, free of charge, to any person",
        })
        self.assertEqual(report["verdict"], "viable", report["limits"])
        self.assertNotIn("fork_exec", report["signals"])
        self.assertIn("fork_exec", report["toolingSignals"])
        self.assertEqual(report["libraries"]["build_from_source"], {})

    def test_empty_folder_is_unknown(self):
        self.assertEqual(self.report({"readme.txt": "hello"})["verdict"], "unknown")

    def test_missing_licence_is_reported_unknown(self):
        report = self.report({"m.c": "int main(void){return 0;}\n"})
        self.assertTrue(any("licence" in item.lower() for item in report["unknown"]))

    def test_render_and_json_roundtrip(self):
        report = self.report({"m.c": "#include <SDL2/SDL.h>\nint main(void){return 0;}\n"})
        text = assess.render(report)
        self.assertIn("**Verdict:", text)
        self.assertIn("estimate", text)
        json.dumps(report)

    def test_fixtures_type_verdict_api_template_tier(self):
        for name, expected in EXPECTED.items():
            with self.subTest(name=name):
                row = assess.batch_row(assess.build_report(FIXTURES / name, None))
                self.assertEqual((row["type"], row["verdict"], row["api"], row["template"], row["tier"]), expected)

    def test_batch_lists_every_fixture(self):
        rows = assess.batch(FIXTURES)
        self.assertEqual(sorted(r["name"] for r in rows), sorted(EXPECTED))
        self.assertIn("| name | type | verdict | api | tier | template |", assess.render_batch(rows))

    def test_json_schema(self):
        report = assess.build_report(FIXTURES / "vulkan_game", None)
        self.assertEqual(report["schemaVersion"], assess.SCHEMA_VERSION)
        for key in ("sourceType", "heavy", "runMode", "template", "osSettings", "osApis", "detections", "performance",
                    "referencePort", "workList", "blockerDetails", "stagedPlan", "previewOptions", "license"):
            self.assertIn(key, report)
        for key in ("audio", "input", "network", "drm", "threads", "memory", "textures", "data"):
            self.assertIn(key, report["detections"])
        for key in ("tier", "profile"):
            self.assertIn(key, report["performance"])
        for item in report["workList"]:
            self.assertEqual(set(item), {"task", "difficulty", "duration", "status"})
            self.assertIn(item["difficulty"], ("easy", "medium", "hard"))
        json.loads(json.dumps(report))
        text = assess.render(report)
        for heading in ("## Recommended route", "## Preview options", "## Work list", "## Staged port plan", "## OS settings"):
            self.assertIn(heading, text)

    def test_evidence_is_file_and_line(self):
        report = assess.build_report(FIXTURES / "emulator_dynarec", None)
        self.assertRegex(report["signals"]["jit_exec"], r"^src/cpu/dynarec\.c:\d+$")
        for item in report["sourceType"]["evidence"]:
            self.assertTrue(item.startswith("path") or re.search(r":\d+$", item), item)

    def test_preview_items_stay_out_of_the_main_route(self):
        report = assess.build_report(FIXTURES / "vulkan_game", None, "1.3.28-beta.2")
        self.assertEqual(report["template"]["status"], "released")
        self.assertEqual(report["runMode"]["status"], "released")
        # An OS 1.3.x target: no Vulkan there, so the route is GL and says why.
        self.assertFalse(report["vulkan"]["available"])
        self.assertIn("GL (renderer port)", report["runMode"]["mode"])
        self.assertTrue(any("Vulkan is not in OS" in text for text in report["limits"]))
        self.assertTrue(any("use the GL path" in step for step in report["route"]))
        # From OS 1.4.0 Vulkan is released (owner decision): native Vulkan route with a GL fallback.
        new_os = assess.build_report(FIXTURES / "vulkan_game", None, "1.4.0")
        self.assertTrue(new_os["vulkan"]["available"])
        self.assertIn("vulkan (gl fallback)", new_os["runMode"]["mode"].lower())
        self.assertTrue(any("GL" in step and "fallback" in step for step in new_os["route"]))
        self.assertTrue(all(s["status"] == "released" for s in report["osSettings"]["released"]))
        self.assertTrue(all(a["status"] == "released" for a in report["osApis"]["released"]))
        self.assertFalse(any(o["item"] in ("template vulkan", "Vulkan path (bonus next to GL)") for o in report["previewOptions"]))
        self.assertTrue(all(o["status"] != "released" or "NexGFX" in o["item"] for o in report["previewOptions"]))

    def test_os_version_compare(self):
        self.assertLess(assess.os_tuple("1.3.28-beta.2"), assess.os_tuple("1.4.0"))
        self.assertEqual(assess.os_tuple("1.4"), (1, 4, 0))
        caps = assess.load_capabilities()
        self.assertFalse(assess.vulkan_on_os(caps, None)["available"])
        self.assertTrue(assess.vulkan_on_os(caps, "1.4.1")["available"])

    def test_heavy_source_gets_heavy_profile_and_staged_plan(self):
        report = assess.build_report(FIXTURES / "vulkan_game", None)
        self.assertTrue(report["heavy"]["heavy"])
        self.assertEqual(report["performance"]["profile"], "heavy")
        self.assertEqual([s["stage"] for s in report["stagedPlan"]],
                         ["core", "graphics", "audio", "input", "save", "localization", "package"])
        light = assess.build_report(FIXTURES / "sdl2_game", None)
        self.assertFalse(light["heavy"]["heavy"])
        self.assertEqual(light["stagedPlan"], [])

    def test_heavy_app_marker(self):
        report = self.report({"CMakeLists.txt": "find_package(Qt6)\nadd_executable(x main.cpp)\n",
                              "main.cpp": "#include <QApplication>\n#include <QtWebEngineWidgets>\nint main(){ QApplication a; }\n"})
        self.assertEqual(report["sourceType"]["type"], "app")
        self.assertTrue(report["heavy"]["heavy"])
        self.assertEqual(report["performance"]["profile"], "heavy")

    def test_blocker_lists_ways_around(self):
        report = self.report({"Game.cs": "class A {}\n"})
        self.assertEqual(report["verdict"], "blocked")
        detail = report["blockerDetails"][0]
        self.assertEqual(detail["id"], "language:C#")
        self.assertGreaterEqual(len(detail["waysAround"]), 2)
        self.assertIn("way around", assess.render(report))

    def test_runtime_routes(self):
        web = self.report({"index.html": "<canvas id=c></canvas><script src=app.js></script>",
                           "app.js": "const g = document.getElementById('c').getContext('webgl2'); requestAnimationFrame(f);"})
        self.assertEqual(web["sourceType"]["type"], "web")
        self.assertEqual(web["runMode"]["runtime"], "web")
        lua = self.report({"main.lua": "function love.draw() end\n"})
        self.assertEqual(lua["runMode"]["runtime"], "lua")

    def test_tool_and_library_types(self):
        tool = self.report({"CMakeLists.txt": "add_executable(t main.c)\n",
                            "main.c": "#include <getopt.h>\nint main(int c,char**v){ getopt_long(c,v,0,0,0); puts(\"usage: t\"); }\n"})
        self.assertEqual(tool["sourceType"]["type"], "tool")
        lib = self.report({"CMakeLists.txt": "add_library(z z.c)\n", "z.c": "int z(void){return 0;}\n",
                           "include/z/z.h": "int z(void);\n"})
        self.assertEqual(lib["sourceType"]["type"], "library")

    def test_new_type_is_one_data_edit(self):
        types = assess.load_source_types()
        types["types"] = {"robot": {"label": "robot", "signals": [{"kind": "regex", "pattern": "servo_move", "weight": 5}],
                                    "templates": [], "profile": "generic"}, **types["types"]}
        with tempfile.TemporaryDirectory() as root:
            make(root, {"m.c": "void f(void){ servo_move(); }\n"})
            found = assess.scan(Path(root), types)
            data = assess.data_stats(Path(root), assess.load_capabilities(), types)
            result = assess.classify(found, data, found["languages"], types)
        self.assertEqual(result["type"], "robot")
        self.assertIn("m.c:1", result["evidence"][0])

    def test_detections_audio_input_threads_memory_textures(self):
        report = self.report({
            "a.c": "#include <AL/al.h>\nvoid f(){ alcOpenDevice(0); SDL_GameControllerOpen(0); pthread_create(0,0,0,0);\n"
                   "pthread_create(0,0,0,0); static char big[64 * 1024 * 1024]; int t = GL_COMPRESSED_RGBA_S3TC_DXT5_EXT; }\n",
            "data/t.dds": "x", "data/u.png": "y"})
        det = report["detections"]
        self.assertIn("audio_openal", det["audio"])
        self.assertIn("input_gamepad", det["input"])
        self.assertEqual(det["threads"]["sites"], 2)
        self.assertEqual(det["memory"][0]["where"], "a.c:3")
        self.assertEqual(det["textures"]["files"], {"DDS (BCn)": 1, "PNG": 1})
        self.assertIn("tex_bc", det["textures"]["code"])

    def test_data_over_package_limits_is_flagged(self):
        caps = assess.load_capabilities()
        caps["limits"] = dict(caps["limits"], packageFilesMax=2, packageUnpackedBytesMax=10)
        with tempfile.TemporaryDirectory() as root:
            make(root, {f"d/{i}.bin": "0123456789" for i in range(3)})
            stats = assess.data_stats(Path(root), caps, assess.load_source_types())
        self.assertEqual(stats["files"], 3)
        self.assertEqual(len(stats["flags"]), 2)

    def test_unrecognised_licence_is_unknown(self):
        report = self.report({"m.c": "int main(void){return 0;}\n", "LICENSE": "All rights reserved by someone."})
        self.assertEqual(report["license"], ["unknown"])

    def test_rust_project_is_not_unknown(self):
        # Regression: program code in a non-native language with no graphics was reported "unknown", as if absent.
        report = assess.build_report(FIXTURES / "rust_python", None)
        self.assertEqual(report["verdict"], "limited")
        self.assertEqual(report["sourceType"]["type"], "software")

    def test_source_types_reference_real_templates_and_runtimes(self):
        caps, types = assess.load_capabilities(), assess.load_source_types()
        for name, spec in types["types"].items():
            for option in spec.get("templates", []) + spec.get("previewTemplates", []):
                self.assertIn(option["template"], caps["templates"], name)
            if spec.get("runtime"):
                self.assertIn(spec["runtime"], caps["runtimes"])
        for runtime in types["runtimeForLanguage"].values():
            self.assertIn(runtime, caps["runtimes"])


if __name__ == "__main__":
    unittest.main()
