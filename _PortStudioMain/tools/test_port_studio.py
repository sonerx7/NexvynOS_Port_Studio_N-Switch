"""Tests that local data and the App Market package never get mixed up."""

import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile
from zlib import compress, crc32

import port_studio as studio
import port_market as market
import sync_nexvyn_sdk as sdk_sync


import studio_pack as studio_pack_mod
ACTIVE = studio.sdk_report(studio.SDK)["versions"]  # fixtures follow the active SDK (always the newest)

class PackageChannelsTest(unittest.TestCase):
    def use(self, context):
        result = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return result

    def setUp(self):
        self.root = Path(self.use(tempfile.TemporaryDirectory()))
        self.use(patch.object(studio, "ROOT", self.root))
        real_sdk_call = studio.sdk_call

        def sdk_call(tool, *args):
            if tool != studio.NATIVE:
                real_sdk_call(tool, *args)
            else:
                self.assertEqual(args[0], "check-win")
                if not args[1].read_bytes().startswith(b"\x7fELF"):
                    raise ValueError("Invalid native module.")

        self.use(patch.object(studio, "sdk_call", side_effect=sdk_call))
        (self.root / "GamePorts").mkdir()
        (self.root / "SoftwarePorts").mkdir()
        self.port = self.root / "GamePorts/fixture-port"
        self.item = self.port / "AppMarket/Store/Games/strategy/fixture-port"
        self.source = self.item / "source"
        self.assertEqual(self.cli("init", "game", "fixture-port", "strategy"), 0)
        languages = ("en", "tr", "de", "es", "fr", "ja", "ko", "zh")
        translations = dict.fromkeys(languages, "Fixture")
        self.write_json(self.source / "app.json", {
            "id": "com.test.fixture", "name": translations, "description": translations,
            "version": "1.2.3", "category": "games", "runtime": "native", "mode": "window",
            "minSdk": "1.10", "targetSdk": ACTIVE["sdk"], "minNative": "1.2", "targetNative": ACTIVE["native"],
            "main": "main.nxvmod", "gamepad": True, "permissions": [],
        })
        # This synthetic file only tests the package chain. It is not a runnable game.
        header = bytearray(64)
        header[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into("<HHI", header, 16, 3, 183, 1)
        (self.source / "main.nxvmod").write_bytes(header)
        (self.source / "icon.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", 256, 256)
        )
        for name in ("LICENSE", "NOTICE.md"):
            (self.source / name).write_text("Fixture.", encoding="utf-8")
        for name in ("PORT.md", "DISTRIBUTION.md"):
            (self.port / name).write_text("# Test fixture\n\nTest data.", encoding="utf-8")
        for name in ("CHANGELOG.md", "KNOWN_ISSUES.md"):
            (self.port / name).write_text("# Test fixture\n\n## 1.2.3\n\n- Test data.\n", encoding="utf-8")
        (self.source / "lang").mkdir()
        for lang in languages:
            self.write_json(self.source / f"lang/{lang}.json", {"play": "Play"})
        self.public = sorted(p.relative_to(self.source).as_posix() for p in self.source.rglob("*") if p.is_file())
        self.configure([{"from": "owned", "to": "game"}])
        self.write_json(self.item / "store.json", {
            "kind": "port", "subtitle": translations, "description": translations,
            "features": ["offline", "controller"], "shots": [["wait 1"], ["wait 2"], ["wait 3"]],
        })
        (self.item / "README.md").write_text("# Fixture Port", encoding="utf-8")
        (self.item / "screenshots").mkdir()
        def png_chunk(kind, value):
            return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", crc32(kind + value))

        screenshot = (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + png_chunk(b"IDAT", compress(b"\0\0"))
            + png_chunk(b"IEND", b"")
        )
        for index in range(1, 4):
            (self.item / "screenshots" / f"{index}.png").write_bytes(screenshot)
        self.data = self.root / "data"
        (self.data / "owned").mkdir(parents=True)
        (self.data / "owned/main.mix").write_bytes(b"personal only")

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def configure(self, mappings):
        self.write_json(self.port / "port.json", {
            "slug": "fixture-port", "storeCategory": "strategy",
            "publicFiles": self.public, "localData": mappings,
            "release": {"status": "ready", "version": "1.2.3", "reasons": []},
        })

    def cli(self, *args):
        errors = io.StringIO()
        with patch("sys.argv", ["port_studio.py", *map(str, args)]), contextlib.redirect_stderr(errors):
            result = studio.main()
        self.last_error = errors.getvalue()
        return result

    def test_channels_and_failed_rebuild(self):
        self.assertEqual(self.cli("check", "store", self.port), 0, self.last_error)
        self.assertEqual(self.cli("pack", "local", self.port, "--data-root", self.data), 0, self.last_error)
        self.assertEqual(self.cli("pack", "store", self.port), 0, self.last_error)
        local = self.root / "_RealesedBuilds/game/fixture-port/com.test.fixture-1.2.3-local.nxvapp"
        store = self.item / "fixture-port.nxvapp"
        with ZipFile(local) as personal, ZipFile(store) as public:
            expected = {*self.public, "manifest.sha256"}
            self.assertEqual(set(public.namelist()), expected)
            self.assertEqual(set(personal.namelist()), expected | {"game/main.mix"})
            self.assertEqual(personal.read("game/main.mix"), b"personal only")
            self.assertEqual(personal.read("app.json"), public.read("app.json"))
        before = store.read_bytes()
        self.assertEqual(self.cli("pack", "store", self.port, "--data-root", self.data), 1)
        (self.source / "unlisted.bin").write_bytes(b"potential personal data")
        self.assertEqual(self.cli("pack", "store", self.port), 1)
        self.assertIn("not listed: unlisted.bin", self.last_error)
        self.assertEqual(store.read_bytes(), before)

    def test_preview_sdk_files_never_reach_a_package(self):
        # OS 1.4.0 / SDK 1.16 headers stay out of every package until that release is public.
        (self.source / "include").mkdir()
        (self.source / "include/nxn_future_preview.h").write_text("/* preview */", encoding="utf-8")
        self.use(patch.object(studio_pack_mod, "PREVIEW_HEADERS", {"nxn_future_preview.h"}))
        self.public = sorted(p.relative_to(self.source).as_posix() for p in self.source.rglob("*") if p.is_file())
        self.configure([{"from": "owned", "to": "game"}])
        for args in (("pack", "store", self.port), ("pack", "local", self.port, "--data-root", self.data)):
            self.assertEqual(self.cli(*args), 1)
            self.assertIn("Preview-only SDK files", self.last_error)
            self.assertIn("include/nxn_future_preview.h", self.last_error)
        self.assertFalse((self.item / "fixture-port.nxvapp").exists())

    def test_preview_candidate_content_is_caught_by_digest(self):
        import studio_pack
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            released, candidates, stage = tmp / "sdk", tmp / "cands", tmp / "stage"
            kit = studio_pack.PREVIEW_KIT
            (released / kit / "include/nexvyn").mkdir(parents=True)
            (released / kit / "include/nexvyn/nxn_sys.h").write_text("released", encoding="utf-8")
            cand = candidates / "preview-abc"
            (cand / kit / "include/nexvyn").mkdir(parents=True)
            (cand / kit / "include/nexvyn/nxn_sys.h").write_text("preview 1.16", encoding="utf-8")
            (cand / kit / "include/nexvyn/nxn_new.h").write_text("new", encoding="utf-8")
            (cand / "PREVIEW_FILES.json").write_text(json.dumps(["include/nexvyn/nxn_sys.h", "include/nexvyn/nxn_new.h"]))
            stage.mkdir()
            (stage / "sys_copy.h").write_text("released", encoding="utf-8")
            studio_pack.check_no_preview_payload(stage, released, candidates)  # released content passes
            (stage / "sys_copy.h").write_text("preview 1.16", encoding="utf-8")
            with self.assertRaises(ValueError):
                studio_pack.check_no_preview_payload(stage, released, candidates)
            (stage / "sys_copy.h").write_text("released", encoding="utf-8")
            (stage / "nxn_new.h").write_text("anything", encoding="utf-8")
            with self.assertRaises(ValueError):
                studio_pack.check_no_preview_payload(stage, released, candidates)

    def test_rejects_overlap_and_missing_version_entry(self):
        self.configure([{"from": "owned/main.mix", "to": "LANG/en.json"}])
        self.assertEqual(self.cli("check", "store", self.port), 1)
        self.assertIn("collides with a personal-data target", self.last_error)
        self.configure([])
        (self.port / "KNOWN_ISSUES.md").write_text("# Bilinen sorunlar\n\n## 1.2.30\n\n- Veri.", encoding="utf-8")
        self.assertEqual(self.cli("check", "local", self.port), 1)
        self.assertIn("## 1.2.3 section", self.last_error)

    def test_software_scaffold_and_no_overwrite(self):
        self.assertEqual(self.cli("init", "software", "fixture-app", "utilities"), 0, self.last_error)
        port = self.root / "SoftwarePorts/fixture-app"
        self.assertTrue((port / "AppMarket/Store/Apps/utilities/fixture-app/source").is_dir())
        self.assertEqual(self.cli("init", "software", "fixture-app", "utilities"), 1)
        self.assertTrue((port / "PORT.md").is_file())

    def test_store_rejects_fake_screenshot(self):
        screenshots = self.item / "screenshots"
        (screenshots / "1.png").write_bytes(b"not a PNG")
        self.assertEqual(self.cli("check", "store", self.port), 1)
        self.assertIn("Invalid store screenshot", self.last_error)

    def test_shot_scenarios_allow_check_but_not_release_package(self):
        for shot in (self.item / "screenshots").glob("*.png"):
            shot.unlink()
        self.assertEqual(self.cli("check", "store", self.port), 0, self.last_error)
        self.assertEqual(self.cli("pack", "store", self.port), 1)
        self.assertIn("1.png", self.last_error)

    def test_release_hold_keeps_technical_check_and_local_package_available(self):
        config = studio.read_json(self.port / "port.json")
        config["release"] = {"status": "blocked", "reasons": ["Cihaz testi bekliyor."]}
        self.write_json(self.port / "port.json", config)
        self.assertEqual(self.cli("check", "store", self.port), 0, self.last_error)
        self.assertEqual(self.cli("pack", "local", self.port, "--data-root", self.data), 0, self.last_error)
        self.assertEqual(self.cli("pack", "store", self.port), 1)
        self.assertIn("Cihaz testi bekliyor.", self.last_error)
        request = SimpleNamespace(port=self.port, item="fixture-release", license="CC0-1.0",
                                  output=self.root / "archive", full_package=False)
        with self.assertRaisesRegex(ValueError, "Cihaz testi bekliyor"):
            market.archive(request)

    def test_pin_rejects_sdk_version_mismatch_at_same_commit(self):
        path = self.port / "sdk.lock.json"
        pin = studio.read_json(path)
        pin["native"] = "999"
        self.write_json(path, pin)
        self.assertEqual(self.cli("check", "store", self.port), 1)
        self.assertIn("Native 999", self.last_error)

    def test_release_approval_is_tied_to_the_reviewed_version(self):
        config = studio.read_json(self.port / "port.json")
        config["release"]["version"] = "1.2.2"
        self.write_json(self.port / "port.json", config)
        self.assertEqual(self.cli("check", "store", self.port), 0, self.last_error)
        self.assertEqual(self.cli("pack", "store", self.port), 1)
        self.assertIn("Review version 1.2.3", self.last_error)

    def test_stage_accepts_only_validated_module_and_preserves_existing_on_error(self):
        old = (self.source / "main.nxvmod").read_bytes()
        incoming = self.root / "incoming.nxvmod"
        incoming.write_bytes(b"invalid module")
        self.assertEqual(self.cli("stage", self.port, "--module", incoming), 1)
        self.assertEqual((self.source / "main.nxvmod").read_bytes(), old)
        (self.source / "main.nxvmod").unlink()
        incoming.write_bytes(old)
        self.assertEqual(self.cli("stage", self.port, "--module", incoming), 0, self.last_error)
        self.assertEqual((self.source / "main.nxvmod").read_bytes(), old)

    def test_archive_full_package_requires_explicit_distribution_setting(self):
        self.assertEqual(self.cli("pack", "local", self.port, "--data-root", self.data), 0, self.last_error)
        request = SimpleNamespace(port=self.port, item="fixture-release", license="CC0-1.0",
                                  output=self.root / "archive", full_package=True)
        with patch.object(market, "ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "archiveFullData"):
                market.archive(request)
            config = studio.read_json(self.port / "port.json")
            config["archiveFullData"] = True
            self.write_json(self.port / "port.json", config)
            market.archive(request)
        with ZipFile(request.output / "fixture-port-1.2.3.nxvapp") as package:
            self.assertEqual(package.read("game/main.mix"), b"personal only")
        metadata = studio.read_json(request.output / "internet-archive.json")
        self.assertEqual(metadata["identifier"], "fixture-release")
        self.assertEqual(metadata["title"], "Fixture 1.2.3")


    def test_import_uses_tracked_files_and_preserves_previous_snapshot(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        root = Path(work.name)
        checkout = root / "upstream"
        source = checkout / "SDK"
        st = root / "studio"
        installed = st / "nexvyn_sdk"
        installed.mkdir(parents=True)
        (installed / "local.key").write_text("preserve", encoding="utf-8")
        files = (*sdk_sync.REQUIRED, "Fonts/.gitkeep")
        for name in (*files, "local.key"):
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture", encoding="utf-8")
        (source / "VERSION.json").write_text(
            '{"os":"1.0","sdk":"1.0","native":"1.0","requiredLocales":["en"]}', encoding="utf-8"
        )

        def git_stub(_checkout, command, *_args):
            return {
                "rev-parse": "a" * 40, "status": "", "ls-files": "\0".join(f"SDK/{name}" for name in files),
                "config": f"https://github.com/{studio.SDK_REPOSITORY}.git",
            }[command]

        with patch.multiple(sdk_sync, STUDIO=st, SDK=installed, git=git_stub):
            sdk_sync.sync(checkout, verify_tools=False)
        self.assertTrue((installed / "Fonts/.gitkeep").is_file())
        self.assertFalse((installed / "local.key").exists())
        previous = list((st / "_SdkBackups").glob("*/nexvyn_sdk/local.key"))
        self.assertEqual(len(previous), 1)
        self.assertEqual(previous[0].read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
