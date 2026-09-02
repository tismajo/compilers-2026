"""Visual representation of the Compiscript parse tree.

The serializer turns an ANTLR parse tree into a JSON-safe structure enriched
with the information the semantic phase produced: the inferred type of every
expression and a flag on the nodes that carry a diagnostic. Three renderers build
on that structure:

``render_html``
    A self-contained, collapsible tree. The VS Code webview embeds exactly this
    document, and it also opens directly in a browser.
``render_svg``
    A static export of the same tree, laid out without external tools.
``render_dot``
    The same tree in Graphviz DOT format, so `dot` can lay it out properly.
"""

from __future__ import annotations

import html
import json
from typing import Any, Optional, Sequence

# Punctuation carries no information once the tree shows the rule names, so it
# is marked as noise and the renderers dim or hide it.
NOISE_TOKENS = frozenset(
    {";", ",", "(", ")", "{", "}", "[", "]", ":", "?", ".", "=", "<EOF>"}
)


def serialize(
    node: Any,
    parser: Any,
    types: Optional[dict[int, str]] = None,
    diagnostics: Sequence[Any] = (),
) -> dict[str, Any]:
    """Convert a parse tree into the JSON structure used by every renderer."""
    types = types or {}
    marks = {(item.line, item.column): item for item in diagnostics}
    return _serialize(node, parser, types, marks)


def _serialize(
    node: Any, parser: Any, types: dict[int, str], marks: dict[tuple[int, int], Any]
) -> dict[str, Any]:
    if hasattr(node, "getRuleIndex"):
        start = getattr(node, "start", None)
        result: dict[str, Any] = {
            "kind": "rule",
            "name": parser.ruleNames[node.getRuleIndex()],
            "children": [
                _serialize(node.getChild(index), parser, types, marks)
                for index in range(node.getChildCount())
            ],
        }
        if start is not None:
            result["line"] = start.line
            result["column"] = start.column + 1
        inferred = types.get(id(node))
        if inferred is not None:
            result["type"] = inferred
        _mark(result, marks)
        return result

    text = node.getText()
    token = getattr(node, "symbol", None)
    leaf: dict[str, Any] = {"kind": "token", "text": text}
    if token is not None:
        leaf["line"] = token.line
        leaf["column"] = token.column + 1
    if text in NOISE_TOKENS:
        leaf["noise"] = True
    _mark(leaf, marks)
    return leaf


def _mark(node: dict[str, Any], marks: dict[tuple[int, int], Any]) -> None:
    """Attach a diagnostic to the innermost node that starts at its position.

    Every rule on the way down shares the position of its first token, so only
    the node whose children start somewhere else is marked.
    """
    key = (node.get("line", 0), node.get("column", 0))
    diagnostic = marks.get(key)
    if diagnostic is None:
        return
    for child in node.get("children", []):
        if (child.get("line", 0), child.get("column", 0)) == key:
            return
    node["diagnostic"] = {
        "code": diagnostic.code,
        "severity": diagnostic.severity,
        "message": diagnostic.message,
    }


def label(node: dict[str, Any]) -> str:
    """Single-line label of a node, used by both renderers."""
    if node["kind"] == "rule":
        text = node["name"]
    else:
        text = repr(node["text"])[1:-1]
    if node.get("type"):
        text = f"{text} : {node['type']}"
    return text


def visible_children(node: dict[str, Any], hide_noise: bool) -> list[dict[str, Any]]:
    children = node.get("children", [])
    if not hide_noise:
        return children
    return [child for child in children if not child.get("noise")]


def compact(node: dict[str, Any], hide_noise: bool = True) -> dict[str, Any]:
    """Collapse chains of single-child rules into their innermost rule.

    The grammar walks the whole precedence ladder even when there is no
    operator, so a literal like ``1`` hangs from a dozen rules that add no
    information. Each chain is replaced by its most specific rule, which is the
    innermost one; the type and the position are the same all along the chain.
    """
    current = node
    if current["kind"] == "rule":
        while True:
            children = visible_children(current, hide_noise)
            if len(children) == 1 and children[0]["kind"] == "rule":
                current = children[0]
            else:
                break
    copy = {key: value for key, value in current.items() if key != "children"}
    children = visible_children(current, hide_noise)
    if children:
        copy["children"] = [compact(child, hide_noise) for child in children]
    return copy


def prune(node: dict[str, Any], max_depth: Optional[int]) -> dict[str, Any]:
    """Copy the tree keeping only ``max_depth`` levels.

    A pruned subtree is replaced by a single node that says how many
    descendants were left out, so the picture stays honest.
    """
    if max_depth is None:
        return node
    return _prune(node, max_depth)


def _prune(node: dict[str, Any], remaining: int) -> dict[str, Any]:
    copy = {key: value for key, value in node.items() if key != "children"}
    children = node.get("children", [])
    if not children:
        return copy
    if remaining <= 1:
        hidden = sum(_count(child) for child in children)
        copy["children"] = [
            {"kind": "token", "text": f"... {hidden} nodos omitidos", "elided": True}
        ]
        return copy
    copy["children"] = [_prune(child, remaining - 1) for child in children]
    return copy


def _count(node: dict[str, Any]) -> int:
    return 1 + sum(_count(child) for child in node.get("children", []))


# ----------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------
_STYLE = """
:root { color-scheme: light dark; }
body { font: 13px/1.5 ui-monospace, Consolas, monospace; margin: 0; padding: 16px; }
h1 { font-size: 15px; margin: 0 0 4px; }
.meta { opacity: .7; margin-bottom: 12px; }
.toolbar { margin-bottom: 12px; display: flex; gap: 12px; flex-wrap: wrap; }
button { font: inherit; padding: 2px 10px; cursor: pointer; }
ul { list-style: none; margin: 0; padding-left: 18px; }
li { position: relative; }
details > summary { cursor: pointer; list-style: none; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: "\\25B8"; display: inline-block; width: 12px; }
details[open] > summary::before { content: "\\25BE"; }
.leaf { padding-left: 12px; }
.rule { font-weight: 600; }
.token { opacity: .85; }
.noise { opacity: .35; }
.type { opacity: .75; font-style: italic; }
.pos { opacity: .5; font-size: 11px; margin-left: 6px; }
.error { color: #b3261e; font-weight: 600; }
.warning { color: #a06000; font-weight: 600; }
.badge { margin-left: 8px; font-size: 11px; }
body.hide-noise .noise { display: none; }
"""

_SCRIPT = """
const root = document.body;
document.getElementById('toggle-noise').addEventListener('click', () => {
  root.classList.toggle('hide-noise');
});
document.getElementById('expand').addEventListener('click', () => {
  document.querySelectorAll('details').forEach(item => { item.open = true; });
});
document.getElementById('collapse').addEventListener('click', () => {
  document.querySelectorAll('details').forEach(item => { item.open = false; });
});
"""


def render_html(node: dict[str, Any], title: str = "Árbol de Compiscript") -> str:
    """Self-contained interactive document; no external resources."""
    safe_title = html.escape(title)
    body = _html_node(node, depth=0)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{safe_title}</title>\n<style>{_STYLE}</style>\n</head>\n"
        f"<body class=\"hide-noise\">\n<h1>{safe_title}</h1>\n"
        '<p class="meta">Los nodos con diagnóstico aparecen resaltados. '
        "La puntuación está oculta; se puede mostrar desde la barra.</p>\n"
        '<div class="toolbar">'
        '<button id="toggle-noise" type="button">Mostrar/ocultar puntuación</button>'
        '<button id="expand" type="button">Expandir todo</button>'
        '<button id="collapse" type="button">Contraer todo</button>'
        "</div>\n"
        f"<ul>{body}</ul>\n"
        f"<script>{_SCRIPT}</script>\n</body>\n</html>\n"
    )


def _html_label(node: dict[str, Any]) -> str:
    classes = ["rule" if node["kind"] == "rule" else "token"]
    if node.get("noise"):
        classes.append("noise")
    diagnostic = node.get("diagnostic")
    if diagnostic is not None:
        classes.append(diagnostic["severity"])

    if node["kind"] == "rule":
        text = html.escape(node["name"])
    else:
        text = html.escape(node["text"])

    parts = [f'<span class="{" ".join(classes)}">{text}</span>']
    if node.get("type"):
        parts.append(f'<span class="type"> : {html.escape(node["type"])}</span>')
    if "line" in node:
        parts.append(f'<span class="pos">{node["line"]}:{node["column"]}</span>')
    if diagnostic is not None:
        message = html.escape(f'{diagnostic["code"]} {diagnostic["message"]}')
        parts.append(f'<span class="badge {diagnostic["severity"]}">{message}</span>')
    return "".join(parts)


def _html_node(node: dict[str, Any], depth: int) -> str:
    children = node.get("children", [])
    if not children:
        return f'<li class="leaf">{_html_label(node)}</li>'
    # The first three levels start expanded; deeper ones stay collapsed.
    open_attribute = " open" if depth < 3 else ""
    inner = "".join(_html_node(child, depth + 1) for child in children)
    return (
        f"<li><details{open_attribute}><summary>{_html_label(node)}</summary>"
        f"<ul>{inner}</ul></details></li>"
    )


# ----------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------
_LEVEL_HEIGHT = 46
_CHAR_WIDTH = 7.2
_GAP = 18


def render_svg(node: dict[str, Any], hide_noise: bool = True) -> str:
    """Static export. Noise tokens are dropped so the picture stays readable."""
    positions: list[dict[str, Any]] = []
    edges: list[tuple[float, float, float, float]] = []
    cursor = [0.0]

    def place(current: dict[str, Any], depth: int) -> float:
        children = visible_children(current, hide_noise)
        width = max(len(label(current)) * _CHAR_WIDTH, 40.0)
        y = depth * _LEVEL_HEIGHT + 24
        if not children:
            x = cursor[0] + width / 2
            cursor[0] += width + _GAP
        else:
            centers = [place(child, depth + 1) for child in children]
            x = (centers[0] + centers[-1]) / 2
            for child_x in centers:
                edges.append((x, y, child_x, y + _LEVEL_HEIGHT))
        positions.append({"node": current, "x": x, "y": y, "width": width})
        return x

    place(node, 0)
    if not positions:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'

    width = max(item["x"] + item["width"] for item in positions) + 20
    height = max(item["y"] for item in positions) + 40

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        "<style>"
        "text{font:12px ui-monospace,Consolas,monospace;text-anchor:middle}"
        ".rule{font-weight:600}.token{opacity:.85}"
        ".error{fill:#b3261e}.warning{fill:#a06000}"
        "line{stroke:#9aa0a6;stroke-width:1}"
        "</style>",
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#ffffff"/>',
    ]
    for x1, y1, x2, y2 in edges:
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1 + 5:.1f}" x2="{x2:.1f}" y2="{y2 - 12:.1f}"/>'
        )
    for item in positions:
        current = item["node"]
        classes = ["rule" if current["kind"] == "rule" else "token"]
        diagnostic = current.get("diagnostic")
        if diagnostic is not None:
            classes.append(diagnostic["severity"])
        text = html.escape(label(current))
        lines.append(
            f'<text class="{" ".join(classes)}" x="{item["x"]:.1f}" '
            f'y="{item["y"]:.1f}">{text}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


def to_json(node: dict[str, Any], indent: int = 2) -> str:
    return json.dumps(node, ensure_ascii=False, indent=indent)


# ----------------------------------------------------------------------
# Graphviz (DOT)
# ----------------------------------------------------------------------
_DOT_HEADER = """digraph Compiscript {
  rankdir=TB;
  graph [bgcolor="white", fontname="Helvetica"];
  node  [fontname="Helvetica", fontsize=10, shape=box, style="rounded,filled",
         fillcolor="#e8eefc", color="#5b7fbd", margin="0.12,0.06"];
  edge  [color="#9aa0a6", arrowsize=0.6];
"""


def _dot_escape(value: str) -> str:
    """Escape a DOT label: backslashes, quotes and real newlines."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return escaped.replace("\n", "\\n")


def _dot_attributes(node: dict[str, Any]) -> str:
    lines = []
    if node["kind"] == "rule":
        lines.append(node["name"])
        if node.get("type"):
            lines.append(f": {node['type']}")
        shape = 'shape=box'
        fill = '"#e8eefc"'
        color = '"#5b7fbd"'
    else:
        lines.append(node["text"])
        shape = 'shape=ellipse'
        fill = '"#f1f3f5"' if not node.get("elided") else '"#ffffff"'
        color = '"#adb5bd"'

    if "line" in node:
        lines.append(f"{node['line']}:{node['column']}")

    diagnostic = node.get("diagnostic")
    if diagnostic is not None:
        lines.append(f"{diagnostic['code']}")
        if diagnostic["severity"] == "warning":
            fill, color = '"#fff3cd"', '"#a06000"'
        else:
            fill, color = '"#fde2e1"', '"#b3261e"'

    label = _dot_escape("\n".join(lines))
    return f'[label="{label}", {shape}, fillcolor={fill}, color={color}]'


def render_dot(
    node: dict[str, Any], hide_noise: bool = True, max_depth: Optional[int] = None
) -> str:
    """Graphviz DOT source of the tree.

    Render it with, for example::

        dot -Tsvg arbol.dot -o arbol.svg

    Only the standard library is used to build the file; Graphviz is needed
    to turn it into an image, never to produce the source.
    """
    root = prune(node, max_depth)
    lines = [_DOT_HEADER]
    counter = [0]

    def walk(current: dict[str, Any]) -> str:
        identifier = f"n{counter[0]}"
        counter[0] += 1
        lines.append(f"  {identifier} {_dot_attributes(current)};")
        for child in visible_children(current, hide_noise):
            child_id = walk(child)
            lines.append(f"  {identifier} -> {child_id};")
        return identifier

    walk(root)
    lines.append("}")
    return "\n".join(lines) + "\n"
