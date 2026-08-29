"""Helpers to read positions and type annotations from the ANTLR parse tree.

The project walks the parse tree directly, so these helpers are the only place
that touches ANTLR context objects when a type or a source position is needed.
"""

from __future__ import annotations

from typing import Any, Optional

from .diagnostics import DiagnosticBag
from .types import BUILTIN_TYPES, ERROR, ArrayType, ClassType, Type


def position(node: Any) -> tuple[int, int]:
    """Return the 1-based ``(line, column)`` of a context or terminal node."""
    token = getattr(node, "symbol", None)
    if token is None:
        token = getattr(node, "start", None)
    if token is None:
        return (0, 0)
    return (token.line, token.column + 1)


class TypeResolver:
    """Turns ``type`` annotations into :class:`~semantic.types.Type` values."""

    def __init__(self, classes: dict[str, Any], bag: DiagnosticBag) -> None:
        self.classes = classes
        self.bag = bag

    def resolve(self, type_ctx: Any) -> Type:
        if type_ctx is None:
            return ERROR
        base_ctx = type_ctx.baseType()
        resolved = self._resolve_base(base_ctx)
        # ``type: baseType ('[' ']')*`` - one array level per bracket pair.
        brackets = type_ctx.getText().count("[")
        for _ in range(brackets):
            resolved = ArrayType(resolved)
        return resolved

    def _resolve_base(self, base_ctx: Any) -> Type:
        name = base_ctx.getText()
        builtin = BUILTIN_TYPES.get(name)
        if builtin is not None:
            return builtin
        symbol = self.classes.get(name)
        if symbol is not None:
            return symbol.type
        line, column = position(base_ctx)
        self.bag.add(
            "SEM209",
            f"El tipo '{name}' no existe",
            line,
            column,
        )
        return ERROR

    def class_type(self, name: str) -> Optional[ClassType]:
        symbol = self.classes.get(name)
        if symbol is None:
            return None
        found = symbol.type
        return found if isinstance(found, ClassType) else None
