"""Tests for market_release.py: release automation for open-source ports (it never uploads)."""

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import market_release as mr


def png(path, shade):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\0" + bytes([shade]) * 4 for _ in range(4))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class MarketReleaseTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.port = Path(tmp.name) / "GamePorts" / "quakeish"
        self.item = self.port / "AppMarket/Store/Games/action/quakeish"
        (self.item / "source").mkdir(parents=True)
        (self.item / "source/app.json").write_text(json.dumps({"id": "com.t.q", "version": "1.0.0", "main": "q.nxvmod"}))
        (self.item / "source/q.nxvmod").write_bytes(b"\x7fELF")
        (self.port / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\n Version 2, June 1991\n")
        (self.port / "port.json").write_text(json.dumps({"slug": "quakeish", "release": {"status": "blocked", "reasons": ["x"]}}))
        (self.port / "PORT.md").write_text("# Port record\n\nOpen-source engine port.\n")
        run = self.port / "screenshots/runs/20261126-100000_gameplay_handheld"
        run.mkdir(parents=True)
        for index, name in enumerate(("launcher", "menu", "ingame_00s", "ingame_10s", "zz_end")):
            png(run / f"{name}.png", 40 * index)
        (run / "scenario.json").write_text(json.dumps({"gameplay": ["ingame_00s", "ingame_10s"]}))
        (run / "review.md").write_text("Automatic checks: **PASS**. Visual review: **PASS**\n")

    def test_item_name_is_search_friendly(self):
        self.assertEqual(mr.suggested_item(Path("x/GamePorts/RedAlert2")), "nexvyn-os-nx-redalert2-game-port")
        self.assertEqual(mr.suggested_item(Path("x/SoftwarePorts/chromium-nx")), "nexvyn-os-nx-chromium-nx-app")

    def test_licence_and_real_shots_are_found(self):
        self.assertEqual(mr.detect_license(self.port)[0], "GPL-2.0")
        shots = [p.stem for p in mr.pick_shots(mr.passing_runs(self.port)[0])]
        self.assertEqual(shots[:2], ["ingame_00s", "ingame_10s"])  # gameplay first
        self.assertNotIn("launcher", shots)
        self.assertNotIn("zz_end", shots)

    def test_lifted_code_is_never_approved(self):
        (self.port / "PORT.md").write_text("Static recompilation of gamemd.exe.\n")
        self.assertIn("lifted", "; ".join(mr.status(self.port)[0]))
        with self.assertRaises(SystemExit):
            mr.approve(self.port, "GPL-2.0", "1.0.0", mr.passing_runs(self.port)[0], "")

    def test_approve_writes_records_and_prepares_without_uploading(self):
        commands = []
        with patch.object(mr, "verify_fails", return_value=[]), \
             patch.object(mr, "run", side_effect=lambda c: commands.append([str(x) for x in c]) or 0), \
             patch.object(mr, "ROOT", self.port.parents[1]), \
             patch.object(mr, "read_json", wraps=mr.read_json) as reader:
            out = self.port.parents[1] / "_RealesedBuilds/archive/quakeish"
            out.mkdir(parents=True)
            (out / "internet-archive.json").write_text(json.dumps({"title": "Quakeish 1.0.0 - Nexvyn OS NX game port"}))
            self.assertEqual(mr.main([str(self.port), "--approve"]), 0)
        config = json.loads((self.port / "port.json").read_text())
        self.assertEqual(config["release"], {"status": "ready", "version": "1.0.0", "reasons": []})
        self.assertEqual(sorted(p.name for p in (self.item / "screenshots").glob("*.png")), ["1.png", "2.png", "3.png"])
        self.assertIn("## 1.0.0", (self.port / "CHANGELOG.md").read_text())
        self.assertIn("GPL-2.0", (self.port / "DISTRIBUTION.md").read_text())
        flat = [" ".join(c) for c in commands]
        self.assertTrue(any("prepare-archive" in c and "nexvyn-os-nx-quakeish-game-port" in c for c in flat))
        self.assertTrue(any(" publish " in f" {c} " for c in flat))
        self.assertFalse(any("--yes" in c or "--full-package" in c for c in flat))

    def test_verify_fail_stops_before_anything_is_written(self):
        with patch.object(mr, "verify_fails", return_value=["content/stand-in FAIL"]), patch.object(mr, "run") as run:
            self.assertEqual(mr.main([str(self.port), "--approve"]), 1)
        run.assert_not_called()
        self.assertFalse((self.item / "screenshots").exists())
        self.assertEqual(json.loads((self.port / "port.json").read_text())["release"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
