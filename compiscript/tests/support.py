"""Shared helpers for the Compiscript test suite.

Assertions compare diagnostic **codes, severities and positions**, never the
full message text, so wording changes do not break the suite.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "program"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(PROGRAM))

try:
    from Driver import analyze_file  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
    if exc.name != "antlr4":
        raise
    analyze_file = None


requires_runtime = unittest.skipIf(
    analyze_file is None, "ANTLR Python runtime is not installed"
)


def analyze_code(source: str) -> Any:
    """Analyze a snippet through the real CLI entry point."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".cps", encoding="utf-8", delete=False
    ) as handle:
        handle.write(source)
        temporary = Path(handle.name)
    try:
        return analyze_file(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def codes(result: Any) -> set[str]:
    return {item.code for item in result.diagnostics}


@requires_runtime
class SemanticTestCase(unittest.TestCase):
    """Base class with the two assertions every semantic test needs."""

    def analyze(self, source: str) -> Any:
        return analyze_code(source)

    def assert_ok(self, source: str) -> Any:
        """The snippet must produce no errors; warnings are allowed."""
        result = self.analyze(source)
        errors = [item.as_dict() for item in result.diagnostics if item.severity == "error"]
        self.assertEqual([], errors)
        return result

    def assert_diagnostic(
        self,
        source: str,
        code: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        severity: str = "error",
    ) -> Any:
        """The snippet must report ``code`` with the expected severity/position."""
        result = self.analyze(source)
        matches = [item for item in result.diagnostics if item.code == code]
        self.assertTrue(
            matches,
            f"se esperaba {code}, se obtuvo {sorted(codes(result))}",
        )
        self.assertEqual(severity, matches[0].severity)
        if line is not None:
            self.assertEqual(line, matches[0].line)
        if column is not None:
            self.assertEqual(column, matches[0].column)
        expected_success = severity != "error"
        self.assertEqual(expected_success, result.success)
        return result


@requires_runtime
class TacTestCase(SemanticTestCase):
    """Generates three-address code through the same entry point as the CLI."""

    def generate(self, source: str) -> Any:
        result = self.assert_ok(source)
        self.assertIsNotNone(result.generate_tac())
        return result

    def code(self, source: str, label: str = "main") -> list[str]:
        """Instructions of one function, without its header and frame markers."""
        function = self.generate(source).tac.function(label)
        self.assertIsNotNone(function, f"no se generó la función {label}")
        return [
            quad.render()
            for quad in function.quads
            if quad.op not in ("begin_func", "end_func")
        ]

    def frame(self, result: Any, label: str) -> Any:
        return next(
            item for item in result.symbols.activation_records if item.label == label
        )
