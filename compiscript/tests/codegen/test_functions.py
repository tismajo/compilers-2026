"""Functions, activation records, addresses and the failing cases."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
import unittest.mock

from support import FIXTURES, TacTestCase

from Driver import main
import tac

FACTORIAL = (
    "function factorial(n: integer): integer {\n"
    "  if (n <= 1) { return 1; }\n"
    "  return n * factorial(n - 1);\n"
    "}\n"
    "print(factorial(5));\n"
)


class CallTests(TacTestCase):
    def test_recursive_call(self) -> None:
        code = self.code(FACTORIAL, "f_factorial")
        self.assertEqual(
            [
                "t0 = n <= 1",
                "ifFalse t0 goto L0",
                "return 1",
                "L0:",
                "t0 = n - 1",
                "param t0",
                "t0 = call f_factorial, 1",
                "t0 = n * t0",
                "return t0",
            ],
            code,
        )

    def test_main_calls_the_function(self) -> None:
        code = self.code(FACTORIAL)
        self.assertEqual(["param 5", "t0 = call f_factorial, 1", "print t0"], code)

    def test_arguments_are_evaluated_before_any_param(self) -> None:
        source = (
            "function add(a: integer, b: integer): integer { return a + b; }\n"
            "print(add(add(1, 2), 3));\n"
        )
        code = self.code(source)
        self.assertEqual(
            [
                "param 1",
                "param 2",
                "t0 = call f_add, 2",
                "param t0",
                "param 3",
                "t0 = call f_add, 2",
                "print t0",
            ],
            code,
        )

    def test_void_call_has_no_result(self) -> None:
        source = "function hello(): void { print(1); }\nhello();\n"
        self.assertEqual(["call f_hello, 0"], self.code(source))

    def test_nested_function_gets_its_own_label(self) -> None:
        source = (
            "function outer(x: integer): integer {\n"
            "  function twice(z: integer): integer { return z * 2; }\n"
            "  return twice(x);\n"
            "}\n"
        )
        self.assertIn("t0 = call f_outer_twice, 1", self.code(source, "f_outer"))


class LayoutTests(TacTestCase):
    SOURCE = (
        "let total: integer = 0;\n"
        "let ratio: float = 1.5;\n"
        "function f(a: integer, b: float): integer {\n"
        "  let x: integer = a;\n"
        "  { let x: integer = 2; print(x); }\n"
        "  return x + total;\n"
        "}\n"
    )

    def test_globals_live_in_the_data_segment(self) -> None:
        result = self.generate(self.SOURCE)
        scope = result.symbols.global_scope
        total = scope.resolve_local("total")
        ratio = scope.resolve_local("ratio")
        self.assertEqual(("global", 0, 4), (total.storage, total.offset, total.size))
        self.assertEqual(("global", 4, 8), (ratio.storage, ratio.offset, ratio.size))
        self.assertEqual(12, result.symbols.globals_size)
        self.assertEqual("f_f", scope.resolve_local("f").label)

    def test_activation_record_of_a_function(self) -> None:
        result = self.generate(self.SOURCE)
        frame = self.frame(result, "f_f")
        self.assertEqual([("a", 8, 4), ("b", 12, 8)], [
            (item.name, item.offset, item.size) for item in frame.parameters
        ])
        # The shadowed ``x`` gets its own slot below the first one.
        self.assertEqual([("x", -4), ("x", -8)], [
            (item.name, item.offset) for item in frame.locals
        ])
        self.assertEqual(1, frame.temps)
        self.assertEqual(8 + 8 + 4, frame.frame_size)
        begin = result.tac.function("f_f").quads[0].render()
        self.assertEqual("begin_func 20", begin)

    def test_reading_a_global_is_not_a_capture(self) -> None:
        result = self.generate(self.SOURCE)
        self.assertEqual([], result.symbols.global_scope.resolve_local("f").captured)

    def test_object_layout_puts_inherited_attributes_first(self) -> None:
        source = (
            "class A { let x: integer; }\n"
            "class B : A { let y: float; }\n"
        )
        result = self.generate(source)
        a = result.symbols.lookup_class("A")
        b = result.symbols.lookup_class("B")
        self.assertEqual(4, a.attributes["x"].offset)
        self.assertEqual(8, b.attributes["y"].offset)
        self.assertEqual((8, 16), (a.size, b.size))

    def test_method_frame_receives_this_first(self) -> None:
        source = "class A { function get(k: integer): integer { return k; } }\n"
        frame = self.frame(self.generate(source), "A_get")
        self.assertEqual(["this", "k"], [item.name for item in frame.parameters])


class FailingTests(TacTestCase):
    INVALID = "let x: integer = \"texto\";\n"

    def test_program_with_semantic_errors_produces_no_tac(self) -> None:
        result = self.analyze(self.INVALID)
        self.assertFalse(result.success)
        self.assertIsNone(result.generate_tac())
        self.assertIsNone(result.symbols.globals_size)

    def test_generator_refuses_an_invalid_program(self) -> None:
        result = self.analyze(self.INVALID)
        with self.assertRaises(ValueError):
            tac.generate(result.tree, result.semantic)

    def test_cli_reports_errors_and_skips_tac(self) -> None:
        source = FIXTURES / "invalid" / "muestra_por_grupo.cps"
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(1, main([str(source), "--tac", "text"]))
        self.assertIn("No se generó código intermedio", errors.getvalue())

    def test_cli_json_includes_tac_and_frames(self) -> None:
        source = FIXTURES / "valid" / "float_and_assignment.cps"
        with unittest.mock.patch("builtins.print") as fake_print:
            self.assertEqual(
                0, main([str(source), "--format", "json", "--tac", "json", "--symbols", "json"])
            )
        payload = json.loads(fake_print.call_args_list[-1].args[0])
        self.assertIn("text", payload["tac"])
        self.assertEqual("main", payload["tac"]["functions"][0]["label"])
        self.assertEqual("main", payload["symbols"]["activationRecords"][0]["label"])


if __name__ == "__main__":
    unittest.main()
