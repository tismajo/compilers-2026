"""Functions: arguments, returns, recursion, nesting and closures."""

from __future__ import annotations

import unittest

from support import SemanticTestCase


class CallTests(SemanticTestCase):
    def test_call_with_matching_arguments(self) -> None:
        source = (
            "function add(a: integer, b: integer): integer { return a + b; }\n"
            "let total: integer = add(1, 2);\n"
        )
        self.assert_ok(source)

    def test_wrong_argument_count_is_reported(self) -> None:
        source = "function add(a: integer): integer { return a; }\nadd();\n"
        self.assert_diagnostic(source, "SEM301", line=2, column=1)

    def test_wrong_argument_type_is_reported(self) -> None:
        source = 'function add(a: integer): integer { return a; }\nadd("uno");\n'
        self.assert_diagnostic(source, "SEM302", line=2)

    def test_integer_argument_widens_to_float(self) -> None:
        source = "function half(a: float): float { return a / 2.0; }\nhalf(3);\n"
        self.assert_ok(source)

    def test_calling_a_non_function_is_reported(self) -> None:
        source = "let total: integer = 1;\ntotal();\n"
        self.assert_diagnostic(source, "SEM306", line=2)


class ReturnTests(SemanticTestCase):
    def test_return_matches_the_declared_type(self) -> None:
        self.assert_ok("function f(): integer { return 1; }")

    def test_return_type_mismatch_is_reported(self) -> None:
        self.assert_diagnostic('function f(): integer { return "a"; }', "SEM303", line=1)

    def test_bare_return_in_a_void_function(self) -> None:
        self.assert_ok('function log() { print("x"); return; }')

    def test_value_returned_from_a_void_function(self) -> None:
        # Decision 4: a function without a return annotation is void.
        self.assert_diagnostic("function log() { return 1; }", "SEM303", line=1)

    def test_missing_value_in_a_typed_function(self) -> None:
        self.assert_diagnostic("function f(): integer { return; }", "SEM303", line=1)

    def test_return_outside_a_function_is_reported(self) -> None:
        self.assert_diagnostic("return 1;", "SEM304", line=1, column=1)

    def test_function_that_may_end_without_returning(self) -> None:
        source = 'function f(): integer { print("sin retorno"); }'
        self.assert_diagnostic(source, "SEM305", line=1)

    def test_both_if_branches_returning_is_enough(self) -> None:
        source = (
            "function sign(n: integer): integer {\n"
            "  if (n < 0) { return 0; } else { return 1; }\n"
            "}\n"
        )
        self.assert_ok(source)


class RecursionAndClosureTests(SemanticTestCase):
    def test_recursive_function_is_supported(self) -> None:
        source = (
            "function factorial(n: integer): integer {\n"
            "  if (n <= 1) { return 1; }\n"
            "  return n * factorial(n - 1);\n"
            "}\n"
        )
        self.assert_ok(source)

    def test_mutually_recursive_functions_are_supported(self) -> None:
        source = (
            "function par(n: integer): boolean {\n"
            "  if (n == 0) { return true; }\n"
            "  return impar(n - 1);\n"
            "}\n"
            "function impar(n: integer): boolean {\n"
            "  if (n == 0) { return false; }\n"
            "  return par(n - 1);\n"
            "}\n"
        )
        self.assert_ok(source)

    def test_nested_function_captures_an_outer_variable(self) -> None:
        source = (
            "function outer(): integer {\n"
            "  let secret: integer = 7;\n"
            "  function inner(): integer { return secret; }\n"
            "  return inner();\n"
            "}\n"
        )
        result = self.assert_ok(source)
        outer = result.symbols.global_scope.resolve_local("outer")
        inner = outer.body_scope.resolve_local("inner")
        self.assertEqual(["secret"], inner.captured)

    def test_nested_function_cannot_use_an_undeclared_name(self) -> None:
        source = (
            "function outer(): integer {\n"
            "  function inner(): integer { return secret; }\n"
            "  return inner();\n"
            "}\n"
        )
        self.assert_diagnostic(source, "SEM201", line=2)

    def test_function_used_as_a_value_keeps_its_signature(self) -> None:
        source = (
            "function add(a: integer, b: integer): integer { return a + b; }\n"
            "let total: integer = add(1, 2);\n"
        )
        result = self.assert_ok(source)
        symbol = result.symbols.global_scope.resolve_local("add")
        self.assertEqual("(integer, integer) -> integer", str(symbol.signature))


if __name__ == "__main__":
    unittest.main()
