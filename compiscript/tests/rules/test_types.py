"""Type system: arithmetic, logic, comparisons, assignments and constants."""

from __future__ import annotations

import unittest

from support import SemanticTestCase


class ArithmeticTests(SemanticTestCase):
    def test_numeric_operands_are_accepted(self) -> None:
        self.assert_ok("let total: integer = 2 + 3 * 4 - 1;")

    def test_mixed_integer_and_float_produces_float(self) -> None:
        self.assert_ok("let total: float = 2 + 1.5;")

    def test_float_result_does_not_fit_in_integer(self) -> None:
        self.assert_diagnostic("let total: integer = 2 + 1.5;", "SEM105", line=1)

    def test_modulo_and_division_accept_numbers(self) -> None:
        self.assert_ok("let total: integer = 7 % 2;\nlet half: float = 7 / 2.0;")

    def test_string_operand_is_rejected_in_subtraction(self) -> None:
        source = 'let name: string = "a";\nlet total: integer = name - 1;\n'
        self.assert_diagnostic(source, "SEM101", line=2)

    def test_unary_minus_requires_a_number(self) -> None:
        self.assert_diagnostic('let bad: integer = -"a";', "SEM101", line=1)

    def test_objects_cannot_be_multiplied(self) -> None:
        source = "class Punto {}\nlet a: Punto = new Punto();\nlet bad: integer = a * a;\n"
        self.assert_diagnostic(source, "SEM101", line=3)

    def test_functions_cannot_be_multiplied(self) -> None:
        source = "function f(): integer { return 1; }\nlet bad: integer = f * 2;\n"
        self.assert_diagnostic(source, "SEM101", line=2)


class ConcatenationTests(SemanticTestCase):
    def test_string_concatenates_printable_values(self) -> None:
        source = (
            'let label: string = "n = " + 1;\n'
            'let flag: string = "b = " + true;\n'
            'let real: string = "f = " + 1.5;\n'
        )
        self.assert_ok(source)

    def test_string_cannot_concatenate_a_function(self) -> None:
        source = 'function f(): integer { return 1; }\nlet bad: string = "f = " + f;\n'
        self.assert_diagnostic(source, "SEM101", line=2)


class LogicTests(SemanticTestCase):
    def test_boolean_operands_are_accepted(self) -> None:
        self.assert_ok("let ok: boolean = true && false || true;")

    def test_non_boolean_operand_is_rejected(self) -> None:
        self.assert_diagnostic("let bad: boolean = true && 3;", "SEM102", line=1)

    def test_negation_accepts_a_boolean(self) -> None:
        self.assert_ok("let ok: boolean = !true;")

    def test_negation_rejects_a_string(self) -> None:
        self.assert_diagnostic('let bad: boolean = !"a";', "SEM103", line=1)


class ComparisonTests(SemanticTestCase):
    def test_equality_between_compatible_types(self) -> None:
        self.assert_ok("let ok: boolean = 1 == 1.5;\nlet same: boolean = true != false;")

    def test_equality_between_incompatible_types(self) -> None:
        self.assert_diagnostic('let bad: boolean = 1 == "uno";', "SEM104", line=1)

    def test_relational_accepts_numbers_and_strings(self) -> None:
        source = 'let a: boolean = 1 < 2.5;\nlet b: boolean = "a" <= "b";\n'
        self.assert_ok(source)

    def test_relational_rejects_mixed_operands(self) -> None:
        self.assert_diagnostic('let bad: boolean = 1 < "a";', "SEM104", line=1)


class TernaryTests(SemanticTestCase):
    def test_compatible_branches_are_accepted(self) -> None:
        self.assert_ok("let value: float = true ? 1 : 2.5;")

    def test_condition_must_be_boolean(self) -> None:
        self.assert_diagnostic("let value: integer = 1 ? 1 : 2;", "SEM106", line=1)

    def test_incompatible_branches_are_rejected(self) -> None:
        self.assert_diagnostic('let value: integer = true ? 1 : "dos";', "SEM107", line=1)


class AssignmentTests(SemanticTestCase):
    def test_declaration_and_later_assignment(self) -> None:
        source = "let total: integer = 1;\ntotal = 2;\nlet real: float = 1;\n"
        self.assert_ok(source)

    def test_initializer_must_match_the_annotation(self) -> None:
        self.assert_diagnostic('let total: integer = "uno";', "SEM105", line=1, column=22)

    def test_later_assignment_must_match(self) -> None:
        source = "let total: integer = 1;\ntotal = true;\n"
        self.assert_diagnostic(source, "SEM105", line=2)

    def test_declaration_without_type_or_initializer(self) -> None:
        self.assert_diagnostic("let alone;", "SEM208", line=1, column=5)

    def test_inference_from_the_initializer(self) -> None:
        source = 'let name = "compiscript";\nlet upper: string = name;\n'
        self.assert_ok(source)

    def test_function_is_not_an_assignable_target(self) -> None:
        source = "function f(): integer { return 1; }\nf = 1;\n"
        self.assert_diagnostic(source, "SEM110", line=2)


class ConstantTests(SemanticTestCase):
    def test_constant_with_initializer_is_accepted(self) -> None:
        self.assert_ok("const LIMIT: integer = 10;\nlet copy: integer = LIMIT;")

    def test_constant_cannot_be_reassigned(self) -> None:
        source = "const LIMIT: integer = 10;\nLIMIT = 11;\n"
        self.assert_diagnostic(source, "SEM108", line=2, column=1)


class PrintTests(SemanticTestCase):
    def test_printable_values_are_accepted(self) -> None:
        self.assert_ok('print("hola");\nprint(1);\nprint(true);')

    def test_functions_are_not_printable(self) -> None:
        source = "function f(): integer { return 1; }\nprint(f);\n"
        self.assert_diagnostic(source, "SEM109", line=2)


if __name__ == "__main__":
    unittest.main()
