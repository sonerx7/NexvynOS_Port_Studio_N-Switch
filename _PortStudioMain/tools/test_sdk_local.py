"""Tests for the local-checkout comparison (sdk_local.py) and the released snapshot's header/ABI consistency."""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import port_studio as studio
import sdk_local

KIT = Path("Languages/c/native-kit/sdk/native")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LocalCompareTest(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        root = Path(context.name)
        self.checkout, self.snapshot = root / "os", root / "snap"
        abi_old = json.dumps({"functions": [{"name": "nxn_a"}]})
        abi_new = json.dumps({"functions": [{"name": "nxn_a"}, {"name": "nxn_b"}]})
        for base, abi, extra in ((self.snapshot / KIT, abi_old, False), (self.checkout / "sdk/native", abi_new, True)):
            write(base / "include/nexvyn/same.h", "int x;\n")
            write(base / "include/nexvyn/comment.h", "/* old path */\nint y;\n" if not extra else "/* new path */\nint y;\n")
            write(base / "include/nexvyn/api.h", "int a(void);\n" if not extra else "int a(void);\nint b(void);\n")
            write(base / "toolchain/nxn_abi_v1.json", abi)
        write(self.checkout / "sdk/native/include/nexvyn/nxn_new.h", "int n;\n")
        write(self.checkout / "sdk/native/lib/libx.a", "binary")
        write(self.checkout / "sdk/native/compat/tests/t.c", "test")
        write(self.snapshot / "VERSION.json", "{}")
        for command in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"]):
            subprocess.run(["git", "-C", str(self.checkout), *command], check=True)

    def test_classifies_folders_and_new_abi(self):
        result = sdk_local.compare(self.checkout, self.snapshot)
        include = result["folders"]["include"]
        self.assertEqual(include["identical"], ["include/nexvyn/same.h"])
        self.assertEqual(include["comment"], ["include/nexvyn/comment.h"])
        self.assertEqual(include["changed"], ["include/nexvyn/api.h"])
        self.assertEqual(include["new"], ["include/nexvyn/nxn_new.h"])
        self.assertEqual(result["newAbiFunctions"], ["nxn_b"])
        everything = [rel for folder in result["folders"].values() for kind in folder.values() for rel in kind]
        self.assertNotIn("lib/libx.a", everything)          # prebuilt binaries never compared or staged
        self.assertNotIn("compat/tests/t.c", everything)    # tests stay private

    def test_stage_marks_preview_and_build_refuses_it(self):
        result = sdk_local.compare(self.checkout, self.snapshot)
        target = sdk_local.stage(result, self.snapshot, self.snapshot.parent / "cands")
        source = json.loads((target / "STUDIO_SOURCE.json").read_text(encoding="utf-8"))
        self.assertEqual(source["status"], "private-preview")
        self.assertNotIn(str(self.checkout), (target / "STUDIO_SOURCE.json").read_text(encoding="utf-8"))
        self.assertTrue((target / KIT / "include/nexvyn/nxn_new.h").is_file())
        self.assertIsNotNone(studio.sdk_problem(studio.sdk_report(target)))
        with self.assertRaises(ValueError):
            sdk_local.stage(result, self.snapshot, self.snapshot.parent / "cands")   # never overwrites

    def test_stage_refuses_removed_abi(self):
        write(self.checkout / "sdk/native/toolchain/nxn_abi_v1.json", json.dumps({"functions": []}))
        subprocess.run(["git", "-C", str(self.checkout), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "y"], check=True)
        result = sdk_local.compare(self.checkout, self.snapshot)
        self.assertEqual(result["removedAbiFunctions"], ["nxn_a"])
        with self.assertRaises(ValueError):
            sdk_local.stage(result, self.snapshot, self.snapshot.parent / "cands")


class ReleasedSnapshotTest(unittest.TestCase):
    """Golden checks on the bundled released snapshot."""

    def test_abi_functions_are_declared_in_headers(self):
        include = studio.SDK / KIT / "include" / "nexvyn"
        abi = json.loads((studio.SDK / KIT / "toolchain" / "nxn_abi_v1.json").read_text(encoding="utf-8"))
        headers = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in include.glob("*.h"))
        names = [f["name"] if isinstance(f, dict) else f for f in abi["functions"]]
        missing = [n for n in names if not re.search(rf"\b{re.escape(n)}\s*\(", headers)]
        self.assertEqual(missing, [])

    def test_versions_agree(self):
        versions = json.loads((studio.SDK / "VERSION.json").read_text(encoding="utf-8"))
        base = (studio.SDK / KIT / "include" / "nexvyn" / "nxn_base.h").read_text(encoding="utf-8")
        major = re.search(r"#define NXN_VERSION_MAJOR\s+(\d+)", base).group(1)
        minor = re.search(r"#define NXN_VERSION_MINOR\s+(\d+)", base).group(1)
        self.assertEqual(versions["native"], f"{major}.{minor}")
        abi_gen = re.search(r"#define NXN_ABI_GEN\s+(\d+)", base).group(1)
        self.assertEqual(str(versions["nativeAbi"]), abi_gen)


if __name__ == "__main__":
    unittest.main()
