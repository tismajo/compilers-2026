"""The symbol table exposed to the CLI, the tests and the VS Code extension."""

from __future__ import annotations

from typing import Any, Iterator, Optional

from .scopes import Environment, Scope
from .symbols import ClassSymbol, Symbol


class SymbolTable:
    """Facade over the scope tree built by the semantic passes."""

    def __init__(self, environment: Optional[Environment] = None) -> None:
        self.environment = environment or Environment()
        self.classes: dict[str, ClassSymbol] = {}
        # Filled by ``tac.layout`` when intermediate code is generated.
        self.activation_records: list[Any] = []
        self.globals_size: Optional[int] = None

    @property
    def global_scope(self) -> Scope:
        return self.environment.global_scope

    def register_class(self, symbol: ClassSymbol) -> None:
        self.classes[symbol.name] = symbol

    def lookup_class(self, name: str) -> Optional[ClassSymbol]:
        return self.classes.get(name)

    def scopes(self) -> Iterator[Scope]:
        return self.global_scope.walk()

    def symbols(self) -> Iterator[Symbol]:
        for scope in self.scopes():
            yield from scope.symbols.values()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "scopes": self.global_scope.as_dict(),
            "classes": [item.as_dict() for item in self.classes.values()],
        }
        if self.globals_size is not None:
            payload["globalsSize"] = self.globals_size
            payload["activationRecords"] = [
                item.as_dict() for item in self.activation_records
            ]
        return payload

    def render(self) -> str:
        text = self.global_scope.render()
        if self.globals_size is None:
            return text
        frames = [f"globals: {self.globals_size} bytes"]
        frames.extend(item.render() for item in self.activation_records)
        return text + "\n\n" + "\n".join(frames)
