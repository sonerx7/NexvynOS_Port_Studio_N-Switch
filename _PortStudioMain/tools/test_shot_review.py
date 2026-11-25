"""Tests for the gameplay scenario run review (shot_review.py) and scenario loading (emulator_test.py)."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import emulator_test
import scenario_run
import shot_review


def noise(path, seed):
    rng = random.Random(seed)
    image = Image.new("RGB", (128, 72))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(128 * 72)])
    image.save(path)


def flat(path, colour=(0, 0, 0)):
    Image.new("RGB", (128, 72), colour).save(path)


SCENARIO = {"name": "gameplay", "mode": "handheld",
            "steps": ["shot launcher", "tap play", "wait 20", "shot ingame_a", "padhold a 2", "wait 5", "shot ingame_b"],
            "gameplay": ["ingame_a", "ingame_b"], "motion": [["ingame_a", "ingame_b"]], "expectLog": ["map loaded"]}


class ShotReviewTest(unittest.TestCase):
    def run_dir(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        return Path(context.name)

    def test_good_run_passes_automatic_and_waits_for_visual(self):
        run = self.run_dir()
        noise(run / "launcher.png", 1)
        noise(run / "ingame_a.png", 2)
        noise(run / "ingame_b.png", 3)
        (run / "com.x.game.log").write_text("map loaded\n", encoding="utf-8")
        (run / "system.log").write_text("[ 1.0] nxwin    com.x.game: 58.0 fps, x\n[ 4.0] nxwin    com.x.game: 30.0 fps, x\n", encoding="utf-8")
        report = shot_review.review(run, SCENARIO, "com.x.game")
        self.assertEqual(report["automatic"], "PASS", report["checks"])
        self.assertEqual(report["fps"]["samples"], 2)
        self.assertEqual(shot_review.check_done(run), 1)  # visual review still PENDING
        text = (run / "review.md").read_text(encoding="utf-8").replace("Visual review: **PENDING**", "Visual review: **PASS**")
        (run / "review.md").write_text(text, encoding="utf-8")
        self.assertEqual(shot_review.check_done(run), 0)

    def test_black_frozen_missing_and_hang_fail(self):
        run = self.run_dir()
        flat(run / "launcher.png", (40, 40, 40))
        flat(run / "ingame_a.png")
        (run / "system.log").write_text("[ 9.0] nxwin    com.x.game is not responding (6.0 s silent)\n", encoding="utf-8")
        report = shot_review.review(run, SCENARIO, "com.x.game")
        failed = {c["check"].split(" (")[0] for c in report["checks"] if c["result"] == "FAIL"}
        self.assertIn("shot ingame_b captured", failed)
        self.assertIn("ingame_a is not blank", failed)
        self.assertIn("log has /map loaded/", failed)
        self.assertIn("system log free of hang/crash/missing symbol/OOM", failed)
        self.assertEqual(report["automatic"], "FAIL")

    def test_identical_gameplay_shots_mean_frozen(self):
        run = self.run_dir()
        noise(run / "launcher.png", 1)
        noise(run / "ingame_a.png", 5)
        noise(run / "ingame_b.png", 5)
        report = shot_review.review(run, dict(SCENARIO, expectLog=[]), "com.x.game")
        motion = [c for c in report["checks"] if c["check"].startswith("picture changed")]
        self.assertEqual(motion[0]["result"], "FAIL")

    def test_shot_after_app_closed_fails(self):
        run = self.run_dir()
        noise(run / "launcher.png", 1)
        noise(run / "ingame_a.png", 2)
        noise(run / "ingame_b.png", 3)
        (run / "system.log").write_text(
            "[ 10.0] autorun  shot ingame_a\n"
            "[ 12.0] nxwin    com.x.game: heap 519 MB reserved in 4 chunk(s), 512 MB in 151 block(s) allocated\n"
            "[ 20.0] res      com.x.game closed: memory in use 874.1 MB; none\n"
            "[ 30.0] autorun  shot ingame_b\n", encoding="utf-8")
        report = shot_review.review(run, dict(SCENARIO, expectLog=[]), "com.x.game")
        result = {c["check"]: c["result"] for c in report["checks"]}
        self.assertEqual(result["app still open at ingame_a"], "PASS")
        self.assertEqual(result["app still open at ingame_b"], "FAIL")
        self.assertEqual(report["peakHeapMB"], 512.0)

    def test_evidence_line_waits_for_visual_review(self):
        run = self.run_dir()
        for i, name in enumerate(("launcher", "ingame_a", "ingame_b")):
            noise(run / f"{name}.png", i + 1)
        (run / "com.x.game.log").write_text("map loaded\n", encoding="utf-8")
        (run / "system.log").write_text("[ 1.0] nxwin    com.x.game: 40.0 fps, x\n", encoding="utf-8")
        shot_review.review(run, SCENARIO, "com.x.game")
        line = json.loads((run / "results.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(line["id"], "STUDIO-GAMEPLAY-HANDHELD")
        self.assertEqual(line["status"], "NOT_RUN")              # automatic pass alone is not a gameplay pass
        self.assertIn("environment=emulator", line["markers"])
        self.assertEqual(line["metrics"]["fps_median"], 40.0)
        self.assertIn("| emulator on ", (run / "performance_row.md").read_text(encoding="utf-8"))
        text = (run / "review.md").read_text(encoding="utf-8").replace("Visual review: **PENDING**", "Visual review: **PASS**")
        (run / "review.md").write_text(text, encoding="utf-8")
        shot_review.check_done(run)
        self.assertEqual(json.loads((run / "results.jsonl").read_text(encoding="utf-8"))["status"], "PASS")

    def test_finished_review_is_never_overwritten(self):
        run = self.run_dir()
        noise(run / "launcher.png", 1)
        (run / "review.md").write_text("# done\nVisual review: **PASS**\n", encoding="utf-8")
        shot_review.review(run, {"steps": ["shot launcher"]}, None)
        self.assertEqual((run / "review.md").read_text(encoding="utf-8"), "# done\nVisual review: **PASS**\n")


class ScenarioLoadTest(unittest.TestCase):
    def port(self, scenarios):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        (Path(context.name) / "port.json").write_text(json.dumps({"emulator": {"scenarios": scenarios}}), encoding="utf-8")
        return context.name

    def test_load_lists_shots(self):
        block = scenario_run.load_scenario(self.port({"gameplay": SCENARIO}), "gameplay")
        self.assertEqual(block["shots"], ["launcher", "ingame_a", "ingame_b"])

    def test_rejects_unknown_and_shotless(self):
        with self.assertRaises(SystemExit):
            scenario_run.load_scenario(self.port({"g": {"steps": ["wait 5"]}}), "g")
        with self.assertRaises(SystemExit):
            scenario_run.load_scenario(self.port({"g": {"steps": ["shot a"], "gameplay": ["b"]}}), "g")
        with self.assertRaises(SystemExit):
            scenario_run.load_scenario(self.port({}), "gameplay")

    def test_scenario_steps_expand_named_taps(self):
        text = emulator_test.expand_steps("\n".join(SCENARIO["steps"]), {"play": {"handheld": [640, 600]}}, "handheld")
        self.assertIn("finger 0 down 640 600", text)
        self.assertIn("shot ingame_b", text)


if __name__ == "__main__":
    unittest.main()


class MotionThresholdTest(unittest.TestCase):
    """Small real changes pass; a single blinking element or an identical frame does not (no false pass)."""

    def setUp(self):
        from PIL import Image
        self.Image = Image
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.base = Image.new("L", (1280, 720), 60)
        for x in range(0, 1280, 40):  # some texture, like a map
            self.base.paste(90, (x, 0, x + 20, 720))

    def pair(self, edit):
        a, b = self.dir / "a.png", self.dir / "b.png"
        self.base.save(a)
        other = self.base.copy()
        edit(other)
        other.save(b)
        return shot_review.motion_result(a, b)[0]

    def test_identical_fails(self):
        self.assertEqual(self.pair(lambda im: None), "FAIL")

    def test_one_blinking_box_fails(self):
        # a focus ring or caret: about 0.07 % of the pixels, all inside one small box
        self.assertEqual(self.pair(lambda im: im.paste(250, (600, 300, 714, 306))), "FAIL")

    def test_scattered_small_changes_pass(self):
        # a counter in one corner and two units that moved: small in total, spread over the frame
        def edit(im):
            im.paste(250, (1150, 5, 1190, 15))
            im.paste(250, (400, 300, 412, 318))
            im.paste(250, (900, 500, 912, 518))
        self.assertEqual(self.pair(edit), "PASS")

    def test_desktop_clock_and_widgets_are_not_motion(self):
        # a launcher on the desktop: the menu-bar clock and the CPU/FPS widget change, the app does not
        def edit(im):
            im.paste(250, (1180, 4, 1270, 20))      # menu-bar clock text
            im.paste(250, (1150, 60, 1260, 120))    # clock widget hands
            im.paste(250, (1100, 300, 1250, 360))   # CPU/FPS meters
        self.assertEqual(self.pair(edit), "FAIL")

    def test_big_change_passes_on_the_mean(self):
        self.assertEqual(self.pair(lambda im: im.paste(200, (0, 0, 1280, 360))), "PASS")
