"""Yerel veri ve App Market paketinin birbirine karışmamasını sınar."""

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

import port_studio as studio
import port_market as market
import sync_nexvyn_sdk as sdk_sync


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
                self.assertTrue(args[1].is_file())

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
            "minSdk": "1.10", "targetSdk": "1.15", "minNative": "1.2", "targetNative": "1.2",
            "main": "main.nxvmod", "gamepad": True, "permissions": [],
        })
        # Bu sentetik dosya yalnızca paket zincirini test eder. Çalıştırılabilir bir oyun değildir.
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
        self.data = self.root / "data"
        (self.data / "owned").mkdir(parents=True)
        (self.data / "owned/main.mix").write_bytes(b"personal only")

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def configure(self, mappings):
        self.write_json(self.port / "port.json", {
            "slug": "fixture-port", "storeCategory": "strategy",
            "publicFiles": self.public, "localData": mappings,
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
        self.assertIn("liste dışı: unlisted.bin", self.last_error)
        self.assertEqual(store.read_bytes(), before)

    def test_rejects_overlap_and_missing_version_entry(self):
        self.configure([{"from": "owned/main.mix", "to": "LANG/en.json"}])
        self.assertEqual(self.cli("check", "store", self.port), 1)
        self.assertIn("kişisel veri hedefiyle çakışıyor", self.last_error)
        self.configure([])
        (self.port / "KNOWN_ISSUES.md").write_text("# Bilinen sorunlar\n\n## 1.2.30\n\n- Veri.", encoding="utf-8")
        self.assertEqual(self.cli("check", "local", self.port), 1)
        self.assertIn("## 1.2.3 altında", self.last_error)

    def test_software_scaffold_and_no_overwrite(self):
        self.assertEqual(self.cli("init", "software", "fixture-app", "utilities"), 0, self.last_error)
        port = self.root / "SoftwarePorts/fixture-app"
        self.assertTrue((port / "AppMarket/Store/Apps/utilities/fixture-app/source").is_dir())
        self.assertEqual(self.cli("init", "software", "fixture-app", "utilities"), 1)
        self.assertTrue((port / "PORT.md").is_file())

    def test_store_rejects_fake_screenshot(self):
        screenshots = self.item / "screenshots"
        screenshots.mkdir()
        (screenshots / "1.png").write_bytes(b"not a PNG")
        self.assertEqual(self.cli("check", "store", self.port), 1)
        self.assertIn("Geçersiz mağaza ekran görüntüsü", self.last_error)

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


class SdkSnapshotTest(unittest.TestCase):
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
        (source / "VERSION.json").write_text('{"os":"1.0","sdk":"1.0","native":"1.0"}', encoding="utf-8")

        def git_stub(_checkout, command, *_args):
            return {"rev-parse": "a" * 40, "status": "", "ls-files": "\0".join(f"SDK/{name}" for name in files)}[command]

        with patch.multiple(sdk_sync, STUDIO=st, SDK=installed, git=git_stub):
            sdk_sync.sync(checkout, verify_tools=False)
        self.assertTrue((installed / "Fonts/.gitkeep").is_file())
        self.assertFalse((installed / "local.key").exists())
        previous = list((st / "_SdkBackups").glob("*/nexvyn_sdk/local.key"))
        self.assertEqual(len(previous), 1)
        self.assertEqual(previous[0].read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
