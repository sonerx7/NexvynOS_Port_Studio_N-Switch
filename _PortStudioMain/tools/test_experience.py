import copy
import json
import tempfile
import unittest
from pathlib import Path

import experience as xp


def cfg(profile, **over):
    return {"experience": {"schema": 1, "profile": profile, **over}}


class ExperienceTests(unittest.TestCase):
    def test_all_presets_valid(self):
        for path in xp.PROFILES.glob("*.json"):
            resolved = xp.resolve(cfg(path.stem))
            self.assertEqual(xp.validate(resolved), [], path.stem)

    def test_override_merges(self):
        resolved = xp.resolve(cfg("rts", performance={"docked": {"fpsCap": 60}}))
        self.assertEqual(resolved["performance"]["docked"]["fpsCap"], 60)
        self.assertEqual(resolved["performance"]["docked"]["resolution"], [1920, 1080])

    def test_reserved_binding_rejected(self):
        resolved = xp.resolve(cfg("generic", input={"actions": {"menu": {"gamepad": ["home"], "touch": ["menu_button"], "kbm": ["escape"]}}}))
        self.assertTrue(any("reserved" in e for e in xp.validate(resolved)))

    def test_missing_mode_binding_rejected(self):
        resolved = xp.resolve(cfg("generic"))
        del resolved["input"]["actions"]["select"]["touch"]
        self.assertTrue(any("touch" in e for e in xp.validate(resolved)))

    def test_gesture_to_unknown_action_rejected(self):
        resolved = xp.resolve(cfg("rts", input={"gestures": {"pinch": "nope"}}))
        self.assertTrue(any("undefined action" in e for e in xp.validate(resolved)))

    def test_perf_range_rejected(self):
        resolved = xp.resolve(cfg("fps", performance={"handheld": {"fpsCap": 500}}))
        self.assertTrue(any("fpsCap" in e for e in xp.validate(resolved)))

    def test_newer_schema_refused_and_unknown_profile(self):
        with self.assertRaises(ValueError):
            xp.resolve({"experience": {"schema": 99, "profile": "rts"}})
        with self.assertRaises(ValueError):
            xp.resolve(cfg("nope"))

    def test_migration_chain(self):
        old_current, old_mig = xp.CURRENT_SCHEMA, dict(xp.MIGRATIONS)
        try:
            xp.CURRENT_SCHEMA = 2
            xp.MIGRATIONS[1] = lambda b: {**b, "migrated": True}
            block = xp.migrate_block({"schema": 1, "profile": "rts"})
            self.assertEqual((block["schema"], block["migrated"]), (2, True))
        finally:
            xp.CURRENT_SCHEMA = old_current
            xp.MIGRATIONS.clear()
            xp.MIGRATIONS.update(old_mig)

    def test_init_check_generate(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp)
            (port / "port.json").write_text('{"slug": "x"}', encoding="utf-8")
            self.assertEqual(xp.main(["init", str(port), "rts"]), 0)
            self.assertEqual(xp.main(["check", str(port)]), 0)
            self.assertEqual(xp.main(["generate", str(port)]), 0)
            header = (port / "generated" / "nx_experience.h").read_text(encoding="utf-8")
            self.assertIn("NX_ACT_CAMERA_ZOOM", header)
            self.assertIn("[NX_GEST_COUNT]", header)
            self.assertEqual(json.loads((port / "generated" / "experience.json").read_text())["profile"], "rts")


class UnsupportedAndAnalyzeTests(unittest.TestCase):
    def test_unsupported_action_and_null_gesture(self):
        resolved = xp.resolve(cfg("rts", input={"unsupported": ["camera_zoom"], "zoom": {"method": "none"}, "gestures": {"two_finger_tap": "command", "pinch": None}}))
        self.assertNotIn("camera_zoom", resolved["input"]["actions"])
        self.assertNotIn("pinch", resolved["input"]["gestures"])
        self.assertEqual(resolved["input"]["gestures"]["two_finger_tap"], "command")
        self.assertEqual(xp.validate(resolved), [])

    def test_analyze_detects_signals(self):
        import analyze
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ra2.mix").write_bytes(b"x")
            (root / "game.c").write_text("SDL_FINGERDOWN; SDL_MOUSEWHEEL", encoding="utf-8")
            (root / "game.exe").write_bytes(b"MZ ddraw.dll GetAsyncKeyState")
            report = analyze.analyze(root)
            for signal in ("input:multitouch", "input:wheel", "graphics:directdraw", "input:keyboard-polling"):
                self.assertIn(signal, report["signals"])
            self.assertEqual(report["genreGuess"]["profile"], "rts")


class ZoomTests(unittest.TestCase):
    def test_present_method_maps_pinch(self):
        resolved = xp.resolve(cfg("rts"))
        self.assertEqual(resolved["input"]["gestures"]["pinch"], "camera_zoom")

    def test_native_needs_evidence(self):
        resolved = xp.resolve(cfg("rts", input={"zoom": {"method": "wheel"}}))
        self.assertTrue(any("evidence" in e for e in xp.validate(resolved)))
        resolved = xp.resolve(cfg("rts", input={"zoom": {"method": "wheel", "evidence": "Tested in game build 1.2: wheel zooms the map."}}))
        self.assertEqual(xp.validate(resolved), [])

    def test_editor_port_can_choose_wheel(self):
        resolved = xp.resolve(cfg("editor", input={"zoom": {"method": "wheel", "evidence": "Manual says wheel zooms."}}))
        self.assertEqual(resolved["input"]["gestures"]["pinch"], "camera_zoom")
        self.assertEqual(xp.validate(resolved), [])

    def test_scenario_mode_must_be_declared(self):
        resolved = xp.resolve(cfg("generic", input={"modes": ["auto", "gamepad"], "defaultMode": "auto"}))
        resolved["scenarios"] = [{"id": "x", "title": "x", "steps": {"touch": "tap"}}]
        self.assertTrue(any("not declared" in e for e in xp.validate(resolved)))


class UpdatesTests(unittest.TestCase):
    def test_version_order_prerelease_below_release(self):
        import updates
        k = updates.version_key
        self.assertTrue(k("v1.3.28-beta.2") < k("1.3.28"))
        self.assertTrue(k("1.3.27") < k("v1.3.28-beta.1"))
        self.assertTrue(k("1.10.0") > k("1.9.9"))
        self.assertIsNone(k("not a version"))


if __name__ == "__main__":
    unittest.main()
