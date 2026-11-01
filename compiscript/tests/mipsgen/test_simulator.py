"""Runs the generated MIPS for real in MARS and checks its actual output —
the only thing that proves "funcional y simulado en un simulador de MIPS"
(60 of the 100 points this phase is worth), not just that the text looks
plausible.

Skips automatically if ``java`` is not on PATH or ``Mars.jar`` has not been
vendored at the repo root, the same way ``tests/test_grammar.py`` skips
without Java — see ``docs/generacion-mips.md`` for how to get ``Mars.jar``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401 - importing it puts ``program/`` on sys.path

import mips

MARS_JAR = support.ROOT / "Mars.jar"
JAVA = shutil.which("java")

requires_mars = unittest.skipUnless(
    JAVA is not None and MARS_JAR.is_file(),
    "Java or Mars.jar is not available (see docs/generacion-mips.md)",
)


def run_in_mars(asm_text: str) -> str:
    """Assemble and run ``asm_text`` in MARS, return what the program
    printed. Raises ``AssertionError`` with MARS's own error text if it
    fails to assemble or crashes during simulation."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".asm", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(asm_text)
        path = Path(handle.name)
    try:
        result = subprocess.run(
            [JAVA, "-jar", str(MARS_JAR), "nc", "sm", "ae1", "se1", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"MARS terminó con código {result.returncode}:\n{result.stdout}{result.stderr}"
            )
        # MARS appends one trailing newline of its own after the simulated
        # program finishes, regardless of whether the program itself printed
        # one — not something the generated code controls, so it is not part
        # of what these tests compare.
        return result.stdout.rstrip("\n")
    finally:
        path.unlink(missing_ok=True)


@requires_mars
class MarsTestCase(unittest.TestCase):
    def run_source(self, source: str) -> str:
        result = support.analyze_code(source)
        self.assertTrue(result.success, result.diagnostics)
        tac_program = result.generate_tac()
        mips_program = mips.generate(tac_program, result.symbols)
        return run_in_mars(mips_program.render())


class ArithmeticTests(MarsTestCase):
    def test_recursive_factorial(self) -> None:
        source = (
            "function factorial(n: integer): integer {\n"
            "  if (n <= 1) { return 1; }\n"
            "  return n * factorial(n - 1);\n"
            "}\n"
            "print(factorial(5));\n"
        )
        self.assertEqual("120", self.run_source(source))

    def test_negative_arithmetic_prints_the_sign(self) -> None:
        source = "let x: integer = 3 - 10;\nprint(x);\nprint(\"neg: \" + x);\n"
        self.assertEqual("-7neg: -7", self.run_source(source))

    def test_float_arithmetic(self) -> None:
        source = "let a: float = 1.5;\nlet b: float = 2.25;\nprint(a + b);\n"
        self.assertEqual("3.75", self.run_source(source))


class ControlFlowTests(MarsTestCase):
    def test_if_else_join_reads_the_branch_that_actually_ran(self) -> None:
        source = (
            "let x: integer = 0;\n"
            "if (x == 0) { x = 1; } else { x = 2; }\n"
            "print(x);\n"
        )
        self.assertEqual("1", self.run_source(source))

    def test_while_loop(self) -> None:
        source = "let i: integer = 0;\nwhile (i < 5) { i = i + 1; }\nprint(i);\n"
        self.assertEqual("5", self.run_source(source))

    def test_sibling_blocks_shadowing_the_same_global_name(self) -> None:
        source = (
            "for (let i: integer = 0; i < 2; i = i + 1) { print(i); }\n"
            "for (let i: integer = 10; i < 12; i = i + 1) { print(i); }\n"
        )
        self.assertEqual("011011", self.run_source(source))


class StringAndBooleanTests(MarsTestCase):
    def test_tostr_and_concat(self) -> None:
        source = 'let x: integer = 5;\nprint("x = " + x);\n'
        self.assertEqual("x = 5", self.run_source(source))

    def test_chained_concat_does_not_corrupt_an_earlier_result(self) -> None:
        # The scenario that ruled out a shared static scratch buffer for
        # concat's result: each call must get its own fresh memory (alloc,
        # not a reused buffer), or the second concat here would silently
        # overwrite bytes the first one's caller (msg) still points to.
        source = (
            "let a: integer = 1;\n"
            "let b: integer = 2;\n"
            "let c: integer = 3;\n"
            'let msg: string = "a=" + a + " b=" + b + " c=" + c;\n'
            "print(msg);\n"
            'print("again: " + msg);\n'
        )
        self.assertEqual("a=1 b=2 c=3again: a=1 b=2 c=3", self.run_source(source))

    def test_zero_prints_as_zero_not_an_empty_sign(self) -> None:
        source = 'let z: integer = 0;\nprint("cero: " + z);\n'
        self.assertEqual("cero: 0", self.run_source(source))

    def test_boolean_print(self) -> None:
        self.assertEqual("truefalse", self.run_source("print(true);\nprint(false);\n"))


if __name__ == "__main__":
    unittest.main()
