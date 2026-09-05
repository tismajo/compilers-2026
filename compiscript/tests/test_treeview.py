"""Tree serializer and its HTML, SVG and Graphviz renderers."""

from __future__ import annotations

import json
import unittest

from support import FIXTURES, PROGRAM, analyze_code, analyze_file, requires_runtime

import treeview


def find(node: dict, predicate) -> list[dict]:
    found = [node] if predicate(node) else []
    for child in node.get("children", []):
        found.extend(find(child, predicate))
    return found


@requires_runtime
class SerializerTests(unittest.TestCase):
    def tree_of(self, source: str) -> dict:
        return analyze_code(source).tree_as_dict()

    def test_rule_names_and_positions(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        self.assertEqual("rule", tree["kind"])
        self.assertEqual("program", tree["name"])
        self.assertEqual(1, tree["line"])
        self.assertEqual(1, tree["column"])

    def test_terminal_text_is_preserved(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        tokens = [item["text"] for item in find(tree, lambda n: n["kind"] == "token")]
        self.assertIn("total", tokens)
        self.assertIn("integer", tokens)
        self.assertIn("1", tokens)

    def test_inferred_types_are_attached(self) -> None:
        tree = self.tree_of('let saludo: string = "hola" + 1;')
        typed = find(tree, lambda n: n.get("type") == "string")
        self.assertTrue(typed)
        self.assertTrue(all("line" in item for item in typed))

    def test_punctuation_is_flagged_as_noise(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        noise = {item["text"] for item in find(tree, lambda n: n.get("noise"))}
        self.assertIn(";", noise)
        self.assertIn(":", noise)
        self.assertNotIn("total", noise)

    def test_visible_children_hides_noise(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        declaration = find(tree, lambda n: n.get("name") == "variableDeclaration")[0]
        visible = treeview.visible_children(declaration, hide_noise=True)
        self.assertNotIn(";", [item.get("text") for item in visible])
        self.assertEqual(
            len(declaration["children"]),
            len(treeview.visible_children(declaration, hide_noise=False)),
        )

    def test_only_the_innermost_node_carries_the_diagnostic(self) -> None:
        tree = self.tree_of("let total: integer = 1;\ntotal = true;\n")
        marked = find(tree, lambda n: "diagnostic" in n)
        self.assertEqual(1, len(marked))
        self.assertEqual("SEM105", marked[0]["diagnostic"]["code"])
        self.assertEqual("error", marked[0]["diagnostic"]["severity"])

    def test_warnings_are_marked_too(self) -> None:
        result = analyze_file(PROGRAM / "program.cps")
        marked = find(result.tree_as_dict(), lambda n: "diagnostic" in n)
        self.assertEqual(1, len(marked))
        self.assertEqual("warning", marked[0]["diagnostic"]["severity"])

    def test_recoverable_errors_still_produce_a_tree(self) -> None:
        result = analyze_file(FIXTURES / "invalid" / "errores_multiples.cps")
        tree = result.tree_as_dict()
        self.assertEqual("program", tree["name"])
        marked = find(tree, lambda n: "diagnostic" in n)
        self.assertGreaterEqual(len(marked), 5)

    def test_tree_is_json_serializable(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        restored = json.loads(treeview.to_json(tree))
        self.assertEqual(tree, restored)


@requires_runtime
class HtmlRendererTests(unittest.TestCase):
    def render(self, source: str) -> str:
        return treeview.render_html(analyze_code(source).tree_as_dict(), "Prueba")

    def test_document_is_self_contained_and_collapsible(self) -> None:
        document = self.render("let total: integer = 1;")
        self.assertTrue(document.startswith("<!DOCTYPE html>"))
        self.assertIn("<details", document)
        self.assertIn("<summary>", document)
        self.assertIn('id="expand"', document)
        self.assertIn('id="collapse"', document)
        self.assertIn('id="toggle-noise"', document)
        self.assertNotIn("http://", document.replace('"http://www.w3.org', ""))

    def test_rules_types_and_positions_are_shown(self) -> None:
        document = self.render("let total: integer = 1;")
        self.assertIn("variableDeclaration", document)
        self.assertIn('class="type"', document)
        self.assertIn('class="pos"', document)

    def test_diagnostic_nodes_are_highlighted(self) -> None:
        document = self.render("let total: integer = 1;\ntotal = true;\n")
        self.assertIn('class="badge error"', document)
        self.assertIn("SEM105", document)

    def test_source_text_is_escaped(self) -> None:
        document = self.render('let etiqueta: string = "<b>hola</b>";')
        self.assertIn("&lt;b&gt;", document)
        self.assertNotIn("<b>hola</b>", document)


@requires_runtime
class SvgRendererTests(unittest.TestCase):
    def test_svg_export_is_produced(self) -> None:
        tree = analyze_code("let total: integer = 1;").tree_as_dict()
        svg = treeview.render_svg(tree)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)
        self.assertIn("<text", svg)
        self.assertIn("variableDeclaration", svg)

    def test_svg_drops_punctuation_by_default(self) -> None:
        tree = analyze_code("let total: integer = 1;").tree_as_dict()
        self.assertNotIn(">;<", treeview.render_svg(tree))
        self.assertIn(">;<", treeview.render_svg(tree, hide_noise=False))


@requires_runtime
class DotRendererTests(unittest.TestCase):
    def tree_of(self, source: str) -> dict:
        return analyze_code(source).tree_as_dict()

    def test_dot_source_is_well_formed(self) -> None:
        dot = treeview.render_dot(self.tree_of("let total: integer = 1;"))
        self.assertTrue(dot.startswith("digraph Compiscript {"))
        self.assertTrue(dot.rstrip().endswith("}"))
        self.assertIn("rankdir=TB", dot)
        self.assertEqual(dot.count(" -> "), dot.count("[label=") - 1)

    def test_rules_types_and_positions_are_labelled(self) -> None:
        dot = treeview.render_dot(self.tree_of("let total: integer = 1;"))
        self.assertIn("variableDeclaration", dot)
        self.assertIn(": integer", dot)
        self.assertIn("1:1", dot)

    def test_tokens_and_rules_use_different_shapes(self) -> None:
        dot = treeview.render_dot(self.tree_of("let total: integer = 1;"))
        self.assertIn("shape=box", dot)
        self.assertIn("shape=ellipse", dot)

    def test_diagnostic_nodes_are_coloured(self) -> None:
        dot = treeview.render_dot(self.tree_of("let total: integer = 1;\ntotal = true;\n"))
        self.assertIn("SEM105", dot)
        self.assertIn("#fde2e1", dot)

    def test_warnings_use_their_own_colour(self) -> None:
        source = "let items: integer[] = [1, 2];\nprint(items[9]);\n"
        dot = treeview.render_dot(self.tree_of(source))
        self.assertIn("SEM604", dot)
        self.assertIn("#fff3cd", dot)

    def test_punctuation_is_hidden_by_default(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        self.assertNotIn('label=";', treeview.render_dot(tree))
        self.assertIn('label=";', treeview.render_dot(tree, hide_noise=False))

    def test_quotes_and_backslashes_are_escaped(self) -> None:
        dot = treeview.render_dot(self.tree_of('let texto: string = "hola";'))
        self.assertIn('\\"hola\\"', dot)

    def test_depth_limit_prunes_the_tree(self) -> None:
        tree = self.tree_of("let total: integer = 1 + 2;")
        full = treeview.render_dot(tree)
        shallow = treeview.render_dot(tree, max_depth=3)
        self.assertLess(shallow.count("[label="), full.count("[label="))
        self.assertIn("nodos omitidos", shallow)

    def test_compact_collapses_the_precedence_chain(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        compacted = treeview.compact(tree)
        full_names = {item["name"] for item in find(tree, lambda n: n["kind"] == "rule")}
        compact_names = {
            item["name"] for item in find(compacted, lambda n: n["kind"] == "rule")
        }
        self.assertIn("logicalOrExpr", full_names)
        self.assertNotIn("logicalOrExpr", compact_names)
        self.assertLess(len(compact_names), len(full_names))

    def test_compact_keeps_the_most_specific_rule(self) -> None:
        compacted = treeview.compact(self.tree_of("let total: integer = 1;"))
        names = {item["name"] for item in find(compacted, lambda n: n["kind"] == "rule")}
        self.assertIn("variableDeclaration", names)
        self.assertIn("literalExpr", names)
        self.assertNotIn("statement", names)

    def test_compact_preserves_types_and_positions(self) -> None:
        compacted = treeview.compact(self.tree_of("let total: integer = 1 + 2;"))
        typed = find(compacted, lambda n: n.get("type") == "integer")
        self.assertTrue(typed)
        self.assertTrue(all("line" in item for item in typed))

    def test_compact_keeps_nodes_with_several_children(self) -> None:
        compacted = treeview.compact(self.tree_of("let total: integer = 1 + 2;"))
        additive = find(compacted, lambda n: n.get("name") == "additiveExpr")
        self.assertEqual(1, len(additive))
        # Two operands plus the operator, which is not punctuation and is kept.
        children = additive[0]["children"]
        self.assertEqual(3, len(children))
        self.assertEqual("+", children[1]["text"])

    def test_compact_keeps_diagnostic_marks(self) -> None:
        tree = self.tree_of("let total: integer = 1;\ntotal = true;\n")
        marked = find(treeview.compact(tree), lambda n: "diagnostic" in n)
        self.assertEqual(1, len(marked))
        self.assertEqual("SEM105", marked[0]["diagnostic"]["code"])

    def test_prune_keeps_the_root_untouched(self) -> None:
        tree = self.tree_of("let total: integer = 1;")
        pruned = treeview.prune(tree, 2)
        self.assertEqual("program", pruned["name"])
        self.assertEqual(tree["line"], pruned["line"])
        self.assertIsNone(treeview.prune(tree, None).get("elided"))


if __name__ == "__main__":
    unittest.main()
