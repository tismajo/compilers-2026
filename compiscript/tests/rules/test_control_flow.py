"""Control flow: conditions, loops, break, continue, switch and try/catch."""

from __future__ import annotations

import unittest

from support import SemanticTestCase


class ConditionTests(SemanticTestCase):
    def test_if_accepts_a_boolean_condition(self) -> None:
        self.assert_ok('if (1 < 2) { print("si"); } else { print("no"); }')

    def test_if_rejects_a_non_boolean_condition(self) -> None:
        self.assert_diagnostic('if (1) { print("no"); }', "SEM106", line=1, column=5)

    def test_while_accepts_a_boolean_condition(self) -> None:
        source = "let n: integer = 0;\nwhile (n < 3) { n = n + 1; }\n"
        self.assert_ok(source)

    def test_while_rejects_a_non_boolean_condition(self) -> None:
        self.assert_diagnostic('while ("a") { break; }', "SEM106", line=1)

    def test_do_while_accepts_a_boolean_condition(self) -> None:
        source = "let n: integer = 0;\ndo { n = n + 1; } while (n < 3);\n"
        self.assert_ok(source)

    def test_do_while_rejects_a_non_boolean_condition(self) -> None:
        self.assert_diagnostic("do { print(1); } while (1);", "SEM106", line=1)

    def test_for_accepts_a_boolean_condition(self) -> None:
        self.assert_ok("for (let i: integer = 0; i < 3; i = i + 1) { print(i); }")

    def test_for_rejects_a_non_boolean_condition(self) -> None:
        source = 'for (let i: integer = 0; "a"; i = i + 1) { print(i); }'
        self.assert_diagnostic(source, "SEM106", line=1)


class ForeachTests(SemanticTestCase):
    def test_foreach_over_an_array_infers_the_element_type(self) -> None:
        source = (
            "let items: integer[] = [1, 2, 3];\n"
            'foreach (item in items) { print("n = " + item); }\n'
        )
        self.assert_ok(source)

    def test_foreach_element_keeps_the_element_type(self) -> None:
        source = (
            "let items: integer[] = [1, 2];\n"
            "foreach (item in items) { let bad: boolean = item; }\n"
        )
        self.assert_diagnostic(source, "SEM105", line=2)

    def test_foreach_rejects_a_non_array(self) -> None:
        source = 'let name: string = "a";\nforeach (letter in name) { print(letter); }\n'
        self.assert_diagnostic(source, "SEM403", line=2)


class BreakContinueTests(SemanticTestCase):
    def test_break_and_continue_inside_a_loop(self) -> None:
        source = (
            "let items: integer[] = [1, 2, 3];\n"
            "foreach (n in items) {\n"
            "  if (n == 2) { continue; }\n"
            "  if (n == 3) { break; }\n"
            "}\n"
        )
        self.assert_ok(source)

    def test_break_outside_a_loop_is_reported(self) -> None:
        self.assert_diagnostic("break;", "SEM401", line=1, column=1)

    def test_continue_outside_a_loop_is_reported(self) -> None:
        self.assert_diagnostic("continue;", "SEM402", line=1, column=1)

    def test_break_inside_switch_is_allowed(self) -> None:
        # Decision 1: break is valid inside a switch.
        source = "let n: integer = 1;\nswitch (n) { case 1: break; default: print(0); }\n"
        self.assert_ok(source)

    def test_continue_inside_switch_is_rejected(self) -> None:
        source = "let n: integer = 1;\nswitch (n) { case 1: continue; }\n"
        self.assert_diagnostic(source, "SEM402", line=2)


class SwitchTests(SemanticTestCase):
    def test_switch_accepts_comparable_cases(self) -> None:
        source = (
            "let n: integer = 1;\n"
            'switch (n) { case 1: print("uno"); case 2: print("dos"); '
            'default: print("otro"); }\n'
        )
        self.assert_ok(source)

    def test_case_incompatible_with_the_subject(self) -> None:
        source = 'let n: integer = 1;\nswitch (n) { case "uno": print(1); }\n'
        self.assert_diagnostic(source, "SEM404", line=2)

    def test_duplicate_constant_case_is_reported(self) -> None:
        source = "let n: integer = 1;\nswitch (n) { case 1: print(1); case 1: print(2); }\n"
        self.assert_diagnostic(source, "SEM405", line=2)


class TryCatchTests(SemanticTestCase):
    def test_catch_variable_is_a_string(self) -> None:
        # Decision 7: the catch variable is typed as string.
        source = 'try { print("t"); } catch (err) { print("e: " + err); }'
        self.assert_ok(source)

    def test_catch_variable_cannot_be_used_as_a_number(self) -> None:
        source = 'try { print("t"); } catch (err) { let bad: integer = err; }'
        self.assert_diagnostic(source, "SEM105", line=1)


if __name__ == "__main__":
    unittest.main()
