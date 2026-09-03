from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "program"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(PROGRAM))

try:
    from Driver import analyze_file  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name != "antlr4":
        raise
    analyze_file = None


@unittest.skipIf(analyze_file is None, "ANTLR Python runtime is not installed")
class SyntaxAnalysisTests(unittest.TestCase):
    def assert_valid(self, fixture: str) -> None:
        result = analyze_file(FIXTURES / "valid" / fixture)
        self.assertTrue(result.success, result.diagnostics)

    def assert_invalid(self, fixture: str, code: str) -> None:
        result = analyze_file(FIXTURES / "invalid" / fixture)
        self.assertFalse(result.success)
        self.assertIn(code, {item.code for item in result.diagnostics})

    def test_official_program_is_valid(self) -> None:
        result = analyze_file(PROGRAM / "program.cps")
        self.assertTrue(result.success, result.diagnostics)

    def test_float_and_property_assignment_are_valid(self) -> None:
        self.assert_valid("float_and_assignment.cps")

    def test_missing_semicolon_is_invalid(self) -> None:
        self.assert_invalid("missing_semicolon.cps", "SYN001")

    def test_unknown_character_is_invalid(self) -> None:
        self.assert_invalid("unknown_character.cps", "LEX001")


if __name__ == "__main__":
    unittest.main()
