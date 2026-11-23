import tempfile
import unittest
from pathlib import Path

import bump
import emulator_test


class StepsTests(unittest.TestCase):
    def test_tap_expands_to_press_and_release(self):
        out = emulator_test.expand_steps("tap 10 20\nwait 2\n").splitlines()
        self.assertEqual(out[0], "finger 0 down 10 20")
        self.assertIn("finger 0 up 10 20", out)
        self.assertEqual(out[-1], "wait 2")

    def test_named_target_resolves_per_mode(self):
        targets = {"play": {"handheld": [816, 172]}}
        out = emulator_test.expand_steps("tap play", targets, "handheld").splitlines()
        self.assertEqual(out[0], "finger 0 down 816 172")
        with self.assertRaises(ValueError):
            emulator_test.expand_steps("tap play", targets, "docked")


class BumpTests(unittest.TestCase):
    def test_bump_updates_versions_and_adds_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp)
            (port / "app.json").write_text('{"version": "1.0.0"}', encoding="utf-8")
            (port / "CHANGELOG.md").write_text("# Log\n\n## 1.0.0\n\n- first\n", encoding="utf-8")
            (port / "KNOWN_ISSUES.md").write_text("# Issues\n\n## 1.0.0\n\n- none\n", encoding="utf-8")
            self.assertEqual(bump.main([str(port), "1.0.1"]), 0)
            self.assertIn('"1.0.1"', (port / "app.json").read_text(encoding="utf-8"))
            self.assertIn("## 1.0.1", (port / "CHANGELOG.md").read_text(encoding="utf-8"))
            self.assertIn("## 1.0.1", (port / "KNOWN_ISSUES.md").read_text(encoding="utf-8"))

    def test_bump_refuses_same_or_lower_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp)
            (port / "app.json").write_text('{"version": "1.0.1"}', encoding="utf-8")
            self.assertEqual(bump.main([str(port), "1.0.1"]), 1)
            self.assertEqual(bump.main([str(port), "1.0.0"]), 1)


if __name__ == "__main__":
    unittest.main()
