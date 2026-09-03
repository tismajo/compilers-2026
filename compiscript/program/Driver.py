"""Command-line frontend for the Compiscript compiler.

Parsing is kept separate from semantic analysis: the tree produced here is
handed to ``semantic.analyze`` without parsing the source a second time.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from antlr4 import CommonTokenStream, FileStream
from antlr4.error.ErrorListener import ErrorListener

from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
import treeview
from semantic import analyze
from semantic.diagnostics import Diagnostic
from semantic.symbol_table import SymbolTable

__all__ = ["Diagnostic", "AnalysisResult", "analyze_file", "main"]


@dataclass
class AnalysisResult:
    source: str
    tree: Any | None = None
    parser: CompiscriptParser | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    symbols: SymbolTable | None = None
    types: dict[int, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)

    @property
    def phase(self) -> str:
        return "semantic" if self.symbols is not None else "syntax"

    def tree_as_dict(self) -> dict[str, Any]:
        """Parse tree enriched with inferred types and diagnostic marks."""
        return treeview.serialize(
            self.tree, self.parser, self.types, self.diagnostics
        )

    def as_dict(
        self, tree_format: str = "none", symbol_format: str = "none"
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "source": self.source,
            "phase": self.phase,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }
        if self.tree is not None and self.parser is not None:
            if tree_format == "lisp":
                payload["tree"] = self.tree.toStringTree(recog=self.parser)
            elif tree_format == "json":
                payload["tree"] = self.tree_as_dict()
            elif tree_format in ("html", "svg", "dot"):
                payload["treeFormat"] = tree_format
        if self.symbols is not None and symbol_format == "json":
            payload["symbols"] = self.symbols.as_dict()
        return payload


class CollectingErrorListener(ErrorListener):
    def __init__(self, phase: str, code: str) -> None:
        super().__init__()
        self.phase = phase
        self.code = code
        self.diagnostics: list[Diagnostic] = []

    def syntaxError(
        self,
        recognizer: Any,
        offendingSymbol: Any,
        line: int,
        column: int,
        msg: str,
        exc: Exception | None,
    ) -> None:
        del recognizer, offendingSymbol, exc
        self.diagnostics.append(
            Diagnostic(
                code=self.code,
                phase=self.phase,
                severity="error",
                message=msg,
                line=line,
                column=column + 1,
            )
        )


def analyze_file(source_path: str | Path, semantic: bool = True) -> AnalysisResult:
    path = Path(source_path)
    lexer_errors = CollectingErrorListener("lexer", "LEX001")
    parser_errors = CollectingErrorListener("parser", "SYN001")

    input_stream = FileStream(str(path), encoding="utf-8")
    lexer = CompiscriptLexer(input_stream)
    lexer.removeErrorListeners()
    lexer.addErrorListener(lexer_errors)

    token_stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(token_stream)
    parser.removeErrorListeners()
    parser.addErrorListener(parser_errors)
    tree = parser.program()

    result = AnalysisResult(
        source=str(path),
        tree=tree,
        parser=parser,
        diagnostics=lexer_errors.diagnostics + parser_errors.diagnostics,
    )

    # A broken parse tree would produce meaningless semantic diagnostics.
    if semantic and result.success:
        semantic_result = analyze(tree)
        result.symbols = semantic_result.symbols
        result.types = semantic_result.types
        result.diagnostics.extend(semantic_result.diagnostics)

    return result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a Compiscript source file")
    parser.add_argument("source", help="Path to a .cps source file")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Diagnostic output format",
    )
    parser.add_argument(
        "--tree",
        choices=("none", "lisp", "json", "html", "svg", "dot"),
        default="none",
        help="Include the parse tree: Lisp, JSON, interactive HTML, SVG or Graphviz DOT",
    )
    parser.add_argument(
        "--tree-compact",
        action="store_true",
        help="Collapse the precedence chains of the grammar in the tree exports",
    )
    parser.add_argument(
        "--tree-depth",
        type=int,
        default=None,
        help="Limit the depth of the SVG and DOT exports",
    )
    parser.add_argument(
        "--tree-out",
        default=None,
        help="Write the tree to this file instead of printing it",
    )
    parser.add_argument(
        "--symbols",
        choices=("none", "text", "json"),
        default="none",
        help="Include the symbol table in the output",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Stop after the syntax phase",
    )
    return parser


def tree_document(
    result: AnalysisResult,
    tree_format: str,
    path: Path,
    payload: dict[str, Any],
    max_depth: int | None = None,
    compact: bool = False,
) -> str | None:
    """Textual form of the tree for the requested format, if any."""
    if tree_format == "none" or result.tree is None:
        return None
    # Compacting first, so the depth limit counts the levels actually drawn.
    tree = result.tree_as_dict()
    if compact and tree_format in ("html", "svg", "dot"):
        tree = treeview.compact(tree)
    if tree_format == "html":
        return treeview.render_html(
            treeview.prune(tree, max_depth), f"Árbol de {path.name}"
        )
    if tree_format == "svg":
        return treeview.render_svg(treeview.prune(tree, max_depth))
    if tree_format == "dot":
        return treeview.render_dot(tree, max_depth=max_depth)
    if tree_format == "json":
        return treeview.to_json(payload.get("tree", tree))
    return payload.get("tree")


def force_utf8_output() -> None:
    """Diagnostics are written in Spanish; keep them readable on any console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    force_utf8_output()
    args = build_argument_parser().parse_args(argv)
    path = Path(args.source)

    if not path.is_file():
        diagnostic = Diagnostic(
            code="CLI001",
            phase="cli",
            severity="error",
            message=f"Source file not found: {path}",
            line=1,
            column=1,
        )
        payload = {
            "success": False,
            "source": str(path),
            "phase": "cli",
            "diagnostics": [diagnostic.as_dict()],
        }
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"{path}:1:1: error CLI001: {diagnostic.message}", file=sys.stderr)
        return 2

    result = analyze_file(path, semantic=not args.no_semantic)
    payload = result.as_dict(args.tree, args.symbols)

    document = tree_document(
        result, args.tree, path, payload, args.tree_depth, args.tree_compact
    )
    if document is not None and args.tree_out:
        Path(args.tree_out).write_text(document, encoding="utf-8")
        print(f"Árbol escrito en {args.tree_out}")
        document = None

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for diagnostic in result.diagnostics:
            print(
                f"{path}:{diagnostic.line}:{diagnostic.column}: "
                f"{diagnostic.severity} {diagnostic.code}: {diagnostic.message}",
                file=sys.stderr,
            )
        if document is not None:
            print(document)
        if args.symbols != "none" and result.symbols is not None:
            if args.symbols == "json":
                print(json.dumps(result.symbols.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(result.symbols.render())

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
