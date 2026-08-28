"""Scopes and the analysis environment.

A scope is created for the program itself and for every block, function, class,
``foreach`` and ``catch``. The :class:`Environment` keeps the walking state that
the semantic passes need: current scope, current function, current class, loop
depth and switch depth.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterator, Optional

from .symbols import ClassSymbol, FunctionSymbol, Symbol


class ScopeKind(str, Enum):
    GLOBAL = "global"
    BLOCK = "block"
    FUNCTION = "function"
    CLASS = "class"
    FOREACH = "foreach"
    CATCH = "catch"


class Scope:
    """A lexical scope holding symbols and a link to its parent."""

    def __init__(
        self,
        kind: ScopeKind,
        name: str,
        parent: Optional["Scope"] = None,
        line: int = 0,
        column: int = 0,
        function_owner: Optional[FunctionSymbol] = None,
    ) -> None:
        self.kind = kind
        self.name = name
        self.parent = parent
        self.line = line
        self.column = column
        self.symbols: dict[str, Symbol] = {}
        self.children: list[Scope] = []
        # Function whose body this scope belongs to; ``None`` at global level.
        self.function_owner = function_owner
        if parent is not None:
            parent.children.append(self)
            if function_owner is None:
                self.function_owner = parent.function_owner

    @property
    def qualified_name(self) -> str:
        if self.parent is None:
            return self.name
        return f"{self.parent.qualified_name}.{self.name}"

    def define(self, symbol: Symbol) -> Optional[Symbol]:
        """Insert ``symbol``; return the clashing symbol when already defined."""
        existing = self.symbols.get(symbol.name)
        if existing is not None:
            return existing
        symbol.scope_name = self.qualified_name
        self.symbols[symbol.name] = symbol
        return None

    def resolve_local(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

    def resolve(self, name: str) -> Optional[Symbol]:
        for scope in self.lineage():
            found = scope.symbols.get(name)
            if found is not None:
                return found
        return None

    def resolve_scope(self, name: str) -> Optional["Scope"]:
        for scope in self.lineage():
            if name in scope.symbols:
                return scope
        return None

    def lineage(self) -> Iterator["Scope"]:
        current: Optional[Scope] = self
        while current is not None:
            yield current
            current = current.parent

    def walk(self) -> Iterator["Scope"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "qualifiedName": self.qualified_name,
            "line": self.line,
            "column": self.column,
            "symbols": [item.as_dict() for item in self.symbols.values()],
            "children": [child.as_dict() for child in self.children],
        }

    def render(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = [f"{pad}[{self.kind.value}] {self.qualified_name}"]
        for symbol in self.symbols.values():
            lines.append(
                f"{pad}  - {symbol.category.value} {symbol.name}: {symbol.type} "
                f"({symbol.line}:{symbol.column})"
            )
        for child in self.children:
            lines.append(child.render(indent + 1))
        return "\n".join(lines)


class Environment:
    """Mutable walking state shared by the two semantic passes."""

    def __init__(self) -> None:
        self.global_scope = Scope(ScopeKind.GLOBAL, "global", line=1, column=1)
        self.current: Scope = self.global_scope
        self.function_stack: list[FunctionSymbol] = []
        self.class_stack: list[ClassSymbol] = []
        self.loop_depth = 0
        self.switch_depth = 0

    # -- scope handling -------------------------------------------------
    def push(
        self,
        kind: ScopeKind,
        name: str,
        line: int = 0,
        column: int = 0,
        function_owner: Optional[FunctionSymbol] = None,
    ) -> Scope:
        scope = Scope(kind, name, self.current, line, column, function_owner)
        self.current = scope
        return scope

    def pop(self) -> None:
        if self.current.parent is not None:
            self.current = self.current.parent

    # -- context --------------------------------------------------------
    @property
    def current_function(self) -> Optional[FunctionSymbol]:
        return self.function_stack[-1] if self.function_stack else None

    @property
    def current_class(self) -> Optional[ClassSymbol]:
        return self.class_stack[-1] if self.class_stack else None

    @property
    def inside_loop(self) -> bool:
        return self.loop_depth > 0

    @property
    def inside_switch(self) -> bool:
        return self.switch_depth > 0

    # -- resolution -----------------------------------------------------
    def define(self, symbol: Symbol) -> Optional[Symbol]:
        return self.current.define(symbol)

    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve ``name`` and record closure captures when crossing functions."""
        owner_scope = self.current.resolve_scope(name)
        if owner_scope is None:
            return None
        self._record_capture(name, owner_scope)
        return owner_scope.symbols[name]

    def _record_capture(self, name: str, owner_scope: Scope) -> None:
        holder = owner_scope.function_owner
        for function in reversed(self.function_stack):
            if function is holder:
                break
            function.capture(name)
