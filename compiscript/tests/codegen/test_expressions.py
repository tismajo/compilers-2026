"""Expressions: arithmetic, conversions, temporaries and short-circuit logic."""

from __future__ import annotations

import unittest

from support import TacTestCase

DECLARATIONS = (
    "let a: integer = 1;\n"
    "let b: integer = 2;\n"
    "let c: integer = 3;\n"
    "let d: integer = 4;\n"
)


class ArithmeticTests(TacTestCase):
    def test_precedence_and_temporary_recycling(self) -> None:
        result = self.generate(DECLARATIONS + "let r: integer = a + b * c - d;")
        code = [quad.render() for quad in result.tac.function("main").quads][5:9]
        self.assertEqual(
            ["t0 = b * c", "t0 = a + t0", "t0 = t0 - d", "r = t0"],
            code,
        )
        # Three operations, a single temporary thanks to recycling.
        self.assertEqual(1, self.frame(result, "main").temps)

    def test_independent_subexpressions_need_two_temporaries(self) -> None:
        result = self.generate(DECLARATIONS + "let r: integer = (a + b) * (c - d);")
        code = [quad.render() for quad in result.tac.function("main").quads]
        # LIFO pool: the last released temporary (t1) holds the result.
        self.assertIn("t1 = t0 * t1", code)
        self.assertEqual(2, self.frame(result, "main").temps)

    def test_integer_is_promoted_in_float_operations(self) -> None:
        code = self.code("let a: integer = 1;\nlet f: float = a * 2.5;")
        self.assertEqual(["a = 1", "t0 = itof a", "t0 = t0 * 2.5", "f = t0"], code)

    def test_integer_assigned_to_float_is_converted(self) -> None:
        code = self.code("let f: float = 3;")
        self.assertEqual(["t0 = itof 3", "f = t0"], code)

    def test_concatenation_converts_the_non_string_side(self) -> None:
        code = self.code('let n: integer = 5;\nprint("n = " + n);')
        self.assertEqual(
            ["n = 5", "t0 = tostr n", 't0 = concat "n = ", t0', "print t0"],
            code,
        )

    def test_unary_operators(self) -> None:
        code = self.code("let a: integer = 1;\nlet b: integer = -a;\nlet c: boolean = !true;")
        self.assertIn("t0 = - a", code)
        self.assertIn("t0 = ! true", code)


class LogicTests(TacTestCase):
    def test_and_skips_the_right_operand_when_false(self) -> None:
        code = self.code(DECLARATIONS + "let ok: boolean = a < b && c < d;")
        self.assertEqual(
            [
                "t0 = a < b",
                "ifFalse t0 goto L0",
                "t1 = c < d",
                "t0 = t1",
                "L0:",
                "ok = t0",
            ],
            code[4:],
        )

    def test_or_skips_the_right_operand_when_true(self) -> None:
        code = self.code(DECLARATIONS + "let ok: boolean = a < b || c < d;")
        self.assertIn("if t0 goto L0", code)

    def test_ternary_writes_both_branches_into_one_temporary(self) -> None:
        code = self.code(DECLARATIONS + "let m: integer = a > b ? a : b;")
        self.assertEqual(
            [
                "t0 = a > b",
                "ifFalse t0 goto L0",
                "t0 = a",
                "goto L1",
                "L0:",
                "t0 = b",
                "L1:",
                "m = t0",
            ],
            code[4:],
        )


class DeclarationTests(TacTestCase):
    def test_uninitialized_variables_get_the_zero_value(self) -> None:
        code = self.code("let n: integer;\nlet s: string;\nlet b: boolean;\nlet f: float;")
        self.assertEqual(["n = 0", 's = ""', "b = false", "f = 0.0"], code)

    def test_shadowed_variable_gets_its_own_name(self) -> None:
        code = self.code("let x: integer = 1;\n{ let x: integer = 2; print(x); }\nprint(x);")
        self.assertEqual(["x = 1", "x#2 = 2", "print x#2", "print x"], code)

    def test_user_name_that_looks_like_a_temporary_is_renamed(self) -> None:
        code = self.code("let t0: integer = 1;\nprint(t0 + 1);")
        self.assertEqual(["t0#v = 1", "t0 = t0#v + 1", "print t0"], code)


if __name__ == "__main__":
    unittest.main()
