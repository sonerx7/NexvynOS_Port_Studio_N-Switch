"""Tests for platform_refresh.py: derived capability facts, status labels and the diff."""

import json
import tempfile
import unittest
from pathlib import Path

import platform_refresh as refresh


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RefreshTest(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        root = Path(context.name)
        self.snapshot, self.checkout = root / "snap", root / "os"
        kit = self.snapshot / refresh.KIT
        write(self.snapshot / "VERSION.json", json.dumps({"os": "9.9.9", "sdk": "2.0", "native": "1.3", "nativeAbi": 1}))
        write(kit / "sdk/native/templates/app/x.txt", "")
        write(kit / "tools/nxv_native/__main__.py", 'sub.add_parser("build")\nsub.add_parser("new")\n')
        write(kit / "sdk/native/sysroot/recipes.json", json.dumps({"recipes": {"zstd": {"version": "1"}}, "vendored": {"imgui": {}}}))
        write(kit / "sdk/native/include/nexvyn/nxn_sys.h", "#define NXN_CAP_A (1)\nint nxn_released_call(void);\n")
        write(self.checkout / "sdk/native/templates/vulkan/x.txt", "")
        write(self.checkout / "sdk/native/templates/app/x.txt", "")
        write(self.checkout / "tools/nxv_native/__main__.py", 'sub.add_parser("build")\nsub.add_parser("shader")\n')
        write(self.checkout / "sdk/native/sysroot/recipes.json", json.dumps({"recipes": {"zstd": {"version": "1"}, "volk": {"version": "2"}}}))
        write(self.checkout / "sdk/native/include/nexvyn/nxn_sys.h", "#define NXN_CAP_A (1)\n#define NXN_CAP_B (2)\n")
        write(refresh.progress_log(self.checkout, "n5"),
              "| Execution | 37/44 (84%) |\n| Device-verified | V.4, V.5 and H.2 PASS_DEVICE |\nold: device-verified 0/44\n")
        write(refresh.progress_log(self.checkout, "n4"),
              "| **Execution (ticked)** | **30/32 (93.8%)** | x |\n| **Device-verified** | **0/32** | NOT_RUN |\n")
        self.caps = {"statusLevels": {"released": "", "private-preview": "", "planned": ""}, "asOf": "x", "source": "x",
                     "newApis": [{"symbol": "nxn_released_call", "header": "nxn_sys.h", "evidence": "host", "status": "?"},
                                 {"symbol": "nxn_preview_call", "header": "nxn_sys.h", "evidence": "host", "status": "?"}],
                     "templates": {"app": {"fits": [], "use": ""}}, "libraries": {}}

    def test_released_versus_preview(self):
        new = refresh.refresh(self.caps, self.snapshot, self.checkout, today="2026-01-01")
        self.assertIn("SDK 2.0", new["source"])
        self.assertEqual(new["templates"]["app"]["status"], "released")
        self.assertEqual(new["templates"]["vulkan"]["status"], "private-preview")
        self.assertEqual(new["tools"]["nxv_native"], {"released": ["build", "new"], "preview": ["shader"]})
        self.assertEqual(new["libraries"]["kitRecipes"]["volk"]["status"], "private-preview")
        self.assertEqual(new["libraries"]["kitRecipes"]["imgui"]["status"], "released")
        status = {a["symbol"]: a["status"] for a in new["newApis"]}
        self.assertEqual(status, {"nxn_released_call": "released", "nxn_preview_call": "private-preview"})
        self.assertEqual(new["capabilityBits"], {"released": ["NXN_CAP_A"], "preview": ["NXN_CAP_B"]})
        self.assertEqual(refresh.validate(new), [])

    def test_owner_released_items_stay_released(self):
        caps = dict(self.caps, ownerReleased={"templates": ["vulkan"], "kitRecipes": ["volk"], "newApis": ["nxn_preview_call"],
                                              "capabilityBits": ["NXN_CAP_B"]})
        new = refresh.refresh(caps, self.snapshot, self.checkout, today="2026-01-01")
        self.assertEqual(new["templates"]["vulkan"]["status"], "released")
        self.assertEqual(new["libraries"]["kitRecipes"]["volk"]["status"], "released")
        self.assertEqual({a["symbol"]: a["status"] for a in new["newApis"]}["nxn_preview_call"], "released")
        self.assertEqual(new["capabilityBits"], {"released": ["NXN_CAP_A", "NXN_CAP_B"], "preview": []})
        self.assertEqual(refresh.validate(new), [])

    def test_counters_read_the_dashboard_and_hide_task_names(self):
        counters = refresh.counters(self.checkout)
        self.assertEqual(counters["N5"], {"execution": "37/44", "device": "3 task(s) passed on device"})
        self.assertEqual(counters["N4"], {"execution": "30/32", "device": "0/32"})

    def test_without_checkout_nothing_is_preview(self):
        new = refresh.refresh(self.caps, self.snapshot, None, today="2026-01-01")
        self.assertEqual(new["tools"]["nxv_native"]["preview"], [])
        self.assertNotIn("deviceValidation", new)

    def test_validate_flags_missing_status_and_diff_lists_changes(self):
        broken = dict(self.caps, templates={"x": {"status": "maybe"}})
        self.assertTrue(any("templates.x" in p for p in refresh.validate(broken)))
        self.assertIn("~ a: 1 -> 2", refresh.diff({"a": 1}, {"a": 2}))

    def test_repository_file_is_valid(self):
        caps = json.loads(refresh.CAPABILITIES.read_text(encoding="utf-8"))
        self.assertEqual(refresh.validate(caps), [])


if __name__ == "__main__":
    unittest.main()
