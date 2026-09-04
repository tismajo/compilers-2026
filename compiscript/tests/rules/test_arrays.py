"""Arrays: element types, indexing and static bounds."""

from __future__ import annotations

import unittest

from support import SemanticTestCase


class ArrayLiteralTests(SemanticTestCase):
    def test_homogeneous_literal_is_inferred(self) -> None:
        source = "let items = [1, 2, 3];\nlet copy: integer[] = items;\n"
        self.assert_ok(source)

    def test_numeric_literal_widens_to_float(self) -> None:
        self.assert_ok("let items: float[] = [1, 2.5];")

    def test_heterogeneous_literal_is_reported(self) -> None:
        self.assert_diagnostic('let items = [1, "dos"];', "SEM603", line=1)

    def test_empty_literal_adapts_to_the_declared_type(self) -> None:
        self.assert_ok("let items: integer[] = [];")

    def test_multidimensional_literal_is_accepted(self) -> None:
        source = "let matrix: integer[][] = [[1, 2], [3, 4]];\nlet row: integer[] = matrix[0];\n"
        self.assert_ok(source)

    def test_array_of_objects_is_accepted(self) -> None:
        source = (
            "class Punto {}\n"
            "let puntos: Punto[] = [new Punto(), new Punto()];\n"
            "let first: Punto = puntos[0];\n"
        )
        self.assert_ok(source)


class IndexingTests(SemanticTestCase):
    def test_integer_index_returns_the_element_type(self) -> None:
        source = "let items: integer[] = [1, 2, 3];\nlet first: integer = items[0];\n"
        self.assert_ok(source)

    def test_non_integer_index_is_reported(self) -> None:
        source = 'let items: integer[] = [1, 2];\nprint(items["a"]);\n'
        self.assert_diagnostic(source, "SEM601", line=2)

    def test_indexing_a_non_array_is_reported(self) -> None:
        source = "let total: integer = 1;\nprint(total[0]);\n"
        self.assert_diagnostic(source, "SEM602", line=2)

    def test_element_type_is_checked_on_use(self) -> None:
        source = "let items: integer[] = [1, 2];\nlet bad: string = items[0];\n"
        self.assert_diagnostic(source, "SEM105", line=2)

    def test_assignment_to_an_element_is_accepted(self) -> None:
        source = "let items: integer[] = [1, 2];\nitems[0] = 5;\n"
        self.assert_ok(source)

    def test_assignment_to_an_element_is_type_checked(self) -> None:
        source = 'let items: integer[] = [1, 2];\nitems[0] = "cinco";\n'
        self.assert_diagnostic(source, "SEM105", line=2)


class StaticBoundsTests(SemanticTestCase):
    def test_literal_index_out_of_range_is_a_warning(self) -> None:
        # Decision 6: the official program indexes numbers[10] on purpose.
        source = "let items: integer[] = [1, 2, 3];\nprint(items[9]);\n"
        result = self.assert_diagnostic(source, "SEM604", line=2, severity="warning")
        self.assertTrue(result.success)

    def test_literal_index_in_range_is_silent(self) -> None:
        source = "let items: integer[] = [1, 2, 3];\nprint(items[2]);\n"
        result = self.assert_ok(source)
        self.assertEqual([], result.diagnostics)

    def test_dynamic_index_is_left_to_runtime(self) -> None:
        source = (
            "let items: integer[] = [1, 2, 3];\n"
            "let position: integer = 99;\n"
            "print(items[position]);\n"
        )
        result = self.assert_ok(source)
        self.assertEqual([], result.diagnostics)


if __name__ == "__main__":
    unittest.main()
