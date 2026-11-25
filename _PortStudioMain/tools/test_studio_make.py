"""Tests for studio_make.py: the workspace copy and the step order (each step is an existing command)."""

import hashlib
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import studio_make


def tree_digest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


class MakeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.port = self.root / "repo/GamePorts/demo"
        files = {
            "port.json": json.dumps({"publicFiles": ["app.json", "assets/logo.png"],
                                     "localData": [{"from": "game/data.mix", "to": "game/data.mix"},
                                                   {"from": "assets/private.csf", "to": "assets/private.csf"}],
                                     "build": {"driver": "manual"}}),
            "PORT.md": "# demo", "assets/logo.png": "png", "assets/private.csf": "personal",
            "game/data.mix": "personal", "build/x.o": "obj", "build_nx/y.o": "obj", "dist/z.nxvapp": "pkg",
            "screenshots/a.png": "shot", "AppMarket/Store/Games/strategy/demo/source/app.json": json.dumps({"id": "com.t.demo"}),
        }
        for rel, text in files.items():
            (self.port / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.port / rel).write_text(text, encoding="utf-8")

    def test_copy_leaves_build_output_and_personal_data_behind(self):
        copy = studio_make.copy_port(self.port, self.root / "ws")
        names = set(tree_digest(copy))
        self.assertIn("assets/logo.png", names)
        self.assertIn("AppMarket/Store/Games/strategy/demo/source/app.json", names)
        for gone in ("game/data.mix", "assets/private.csf", "build/x.o", "build_nx/y.o", "dist/z.nxvapp", "screenshots/a.png"):
            self.assertNotIn(gone, names)
        self.assertEqual(studio_make.copy_port(self.port, self.root / "ws"), copy)  # reused, not copied again

    def test_steps_run_existing_commands_on_the_copy_and_stop_at_a_failure(self):
        before = tree_digest(self.port)
        seen = []

        def fake(name, command, env, log):
            seen.append((name, command, env.get("PORT_STUDIO_ROOT")))
            log.append({"step": name, "command": " ".join(map(str, command)), "exit": 0 if name != "verify" else 1,
                        "seconds": 0, "tail": []})
            return name != "verify", ""

        args = Namespace(port=str(self.port), module=str(self.root / "m.nxvmod"), data_root=None,
                         workspace=str(self.root / "ws"), mode="both", steps=None)
        with patch.object(studio_make, "run_step", side_effect=fake):
            self.assertEqual(studio_make.make(args, self.root / "repo"), 1)
        self.assertEqual([s[0] for s in seen], ["doctor", "build", "verify"])
        self.assertTrue(all(root == str((self.root / "ws").resolve()) or root == str(self.root / "ws") for _, _, root in seen))
        self.assertIn("stage", seen[1][1])  # manual driver: stage --module
        self.assertTrue(all(str(self.port) not in " ".join(map(str, c)) for _, c, _ in seen))
        self.assertEqual(tree_digest(self.port), before)  # the original port is only read
        report = (self.root / "ws/make_report.md").read_text(encoding="utf-8")
        self.assertIn("Stopped at verify", report)
        self.assertIn("Not tested on a device", report)

    def test_script_app_skips_build_and_packs_with_nxv(self):
        app = self.root / "repo/SoftwarePorts/idea"
        (app / "source").mkdir(parents=True)
        (app / "source/app.json").write_text(json.dumps({"id": "com.t.idea", "main": "main.lua"}), encoding="utf-8")
        (app / "port.json").write_text(json.dumps({"slug": "idea"}), encoding="utf-8")
        seen = []

        def fake(name, command, env, log):
            seen.append((name, [str(c) for c in command]))
            log.append({"step": name, "command": "", "exit": 0, "seconds": 0, "tail": []})
            return True, ""

        args = Namespace(port=str(app), module=None, data_root=None, workspace=None, mode="handheld",
                         steps="doctor,build,verify,pack,scenario")
        with patch.object(studio_make, "run_step", side_effect=fake):
            self.assertEqual(studio_make.make(args, self.root / "repo"), 0)
        names = [n for n, _ in seen]
        self.assertEqual(names, ["doctor", "verify", "pack", "scenario"])  # build skipped for a script app
        self.assertIn("pack", seen[2][1])
        self.assertTrue(seen[2][1][1].endswith("nxv.py"))
        self.assertIn("--source", seen[3][1])
        self.assertIn("build: skipped; script app", (app / "make_report.md").read_text(encoding="utf-8"))

    def test_unknown_step_is_refused(self):
        args = Namespace(port=str(self.port), module=None, data_root=None, workspace=None, mode="both", steps="deploy")
        with self.assertRaises(ValueError):
            studio_make.make(args, self.root / "repo")


if __name__ == "__main__":
    unittest.main()
