"""Tests for scaffold.py and the experience presets (golden output must not drift)."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import experience as xp
import port_studio as studio
import scaffold

# SHA-256 of generated/experience.json and generated/nx_experience.h (CRLF normalised to LF),
# recorded from the code before the heavy preset was added.
GOLDEN = {
    "rts": ("f4dba57a57ff7a5658c6b7f99e625727a3395190cd17e2fd4ab7d5f08be260e8",
            "1c1a771876b43127577071b4f6ca15ba8faf3c483d3db73ab310823dbac29412"),
    "fps": ("eddda6ce65bf9f3fc81605aa585edf1843206907677df5e01554a7222ee10f29",
            "539379647377e747c31e1d6896fbde7a71247060db08fa7647523b1db84cad9a"),
    "editor": ("f4666f7d60220e80ae43747373e9fcc87576ccadf9c9a75f53fc3074f0cf697b",
               "2fee8223ca63c72f77cdf84be51e9387ce9b267416fef4eb7a84bb147037a901"),
    "generic": ("87d7810222c3964e164124d22ef2d41bcd35b3f85899b2e6d44b441eb9e95921",
                "3480424c2093514c573b14f685bb36e8657f346d1b21b88c6ccee67ce8857344"),
}


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class GoldenPresetTest(unittest.TestCase):
    def test_presets_byte_identical(self):
        for profile, expected in GOLDEN.items():
            with tempfile.TemporaryDirectory() as tmp:
                port = Path(tmp)
                (port / "port.json").write_text(json.dumps({"experience": {"schema": 1, "profile": profile}}))
                xp.generate(port, xp.resolve(xp.port_config(port)))
                got = tuple(digest(port / "generated" / name) for name in ("experience.json", "nx_experience.h"))
                self.assertEqual(got, expected, profile)

    def test_heavy_valid(self):
        resolved = xp.resolve({"experience": {"schema": 1, "profile": "heavy"}})
        self.assertEqual(xp.validate(resolved), [])
        self.assertEqual(resolved["performance"]["handheld"]["renderScale"], 0.67)
        self.assertIn("basis", xp.load_profile("heavy"))


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = patch.object(studio, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def report(self, **over):
        data = {"name": "t", "verdict": "limited", "graphics": {"api": "opengl-4.x", "level": 4},
                "performance": {}, "libraries": {"build_from_source": {"foo": {}}}}
        data.update(over)
        path = self.root / "report.json"
        path.write_text(json.dumps(data))
        return str(path)

    def run_scaffold(self, slug="demo", report=None, *extra):
        return scaffold.main(["game", slug, "strategy", "--from-assess", report or self.report(), *extra])

    def test_creates_files(self):
        self.assertEqual(self.run_scaffold(), 0)
        port = self.root / "GamePorts/demo"
        for rel in ("PORT.md", "port.json", "sdk.lock.json", "CMakeLists.txt", "src/nx_port_rules.h",
                    "TODO_icon.txt", "TODO_screenshots.txt",
                    "AppMarket/Store/Games/strategy/demo/source/app.json"):
            self.assertTrue((port / rel).is_file(), rel)
        app = json.loads((port / "AppMarket/Store/Games/strategy/demo/source/app.json").read_text())
        self.assertEqual((app["minNative"], app["memory"], app["loadingHint"]), ("1.1", 512, True))
        self.assertIn("`foo`", (port / "PORT.md").read_text())
        self.assertIn("nxn_should_quit", (port / "src/nx_port_rules.h").read_text())
        self.assertIn("#if defined(NXN_CAP_MEMORY_BUDGET)", (port / "src/nx_port_rules.h").read_text())

    def test_refuses_existing(self):
        (self.root / "GamePorts/demo").mkdir(parents=True)
        self.assertEqual(self.run_scaffold(), 1)
        self.assertEqual(list((self.root / "GamePorts/demo").iterdir()), [])

    def test_heavy_for_tier4_and_generic_below(self):
        self.run_scaffold()
        config = json.loads((self.root / "GamePorts/demo/port.json").read_text())
        self.assertEqual(config["experience"]["profile"], "heavy")
        self.run_scaffold("light", self.report(graphics={"api": "opengl-3", "level": 2}))
        config = json.loads((self.root / "GamePorts/light/port.json").read_text())
        self.assertEqual(config["experience"]["profile"], "rts")

    def test_emulator_block(self):
        self.run_scaffold()
        config = json.loads((self.root / "GamePorts/demo/port.json").read_text())
        self.assertEqual(config["emulator"]["targets"]["play"]["docked"], [640, 600])
        self.assertEqual(set(config["emulator"]["scenarios"]), {"gameplay", "update", "clean_install"})
        self.assertIn("placeholders", (self.root / "GamePorts/demo/PORT.md").read_text())

    def test_vulkan_template_is_released_with_os_and_sdk_notes(self):
        # Owner decision: Vulkan is released from OS 1.4.0, so no --allow-preview; the notes name OS 1.4.0 and SDK 1.15.
        self.assertEqual(self.run_scaffold("vk", None, "--template", "vulkan"), 0)
        header = (self.root / "GamePorts/vk/src/nx_vulkan_path.h").read_text()
        self.assertIn("nxn_vk_available", header)
        self.assertIn("OS 1.4.0", header)
        notes = (self.root / "GamePorts/vk/PORT.md").read_text()
        self.assertIn("OS 1.4.0", notes)
        self.assertIn("`nxn_vk.h` ships with SDK 1.16", notes)
        self.assertIn("#include <nexvyn/nxn_vk.h>", header)

    def test_old_port_output_unchanged_except_new_defaults(self):
        golden = json.loads((Path(scaffold.__file__).parent / "fixtures/scaffold/golden_before_p2.json").read_text(encoding="utf-8"))
        cases = {"game": ("strategy", {}),
                 "software": ("developer", {"verdict": "ok", "graphics": {"api": "opengl-3.x/gles", "level": 2},
                                            "performance": {"tier": 2}, "libraries": {}})}
        for kind, (category, over) in cases.items():
            report = self.report(**over)  # report() rewrites one file: build each just before use
            root = self.root / kind
            port = scaffold.scaffold(scaffold.argparse.Namespace(kind=kind, slug="gold", category=category, from_assess=report,
                                                                 template=None, allow_preview=False, dest=str(root)))
            files = {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}
            self.assertEqual(set(files), set(golden[kind]["files"]), kind)
            changed = sorted(f for f in files if files[f] != golden[kind]["files"][f])
            # sdk.lock.json pins the active SDK, which is always the newest one, so it may differ from the recording.
            self.assertTrue(all(f.endswith(("source/app.json", "/PORT.md", "/sdk.lock.json")) for f in changed), changed)
            app_path = next(port.rglob("source/app.json"))
            app = json.loads(app_path.read_text(encoding="utf-8"))
            sdk_keys = ("minSdk", "targetSdk", "targetNative")  # follow the active SDK, always the newest
            self.assertEqual({k: v for k, v in app.items() if k not in ("loadingHint", "fullscreenPause", *sdk_keys)},
                             {k: v for k, v in golden[kind]["app"].items() if k not in ("loadingHint", *sdk_keys)}, kind)
            lock = json.loads((port / "sdk.lock.json").read_text(encoding="utf-8"))
            self.assertEqual((app["targetSdk"], app["targetNative"]), (lock["sdk"], lock["native"]))
            self.assertEqual((app["loadingHint"], app["fullscreenPause"]), (True, True))
            self.assertIn("performance panel", (port / "PORT.md").read_text(encoding="utf-8"))

    def test_locales_same_keys(self):
        self.run_scaffold()
        keys = set()
        files = sorted((self.root / "GamePorts/demo/lang").glob("*.json"))
        self.assertEqual([f.stem for f in files], sorted(scaffold.LOCALES))
        for f in files:
            keys.add(tuple(sorted(json.loads(f.read_text(encoding="utf-8")))))
        self.assertEqual(len(keys), 1)


class NewAppTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def new(self, *args):
        return scaffold.main(["new-app", *args, "--dest", str(self.root)])

    def test_script_runtimes_create_store_items_that_pack(self):
        import subprocess, sys
        nxv = studio.sdk_paths(studio.SDK)[0]
        for runtime, main in (("lua", "main.lua"), ("js", "main.js"), ("python3", "main.py")):
            slug = "idea-" + runtime
            self.assertEqual(self.new(runtime, slug), 0)
            source = self.root / "SoftwarePorts" / slug / "source"
            app = json.loads((source / "app.json").read_text(encoding="utf-8"))
            self.assertEqual(app["main"], main)
            self.assertEqual(sorted(p.stem for p in (source / "lang").glob("*.json")), sorted(scaffold.LOCALES))
            result = subprocess.run([sys.executable, str(nxv), "pack", str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((self.root / "SoftwarePorts" / slug / f"{slug}.nxvapp").is_file())
        self.assertTrue(json.loads((self.root / "SoftwarePorts/idea-python3/source/app.json").read_text(encoding="utf-8"))["loadingHint"])

    def test_native_runtimes_use_port_skeleton_without_assess(self):
        self.assertEqual(self.new("native-app", "tool-x"), 0)
        self.assertEqual(self.new("game", "game-x", "--category", "puzzle"), 0)
        self.assertTrue((self.root / "SoftwarePorts/tool-x/CMakeLists.txt").is_file())
        app = json.loads((self.root / "GamePorts/game-x/AppMarket/Store/Games/puzzle/game-x/source/app.json").read_text())
        self.assertEqual((app["mode"], app["gamepad"], app["fullscreenPause"]), ("fullscreen", True, True))

    def test_web_and_game_flag_and_bad_category(self):
        self.assertEqual(self.new("web", "web-x"), 0)
        self.assertIn("webgl2", (self.root / "SoftwarePorts/web-x/web/index.html").read_text(encoding="utf-8"))
        self.assertEqual(self.new("lua", "lua-game", "--game", "--category", "puzzle"), 0)
        self.assertEqual(json.loads((self.root / "GamePorts/lua-game/source/app.json").read_text(encoding="utf-8"))["category"], "games")
        self.assertEqual(self.new("lua", "bad", "--category", "nope"), 1)
        self.assertEqual(self.new("web", "web-x"), 1)  # never overwrites


if __name__ == "__main__":
    unittest.main()
