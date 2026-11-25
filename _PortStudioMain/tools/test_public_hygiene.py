"""The Studio repository is public: its docs and data carry no private OS-source markers and no trademark word."""

import re
import unittest
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
ROOT = STUDIO.parent
SCANNED = [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "FIRST_RUN.md", STUDIO / "README.md", STUDIO / "CHANGELOG.md"]
SCANNED_DIRS = [STUDIO / "docs", STUDIO / "platform", STUDIO / "profiles", STUDIO / "templates"]
# The names of private OS-source files and folders are not written here (this repository is public): they live in the
# git-ignored _LocalData/private_markers.txt, one regex per line. Without that file a generic pattern still catches
# internal plan documents (upper-case plan prefix plus .md) and numbered plan folders.
LOCAL_MARKERS = ROOT / "_LocalData" / "private_markers.txt"
GENERIC = r"\b[A-Z]\d_[A-Z][A-Z_]*\.md\b|/current/[a-z]\d\b"


def private_pattern():
    local = []
    if LOCAL_MARKERS.is_file():
        local = [line.strip() for line in LOCAL_MARKERS.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
    return re.compile("|".join([GENERIC, *local]))


PRIVATE = private_pattern()
TRADEMARK = re.compile(r"nintendo", re.I)


def files():
    found = [p for p in SCANNED if p.is_file()]
    for folder in SCANNED_DIRS:
        found += [p for p in folder.rglob("*") if p.is_file() and p.suffix in {".md", ".json", ".txt", ".h", ".cmake"}]
    return found


class PublicHygieneTest(unittest.TestCase):
    def test_no_private_markers_or_trademark(self):
        problems = []
        for path in files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern, label in ((PRIVATE, "private marker"), (TRADEMARK, "trademark word")):
                match = pattern.search(text)
                if match:
                    problems.append(f"{path.relative_to(ROOT)}: {label} {match.group(0)!r}")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
