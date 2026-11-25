"""Tests for market_release.py: item naming and the release gate (it never uploads)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import market_release


class MarketReleaseTest(unittest.TestCase):
    def test_item_name_is_search_friendly(self):
        self.assertEqual(market_release.suggested_item(Path("x/GamePorts/RedAlert2")), "nexvyn-os-nx-redalert2-game-port")
        self.assertEqual(market_release.suggested_item(Path("x/SoftwarePorts/chromium-nx")), "nexvyn-os-nx-chromium-nx-app")

    def test_blocked_port_stops_before_any_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp) / "GamePorts" / "demo"
            port.mkdir(parents=True)
            (port / "port.json").write_text(json.dumps({"release": {"status": "blocked", "reasons": ["rights"]}}))
            with patch.object(market_release, "run") as run:
                self.assertEqual(market_release.main([str(port)]), 1)
            run.assert_not_called()

    def test_never_passes_yes_or_full_package(self):
        source = Path(market_release.__file__).read_text(encoding="utf-8")
        code = source.split('"""', 2)[2]  # skip the docstring, which explains the rule
        self.assertNotIn('"--yes"', code)
        self.assertNotIn('"--full-package"', code)


if __name__ == "__main__":
    unittest.main()
