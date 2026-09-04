"""Dead code plus whole-program checks over the official and local fixtures."""

from __future__ import annotations

import unittest

from support import FIXTURES, PROGRAM, SemanticTestCase, analyze_file, codes


class DeadCodeTests(SemanticTestCase):
    def test_statement_after_return_is_a_warning(self) -> None:
        # Decision 5: dead code is a warning and keeps the exit code at 0.
        source = 'function f(): integer {\n  return 1;\n  print("muerto");\n}\n'
        result = self.assert_diagnostic(source, "SEM701", line=3, severity="warning")
        self.assertTrue(result.success)

    def test_statement_after_break_is_a_warning(self) -> None:
        source = "while (true) {\n  break;\n  print(1);\n}\n"
        self.assert_diagnostic(source, "SEM701", line=3, severity="warning")

    def test_statement_after_continue_is_a_warning(self) -> None:
        source = "while (true) {\n  continue;\n  print(1);\n}\n"
        self.assert_diagnostic(source, "SEM701", line=3, severity="warning")

    def test_block_after_an_exhaustive_if_is_a_warning(self) -> None:
        source = (
            "function f(): integer {\n"
            "  if (true) { return 1; } else { return 2; }\n"
            "  print(1);\n"
            "}\n"
        )
        self.assert_diagnostic(source, "SEM701", line=3, severity="warning")

    def test_reachable_code_after_a_partial_if_is_not_flagged(self) -> None:
        source = (
            "function f(): integer {\n"
            "  if (true) { return 1; }\n"
            "  return 2;\n"
            "}\n"
        )
        result = self.assert_ok(source)
        self.assertNotIn("SEM701", codes(result))

    def test_code_after_a_loop_containing_break_is_not_flagged(self) -> None:
        source = (
            "function f(): integer {\n"
            "  while (true) { break; }\n"
            "  return 1;\n"
            "}\n"
        )
        result = self.assert_ok(source)
        self.assertNotIn("SEM701", codes(result))


class OfficialProgramTests(SemanticTestCase):
    def test_official_program_passes_the_semantic_phase(self) -> None:
        result = analyze_file(PROGRAM / "program.cps")
        self.assertTrue(result.success, [item.as_dict() for item in result.diagnostics])
        self.assertEqual("semantic", result.phase)

    def test_official_program_only_warns_about_the_literal_index(self) -> None:
        result = analyze_file(PROGRAM / "program.cps")
        self.assertEqual({"SEM604"}, codes(result))
        self.assertEqual("warning", result.diagnostics[0].severity)

    def test_official_program_builds_its_symbol_table(self) -> None:
        result = analyze_file(PROGRAM / "program.cps")
        classes = result.symbols.classes
        self.assertIn("Animal", classes)
        self.assertIn("Dog", classes)
        self.assertEqual("Animal", classes["Dog"].parent_name)
        self.assertIsNotNone(classes["Dog"].lookup_attribute("name"))
        self.assertIsNotNone(classes["Dog"].lookup_constructor())


class FixtureProgramTests(SemanticTestCase):
    def test_complete_valid_program(self) -> None:
        result = analyze_file(FIXTURES / "valid" / "programa_completo.cps")
        self.assertTrue(result.success, [item.as_dict() for item in result.diagnostics])
        self.assertEqual([], result.diagnostics)

    def test_program_with_multiple_recoverable_errors(self) -> None:
        result = analyze_file(FIXTURES / "invalid" / "errores_multiples.cps")
        self.assertFalse(result.success)
        expected = {
            "SEM101",
            "SEM104",
            "SEM105",
            "SEM108",
            "SEM201",
            "SEM301",
            "SEM402",
            "SEM502",
        }
        self.assertTrue(
            expected.issubset(codes(result)),
            f"faltaron {sorted(expected - codes(result))}",
        )

    def test_one_error_per_semantic_group(self) -> None:
        result = analyze_file(FIXTURES / "invalid" / "muestra_por_grupo.cps")
        families = {item.code[:4] for item in result.diagnostics}
        self.assertEqual(
            {"SEM1", "SEM2", "SEM3", "SEM4", "SEM5", "SEM6", "SEM7"},
            families,
        )

    def test_every_diagnostic_carries_code_and_position(self) -> None:
        result = analyze_file(FIXTURES / "invalid" / "errores_multiples.cps")
        for diagnostic in result.diagnostics:
            self.assertTrue(diagnostic.code)
            self.assertTrue(diagnostic.message)
            self.assertIn(diagnostic.severity, ("error", "warning"))
            self.assertGreater(diagnostic.line, 0)
            self.assertGreater(diagnostic.column, 0)

    def test_errors_are_reported_in_source_order(self) -> None:
        result = analyze_file(FIXTURES / "invalid" / "errores_multiples.cps")
        lines = [item.line for item in result.diagnostics]
        self.assertEqual(sorted(lines), lines)


if __name__ == "__main__":
    unittest.main()
