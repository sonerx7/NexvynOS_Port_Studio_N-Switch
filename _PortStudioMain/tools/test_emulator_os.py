"""Rule: the emulator always runs the newest Nexvyn OS known on this machine (emulator_test.find_nro)."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import emulator_test as emu


class NewestOsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        (self.cache / "NexvynOS.nro").write_bytes(b"public 1.3")
        (self.cache / "os_version.txt").write_text("v1.3.28-beta.2", encoding="utf-8")
        self.checkout = self.root / "os"
        for patcher in (patch.object(emu, "CACHE", self.cache),
                        patch.object(emu, "LOCAL_CONFIG", self.root / "studio_local.json"),
                        patch.dict("os.environ", {"NEXVYN_OS_CHECKOUT": str(self.checkout), "NEXVYN_NRO": ""})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def release(self, version, data=b"os build", good_sum=True):
        folder = self.checkout / "build" / f"release-{version}"
        folder.mkdir(parents=True)
        (folder / "NexvynOS.nro").write_bytes(data)
        digest = hashlib.sha256(data if good_sum else b"other").hexdigest()
        (folder / "SHA256SUMS").write_text(f"{digest} *NexvynOS.nro\n", encoding="utf-8")
        return folder / "NexvynOS.nro"

    def test_version_order(self):
        order = ["v1.3.27", "v1.3.28-beta.2", "1.3.28", "1.4.0-rc1", "1.4.0", "1.10.0"]
        self.assertEqual(sorted(order, key=emu.os_version_tuple), order)

    def test_local_release_newer_than_public_is_chosen(self):
        newer = self.release("1.4.0")
        self.assertEqual(emu.find_nro(refresh=False), newer)
        self.assertEqual(emu.LAST_OS["version"], "1.4.0")

    def test_public_cache_wins_when_it_is_newer(self):
        self.release("1.3.20")
        self.assertEqual(emu.find_nro(refresh=False), self.cache / "NexvynOS.nro")

    def test_build_with_wrong_checksum_is_ignored(self):
        self.release("1.4.0", good_sum=False)
        self.assertEqual(emu.find_nro(refresh=False), self.cache / "NexvynOS.nro")

    def test_explicit_nro_wins_but_is_reported(self):
        self.release("1.4.0")
        explicit = self.root / "old.nro"
        explicit.write_bytes(b"old")
        with patch("sys.stderr") as err:
            self.assertEqual(emu.find_nro(str(explicit), refresh=False), explicit)
        self.assertIn("newest known Nexvyn OS is 1.4.0", "".join(c.args[0] for c in err.write.call_args_list))

    def test_public_release_newer_than_cache_is_downloaded(self):
        with patch.object(emu, "public_latest_tag", return_value="v1.4.1"), \
             patch.object(emu, "fetch_os", side_effect=lambda: (self.cache / "os_version.txt").write_text("v1.4.1")) as fetch:
            emu.find_nro()
        fetch.assert_called_once()
        self.assertEqual(emu.LAST_OS["version"], "v1.4.1")

    def test_ryujinx_path_is_remembered_locally(self):
        exe = self.root / "ryu" / "Ryujinx.exe"
        exe.parent.mkdir()
        exe.write_bytes(b"")
        with patch.dict("os.environ", {"RYUJINX_EXE": ""}), patch("shutil.which", return_value=None), \
             patch.object(emu, "known_ryujinx_places", return_value=[exe]):
            self.assertEqual(emu.find_ryujinx(), exe)
        self.assertEqual(json.loads((self.root / "studio_local.json").read_text())["ryujinx"], str(exe))


class ProfileLockTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        profile = Path(tmp.name) / ".emulator_profile"
        patcher = patch.object(emu, "PROFILE", profile)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.lock = profile.parent / ".emulator_profile.lock"

    def test_second_taker_is_refused_while_the_holder_lives(self):
        self.lock.write_text("4242")
        with patch.object(emu, "pid_alive", return_value=True):
            self.assertIsNone(emu.acquire_profile_lock())

    def test_stale_lock_is_replaced_atomically(self):
        self.lock.write_text("4242")
        with patch.object(emu, "pid_alive", return_value=False):
            self.assertEqual(emu.acquire_profile_lock(), self.lock)
        self.assertEqual(self.lock.read_text(), str(__import__("os").getpid()))

    def test_free_profile_is_taken(self):
        self.assertEqual(emu.acquire_profile_lock(), self.lock)


if __name__ == "__main__":
    unittest.main()
