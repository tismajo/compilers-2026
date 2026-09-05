"""Command-line behaviour: exit codes and output formats.

The VS Code extension depends on this contract, so it is covered explicitly.
"""

from __future__ import annotations

import io
import json
import contextlib
import tempfile
import unittest
from pathlib import Path

from support import FIXTURES, PROGRAM, requires_runtime

import Driver


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = Driver.main(list(argv))
    return code, out.getvalue(), err.getvalue()


@requires_runtime
class ExitCodeTests(unittest.TestCase):
    def test_valid_file_returns_zero(self) -> None:
        code, _, _ = run_cli(str(PROGRAM / "program.cps"))
        self.assertEqual(0, code)

    def test_invalid_file_returns_one(self) -> None:
        code, _, err = run_cli(str(FIXTURES / "invalid" / "errores_multiples.cps"))
        self.assertEqual(1, code)
        self.assertIn("SEM", err)

    def test_missing_file_returns_two(self) -> None:
        code, _, err = run_cli("no-existe.cps")
        self.assertEqual(2, code)
        self.assertIn("CLI001", err)

    def test_warnings_do_not_change_the_exit_code(self) -> None:
        code, _, err = run_cli(str(PROGRAM / "program.cps"))
        self.assertEqual(0, code)
        self.assertIn("SEM604", err)


@requires_runtime
class OutputFormatTests(unittest.TestCase):
    def payload(self, *argv: str) -> dict:
        _, out, _ = run_cli(*argv)
        return json.loads(out)

    def test_json_diagnostics_carry_the_expected_fields(self) -> None:
        payload = self.payload(
            str(FIXTURES / "invalid" / "errores_multiples.cps"), "--format", "json"
        )
        self.assertFalse(payload["success"])
        self.assertEqual("semantic", payload["phase"])
        first = payload["diagnostics"][0]
        for key in ("code", "phase", "severity", "message", "line", "column"):
            self.assertIn(key, first)

    def test_json_tree_keeps_rules_and_positions(self) -> None:
        payload = self.payload(
            str(PROGRAM / "program.cps"), "--format", "json", "--tree", "json"
        )
        tree = payload["tree"]
        self.assertEqual("rule", tree["kind"])
        self.assertEqual("program", tree["name"])
        self.assertIn("line", tree)
        self.assertIn("column", tree)

    def test_lisp_tree_is_printed(self) -> None:
        _, out, _ = run_cli(str(PROGRAM / "program.cps"), "--tree", "lisp")
        self.assertTrue(out.startswith("(program"))

    def test_json_symbol_table_is_included(self) -> None:
        payload = self.payload(
            str(PROGRAM / "program.cps"), "--format", "json", "--symbols", "json"
        )
        self.assertEqual("global", payload["symbols"]["scopes"]["name"])
        names = [item["name"] for item in payload["symbols"]["classes"]]
        self.assertIn("Animal", names)

    def test_text_symbol_table_is_printed(self) -> None:
        _, out, _ = run_cli(str(PROGRAM / "program.cps"), "--symbols", "text")
        self.assertIn("[global] global", out)
        self.assertIn("[class] global.Animal", out)

    def test_no_semantic_stops_after_the_syntax_phase(self) -> None:
        payload = self.payload(
            str(PROGRAM / "program.cps"), "--format", "json", "--no-semantic"
        )
        self.assertEqual("syntax", payload["phase"])
        self.assertNotIn("symbols", payload)
        self.assertTrue(payload["success"])


@requires_runtime
class TreeExportTests(unittest.TestCase):
    def test_html_tree_is_printed(self) -> None:
        _, out, _ = run_cli(str(PROGRAM / "program.cps"), "--tree", "html")
        self.assertTrue(out.startswith("<!DOCTYPE html>"))
        self.assertIn("<details", out)

    def test_svg_tree_is_written_to_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "arbol.svg"
            code, out, _ = run_cli(
                str(PROGRAM / "program.cps"), "--tree", "svg", "--tree-out", str(target)
            )
            self.assertEqual(0, code)
            self.assertIn(str(target), out)
            document = target.read_text(encoding="utf-8")
            self.assertTrue(document.startswith("<svg"))

    def test_dot_tree_is_printed(self) -> None:
        _, out, _ = run_cli(str(PROGRAM / "program.cps"), "--tree", "dot")
        self.assertTrue(out.startswith("digraph Compiscript {"))

    def test_dot_tree_respects_the_depth_limit(self) -> None:
        _, full, _ = run_cli(str(PROGRAM / "program.cps"), "--tree", "dot")
        _, shallow, _ = run_cli(
            str(PROGRAM / "program.cps"), "--tree", "dot", "--tree-depth", "4"
        )
        self.assertLess(shallow.count("[label="), full.count("[label="))
        self.assertIn("nodos omitidos", shallow)

    def test_compact_flag_shrinks_the_tree(self) -> None:
        _, full, _ = run_cli(str(PROGRAM / "program.cps"), "--tree", "dot")
        _, small, _ = run_cli(
            str(PROGRAM / "program.cps"), "--tree", "dot", "--tree-compact"
        )
        self.assertLess(small.count("[label="), full.count("[label=") // 2)

    def test_json_tree_is_written_to_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "arbol.json"
            run_cli(
                str(PROGRAM / "program.cps"), "--tree", "json", "--tree-out", str(target)
            )
            tree = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual("program", tree["name"])


if __name__ == "__main__":
    unittest.main()
