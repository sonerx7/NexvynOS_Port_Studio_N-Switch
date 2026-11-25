"""Run every Port Studio test with one command.

  python _PortStudioMain/tools/run_tests.py [-v] [pattern]

Host only: no emulator, no device, no network. Exit code 0 when every test passes.
"""

import sys
import unittest
from pathlib import Path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    verbosity = 2 if "-v" in argv else 1
    argv = [a for a in argv if a != "-v"]
    pattern = argv[0] if argv else "test_*.py"
    tools = Path(__file__).resolve().parent
    sys.path.insert(0, str(tools))
    suite = unittest.defaultTestLoader.discover(str(tools), pattern=pattern, top_level_dir=str(tools))
    result = unittest.TextTestRunner(verbosity=verbosity, buffer=True).run(suite)
    print(f"Host tests: {result.testsRun} run, {len(result.failures)} failed, {len(result.errors)} errors, "
          f"{len(result.skipped)} skipped.")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
