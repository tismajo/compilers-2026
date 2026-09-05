"""Coverage report for the compiler, using only the standard library.

The project may not install extra tooling, so this uses ``trace`` instead of a
third-party coverage package.

    ./.venv/Scripts/python.exe tests/coverage_report.py
    ./.venv/Scripts/python.exe tests/coverage_report.py --output cobertura
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import trace
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "program"
TESTS = ROOT / "tests"
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(TESTS))


def run_suite() -> unittest.TestResult:
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS), top_level_dir=str(TESTS))
    runner = unittest.TextTestRunner(verbosity=1, stream=sys.stderr)
    return runner.run(suite)


def main(argv: list[str] | None = None) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Coverage report of the compiler")
    parser.add_argument(
        "--output",
        default=None,
        help="Directory for the annotated .cover files (default: a temporary one)",
    )
    args = parser.parse_args(argv)

    tracer = trace.Trace(
        count=1,
        trace=0,
        ignoredirs=[sys.prefix, sys.exec_prefix, str(TESTS)],
    )
    result = tracer.runfunc(run_suite)

    directory = args.output or tempfile.mkdtemp(prefix="compiscript-cover-")
    Path(directory).mkdir(parents=True, exist_ok=True)
    print(f"\nCobertura por módulo (archivos anotados en {directory}):\n")
    tracer.results().write_results(show_missing=True, summary=True, coverdir=directory)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
