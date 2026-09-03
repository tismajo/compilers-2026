from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = ROOT / "program" / "Compiscript.g4"
JAR = ROOT / "antlr-4.13.1-complete.jar"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def java_environment() -> dict[str, str]:
    environment = os.environ.copy()
    java = shutil.which("java")
    if java:
        java_home = Path(java).resolve().parent.parent
        library_paths = [java_home / "lib", java_home / "lib" / "server"]
        previous = environment.get("LD_LIBRARY_PATH")
        if previous:
            library_paths.append(Path(previous))
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(map(str, library_paths))
    return environment


def interpret(source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "java",
            "-cp",
            str(JAR),
            "org.antlr.v4.gui.Interpreter",
            str(GRAMMAR),
            "program",
            str(source),
        ],
        cwd=ROOT,
        env=java_environment(),
        check=False,
        capture_output=True,
        text=True,
    )


@unittest.skipUnless(shutil.which("java") and JAR.is_file(), "Java/ANTLR unavailable")
class GrammarTests(unittest.TestCase):
    def assert_valid(self, source: Path) -> None:
        result = interpret(source)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr, result.stderr)

    def assert_invalid(self, fixture: str, expected: str) -> None:
        result = interpret(FIXTURES / "invalid" / fixture)
        self.assertIn(expected, result.stderr)

    def test_official_program_is_valid(self) -> None:
        self.assert_valid(ROOT / "program" / "program.cps")

    def test_float_and_property_assignment_are_valid(self) -> None:
        self.assert_valid(FIXTURES / "valid" / "float_and_assignment.cps")

    def test_missing_semicolon_is_rejected(self) -> None:
        self.assert_invalid("missing_semicolon.cps", "missing ';'")

    def test_unknown_character_is_rejected(self) -> None:
        self.assert_invalid("unknown_character.cps", "token recognition error")


if __name__ == "__main__":
    unittest.main()
