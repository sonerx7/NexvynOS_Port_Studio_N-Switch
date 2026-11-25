"""Tests for verify.py: temp ports, mocked SDK tools (no devkitPro needed)."""

import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify

REAL_RUN_TOOL = verify.run_tool
LANGS = ("en", "tr", "de", "es", "fr", "ja", "ko", "zh")
SDK = Path("sdk-snapshot")


class VerifyTest(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.port = self.root / "GamePorts" / "fx"
        self.src = self.port / "AppMarket/Store/Games/strategy/fx/source"
        (self.src / "lang").mkdir(parents=True)
        self.module = self.src / "fx.nxvmod"
        self.module.write_bytes(b"\x7fELF")
        for code in LANGS:
            self.write(self.src / "lang" / f"{code}.json", {"title": code, "menu": {"play": code}})
        self.write(self.src / "app.json", {
            "id": "com.test.fx", "main": "fx.nxvmod", "minSdk": "1.13", "minNative": "1.2", "memory": 256,
            "loadingHint": True, "liveResize": True})
        self.write(self.port / "port.json", {
            "slug": "fx", "storeCategory": "strategy",
            "publicFiles": ["app.json", "fx.nxvmod", *(f"lang/{c}.json" for c in LANGS)],
            "localData": [{"from": "game/data.bin", "to": "assets/data.bin"}],
            "emulator": {"scenarios": {
                "update": {"steps": ["shot a"]}, "clean_install": {"steps": ["shot b"]}}}})
        self.tool_output = {"check-win": (0, "ok"), "imports": (0, "fx.nxvmod: ok")}
        stack.enter_context(patch.object(verify.studio, "port_sdk", return_value=SDK))
        stack.enter_context(patch.object(verify, "run_tool", side_effect=self.fake_tool))
        stack.enter_context(patch.object(verify, "load_caps", return_value={
            "limits": {"packageFilesMax": 20000, "packageUnpackedBytesMax": 1 << 30},
            "newApis": [{"symbol": "nxn_vk_proc", "status": "private-preview"}]}))

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def fake_tool(self, script, args, **kw):
        if "check-design" in args:
            raise verify.NotRun("unused")
        if args[0] == "--help":
            return 0, "{new,build,check-win}"
        return self.tool_output[args[0]]

    def status(self, name):
        return {r["check"]: r for r in verify.verify(self.port)}[name]

    def test_clean_port_passes(self):
        rows = verify.verify(self.port)
        self.assertEqual([r["check"] for r in rows if r["status"] == verify.FAIL], [])
        self.assertEqual(self.status("module/check-win")["status"], verify.PASS)
        self.assertEqual(self.status("abi")["status"], verify.PASS)
        self.assertEqual(verify.main([str(self.port)]), 0)

    def test_missing_locale_key_fails(self):
        self.write(self.src / "lang/de.json", {"title": "de"})
        result = self.status("app.json/locales")
        self.assertEqual(result["status"], verify.FAIL)
        self.assertIn("lang/de.json", result["detail"])
        self.assertIn("menu.play", result["detail"])
        self.assertEqual(verify.main([str(self.port)]), 1)

    def test_too_many_files_fails_and_warns(self):
        with patch.object(verify, "load_caps", return_value={"limits": {"packageFilesMax": 5}}):
            self.assertEqual(self.status("limits/package")["status"], verify.FAIL)
        (self.src / "many").mkdir()
        for i in range(1001):
            (self.src / "many" / f"f{i}.txt").write_text("x")
        self.assertEqual(self.status("limits/package")["status"], verify.WARN)

    def test_preview_symbol_is_labelled(self):
        self.tool_output["imports"] = (1, "not in the host import set: nxn_vk_proc\nnot in the host import set: foo_bar")
        result = self.status("abi")
        self.assertEqual(result["status"], verify.FAIL)
        self.assertIn("nxn_vk_proc (private preview: needs a newer public SDK)", result["detail"])
        self.assertIn("foo_bar", result["detail"])
        self.tool_output["imports"] = (1, "not in the host import set: nxn_vk_proc")
        self.assertIn("Needs a newer public SDK", self.status("abi")["fix"])

    def test_missing_devkit_gives_not_run(self):
        script = self.root / "tool.py"
        script.write_text("print('hi')")
        with patch.object(verify, "devkit_missing", return_value="devkitPro not found at X"):
            with self.assertRaises(verify.NotRun) as caught:
                REAL_RUN_TOOL(script, ["check-win", "x"])
        self.assertIn("devkitPro", str(caught.exception))
        with patch.object(verify, "run_tool", side_effect=verify.NotRun("devkitPro not found at X")):
            rows = {r["check"]: r for r in verify.verify(self.port)}
        for name in ("module/check-win", "abi"):
            self.assertEqual(rows[name]["status"], verify.NOT_RUN)
            self.assertIn("devkitPro", rows[name]["detail"])

    def test_tool_timeout_gives_not_run(self):
        script = self.root / "slow.py"
        script.write_text("import time; time.sleep(30)")
        with patch.object(verify, "devkit_missing", return_value=None):
            with self.assertRaises(verify.NotRun) as caught:
                REAL_RUN_TOOL(script, [], timeout=1)
        self.assertIn("timed out", str(caught.exception))

    def test_private_data_in_store_source_fails(self):
        (self.src / "assets").mkdir()
        (self.src / "assets/data.bin").write_bytes(b"x")
        self.assertEqual(self.status("limits/personal-data")["status"], verify.FAIL)

    def test_missing_scenarios_fail_with_snippet(self):
        self.write(self.port / "port.json", {
            "slug": "fx", "storeCategory": "strategy", "publicFiles": ["app.json"], "localData": []})
        result = self.status("scenario/update")
        self.assertEqual(result["status"], verify.FAIL)
        self.assertIn('"update"', result["fix"])

    def test_built_in_program_is_a_fake(self):
        (self.port / "src").mkdir(exist_ok=True)
        (self.port / "src" / "main.cpp").write_text("void boot(){\n    g_ppu.load_builtin_rom(g_vm, mode);\n}\n")
        result = self.status("content/stand-in")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("src/main.cpp:2", result["detail"])

    def test_declared_status_screen_is_a_warning(self):
        (self.port / "src").mkdir(exist_ok=True)
        (self.port / "src" / "boot.cpp").write_text(
            "// nx-allow-standin: boot status line while the real game loads\nstatic void draw_test_pattern(){}\n")
        self.assertEqual(self.status("content/stand-in")["status"], "WARN")

    def test_real_code_and_generated_code_pass(self):
        (self.port / "src" / "gen").mkdir(parents=True, exist_ok=True)
        (self.port / "src" / "gen" / "lifted.c").write_text("/* fake_frame in generated code is not ours */\n")
        (self.port / "src" / "main.c").write_text("/* show an honest status line, never fake art */\nint main(){return 0;}\n")
        self.assertEqual(self.status("content/stand-in")["status"], "PASS")

    def test_user_folder_path_in_records_warns(self):
        (self.port / "PORT.md").write_text("Samples in C:\\Users\\someone\\Desktop\\games\n", encoding="utf-8")
        result = self.status("records/personal-paths")
        self.assertEqual(result["status"], "WARN")
        self.assertIn("PORT.md:1", result["detail"])

    def test_script_app_uses_nxv_check_instead_of_native_checks(self):
        app = self.root / "SoftwarePorts" / "idea"
        (app / "source" / "lang").mkdir(parents=True)
        self.write(app / "source" / "app.json", {"id": "com.t.idea", "main": "main.lua", "minSdk": "1.16", "memory": 64})
        for code in LANGS:
            self.write(app / "source" / "lang" / f"{code}.json", {"title": code})
        (app / "source" / "main.lua").write_text("return {}\n", encoding="utf-8")
        self.tool_output["check"] = (0, "ok")
        rows = {r["check"]: r for r in verify.verify(app)}
        self.assertEqual(rows["script/nxv-check"]["status"], "PASS")
        self.assertEqual(rows["module/check-win"]["status"], "NOT_RUN")
        self.assertEqual(rows["app.json/fields"]["status"], "PASS")  # no minNative needed for a script app

    def test_shader_tool_is_preview_only(self):
        (self.port / "src").mkdir()
        (self.port / "src/a.frag").write_text("void main(){}")
        result = self.status("shaders")
        self.assertEqual(result["status"], verify.NOT_RUN)
        self.assertIn("preview-only", result["detail"])


if __name__ == "__main__":
    unittest.main()
