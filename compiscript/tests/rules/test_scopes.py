"""Symbol table, scopes and name resolution."""

from __future__ import annotations

import unittest

from support import SemanticTestCase
from semantic.scopes import ScopeKind


class ResolutionTests(SemanticTestCase):
    def test_global_declaration_is_registered_and_resolved(self) -> None:
        source = (
            "let total: integer = 1;\n"
            "function useTotal(): integer { return total; }\n"
        )
        result = self.assert_ok(source)
        symbol = result.symbols.global_scope.resolve_local("total")
        self.assertIsNotNone(symbol)
        self.assertEqual("integer", str(symbol.type))

    def test_nested_block_resolves_outer_name(self) -> None:
        self.assert_ok("let total: integer = 1;\n{ { print(total); } }\n")

    def test_undeclared_identifier_is_reported(self) -> None:
        self.assert_diagnostic("print(missing);", "SEM201", line=1, column=7)

    def test_inner_declaration_is_not_visible_outside(self) -> None:
        source = "{ let inner: integer = 1; }\nprint(inner);\n"
        self.assert_diagnostic(source, "SEM201", line=2)

    def test_redeclaration_in_same_scope_is_reported(self) -> None:
        source = "let value: integer = 1;\nlet value: integer = 2;\n"
        self.assert_diagnostic(source, "SEM202", line=2, column=5)

    def test_shadowing_in_nested_block_is_allowed(self) -> None:
        # Decision 2: shadowing is permitted, like TypeScript.
        source = 'let value: integer = 1;\n{ let value: string = "otro"; print(value); }\n'
        self.assert_ok(source)

    def test_local_cannot_shadow_a_parameter(self) -> None:
        source = "function f(a: integer): integer {\nlet a: integer = 2;\nreturn a;\n}\n"
        self.assert_diagnostic(source, "SEM202", line=2)

    def test_duplicate_parameters_are_reported(self) -> None:
        source = "function repeat(a: integer, a: integer): integer { return a; }"
        self.assert_diagnostic(source, "SEM203", line=1)

    def test_duplicate_functions_are_reported(self) -> None:
        source = (
            "function twice(): integer { return 1; }\n"
            "function twice(): integer { return 2; }\n"
        )
        self.assert_diagnostic(source, "SEM204", line=2)

    def test_duplicate_classes_are_reported(self) -> None:
        self.assert_diagnostic("class Repeated {}\nclass Repeated {}\n", "SEM205", line=2)

    def test_parameter_without_annotation_is_rejected(self) -> None:
        # Decision 3: an unannotated parameter is an error.
        self.assert_diagnostic("function f(a): integer { return 1; }", "SEM210", line=1)

    def test_unknown_type_in_annotation_is_reported(self) -> None:
        self.assert_diagnostic("let value: Desconocido = null;", "SEM209", line=1)


class ScopeTreeTests(SemanticTestCase):
    def test_every_scope_kind_is_created(self) -> None:
        source = (
            "class Holder { let name: string; }\n"
            "let items: integer[] = [1, 2];\n"
            "function walk(): integer {\n"
            "  { let inner: integer = 1; print(inner); }\n"
            "  foreach (item in items) { print(item); }\n"
            '  try { print("ok"); } catch (err) { print(err); }\n'
            "  return 0;\n"
            "}\n"
        )
        result = self.assert_ok(source)
        found = {scope.kind for scope in result.symbols.scopes()}
        self.assertEqual(
            {
                ScopeKind.GLOBAL,
                ScopeKind.CLASS,
                ScopeKind.FUNCTION,
                ScopeKind.BLOCK,
                ScopeKind.FOREACH,
                ScopeKind.CATCH,
            },
            found,
        )

    def test_symbol_table_is_exportable(self) -> None:
        result = self.assert_ok("let total: integer = 1;")
        payload = result.symbols.as_dict()
        self.assertIn("scopes", payload)
        self.assertIn("classes", payload)
        names = [item["name"] for item in payload["scopes"]["symbols"]]
        self.assertIn("total", names)

    def test_symbols_reserve_fields_for_later_phases(self) -> None:
        result = self.assert_ok("let total: integer = 1;")
        symbol = result.symbols.global_scope.resolve_local("total").as_dict()
        for field in ("offset", "size", "storage", "label"):
            self.assertIn(field, symbol)
            self.assertIsNone(symbol[field])


if __name__ == "__main__":
    unittest.main()
