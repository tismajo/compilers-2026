"""Entry point of the semantic analysis.

``analyze`` runs the two passes over an already built parse tree, so the CLI
never parses the same file twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .checker import Checker
from .collector import Collector
from .diagnostics import Diagnostic, DiagnosticBag
from .symbol_table import SymbolTable
from .symbols import Symbol
from .types import Type


@dataclass
class SemanticResult:
    symbols: SymbolTable
    diagnostics: list[Diagnostic] = field(default_factory=list)
    # ``id(ctx) -> type name`` for every typed expression node.
    types: dict[int, str] = field(default_factory=dict)
    # Consumed by the TAC generator: ``id(ctx) -> Type`` for expressions,
    # ``id(ctx) -> Symbol`` for identifiers and declarations.
    type_objects: dict[int, Type] = field(default_factory=dict)
    bindings: dict[int, Symbol] = field(default_factory=dict)
    declared: dict[int, Symbol] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)


def analyze(program_ctx: Any) -> SemanticResult:
    table = SymbolTable()
    bag = DiagnosticBag()

    collector = Collector(table, bag)
    collector.run(program_ctx)

    checker = Checker(table, bag, collector.declared)
    checker.run(program_ctx)

    return SemanticResult(
        symbols=table,
        diagnostics=bag.sorted_items(),
        types=checker.types,
        type_objects=checker.type_objects,
        bindings=checker.bindings,
        declared=checker.declared,
    )
