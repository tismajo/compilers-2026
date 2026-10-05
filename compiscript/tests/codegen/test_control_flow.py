"""Control flow: labels and jumps for conditionals and loops."""

from __future__ import annotations

import unittest

from support import TacTestCase


class ConditionalTests(TacTestCase):
    def test_if_without_else(self) -> None:
        code = self.code("let a: integer = 1;\nif (a > 0) { print(a); }")
        self.assertEqual(
            ["a = 1", "t0 = a > 0", "ifFalse t0 goto L0", "print a", "L0:"],
            code,
        )

    def test_if_with_else(self) -> None:
        code = self.code("let a: integer = 1;\nif (a > 0) { print(1); } else { print(2); }")
        self.assertEqual(
            [
                "a = 1",
                "t0 = a > 0",
                "ifFalse t0 goto L0",
                "print 1",
                "goto L1",
                "L0:",
                "print 2",
                "L1:",
            ],
            code,
        )


class LoopTests(TacTestCase):
    def test_while_with_break_and_continue(self) -> None:
        source = (
            "let i: integer = 0;\n"
            "while (i < 10) {\n"
            "  i = i + 1;\n"
            "  if (i == 2) { continue; }\n"
            "  if (i == 5) { break; }\n"
            "}\n"
        )
        code = self.code(source)
        self.assertEqual("L0:", code[1])
        self.assertEqual("ifFalse t0 goto L1", code[3])
        # continue goes back to the condition, break leaves the loop.
        self.assertIn("goto L0", code[code.index("ifFalse t0 goto L2") + 1])
        self.assertIn("goto L1", code[code.index("ifFalse t0 goto L3") + 1])
        self.assertEqual(["goto L0", "L1:"], code[-2:])

    def test_do_while_jumps_back_while_true(self) -> None:
        code = self.code("let i: integer = 0;\ndo { i = i + 1; } while (i < 3);")
        self.assertEqual(
            [
                "i = 0",
                "L0:",
                "t0 = i + 1",
                "i = t0",
                "L1:",
                "t0 = i < 3",
                "if t0 goto L0",
                "L2:",
            ],
            code,
        )

    def test_for_continue_runs_the_step(self) -> None:
        source = (
            "for (let i: integer = 0; i < 3; i = i + 1) {\n"
            "  if (i == 1) { continue; }\n"
            "  print(i);\n"
            "}\n"
        )
        code = self.code(source)
        self.assertEqual(["i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L2"], code[:4])
        self.assertIn("goto L1", code)  # continue
        step = code.index("L1:")
        self.assertEqual(["t0 = i + 1", "i = t0", "goto L0", "L2:"], code[step + 1 :])

    def test_for_with_empty_initializer_keeps_its_condition(self) -> None:
        code = self.code("let k: integer = 0;\nfor (; k < 3; k = k + 1) { print(k); }")
        self.assertIn("t0 = k < 3", code)
        self.assertIn("ifFalse t0 goto L2", code)


if __name__ == "__main__":
    unittest.main()
