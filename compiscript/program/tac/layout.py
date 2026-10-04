"""Runtime layout: addresses for every symbol and one activation record per function.

Conventions (documented in ``docs/lenguaje-intermedio.md``):

* ``float`` takes 8 bytes; ``integer``, ``boolean`` and every reference
  (``string``, arrays, objects, functions) take one 4-byte word.
* Globals live in a static data segment: ``storage="global"``, offset from its
  start.
* Parameters and locals live in the frame of their function:
  ``storage="stack"``. Parameters sit above the frame pointer
  (``fp+8``, ``fp+12``...), locals below it (``fp-4``, ``fp-8``...).
  ``fp+0`` keeps the caller's ``fp`` (control link) and ``fp+4`` the return
  address. Methods receive ``this`` as the first parameter at ``fp+8``.
* Attributes live in the object: ``storage="heap"``. Offset 0 holds the class
  descriptor, so attributes start at 4, inherited ones first.
* Shadowed symbols in nested blocks get their own slot; slots are not shared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from semantic.scopes import Scope, ScopeKind
from semantic.symbol_table import SymbolTable
from semantic.symbols import (
    ClassSymbol,
    FunctionSymbol,
    MethodSymbol,
    ParameterSymbol,
    Symbol,
)
from semantic.types import FLOAT, VOID, Type

WORD = 4
FRAME_HEADER = 2 * WORD  # control link + return address
OBJECT_HEADER = WORD  # class descriptor
TEMP_SIZE = WORD


def size_of(value_type: Type) -> int:
    if value_type == FLOAT:
        return 8
    if value_type == VOID:
        return 0
    return WORD


@dataclass
class Slot:
    name: str
    offset: int
    size: int

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "offset": self.offset, "size": self.size}


@dataclass
class ActivationRecord:
    """Frame of one function: what the caller pushes and what the callee reserves."""

    name: str
    label: str
    kind: str = "function"
    parameters: list[Slot] = field(default_factory=list)
    locals: list[Slot] = field(default_factory=list)
    temps: int = 0
    captured: list[str] = field(default_factory=list)

    @property
    def parameters_size(self) -> int:
        return sum(item.size for item in self.parameters)

    @property
    def locals_size(self) -> int:
        return sum(item.size for item in self.locals)

    @property
    def temps_size(self) -> int:
        return self.temps * TEMP_SIZE

    @property
    def frame_size(self) -> int:
        """Bytes the callee reserves: header, locals and spilled temporaries."""
        return FRAME_HEADER + self.locals_size + self.temps_size

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "controlLink": "fp+0",
            "returnAddress": "fp+4",
            "parameters": [item.as_dict() for item in self.parameters],
            "locals": [item.as_dict() for item in self.locals],
            "temps": self.temps,
            "parametersSize": self.parameters_size,
            "localsSize": self.locals_size,
            "frameSize": self.frame_size,
            "captured": list(self.captured),
        }

    def render(self) -> str:
        lines = [f"frame {self.label} ({self.kind}) — {self.frame_size} bytes"]
        for item in self.parameters:
            lines.append(f"  param {item.name}: fp+{item.offset} ({item.size}B)")
        for item in self.locals:
            lines.append(f"  local {item.name}: fp{item.offset} ({item.size}B)")
        lines.append(f"  temps: {self.temps} × {TEMP_SIZE}B")
        return "\n".join(lines)


class Layout:
    """Fills ``offset``/``size``/``storage``/``label`` and builds the frames."""

    def __init__(self, table: SymbolTable) -> None:
        self.table = table
        self.records: dict[int, ActivationRecord] = {}
        self.globals_size = 0
        self._class_sizes: dict[str, int] = {}

    def run(self) -> "Layout":
        for symbol in self.table.classes.values():
            self._lay_out_class(symbol)
        self._walk(self.table.global_scope, None, [])
        self.table.activation_records = list(self.records.values())
        self.table.globals_size = self.globals_size
        return self

    def record_for(self, function: FunctionSymbol) -> ActivationRecord:
        return self.records[id(function)]

    # -- scopes ---------------------------------------------------------
    def _walk(
        self,
        scope: Scope,
        record: Optional[ActivationRecord],
        owners: list[str],
    ) -> None:
        if scope.kind == ScopeKind.CLASS:
            owners = owners + [scope.name]
        elif scope.kind == ScopeKind.FUNCTION and scope.function_owner is not None:
            function = scope.function_owner
            record = self._open_record(function, owners)
            owners = owners + [function.name]

        for symbol in scope.symbols.values():
            self._place(symbol, record, owners)
        for child in scope.children:
            self._walk(child, record, owners)

    def _place(
        self, symbol: Symbol, record: Optional[ActivationRecord], owners: list[str]
    ) -> None:
        if isinstance(symbol, FunctionSymbol):
            symbol.storage = "code"
            symbol.size = 0
            symbol.label = self._function_label(symbol, owners)
            return
        if isinstance(symbol, ClassSymbol):
            symbol.storage = "heap"
            symbol.size = self._class_sizes.get(symbol.name, OBJECT_HEADER)
            symbol.label = symbol.name
            return
        if symbol.category.value == "attribute":
            return  # placed by ``_lay_out_class``
        if isinstance(symbol, ParameterSymbol):
            return  # placed when the record is opened
        size = size_of(symbol.type)
        symbol.size = size
        if record is None:
            symbol.storage = "global"
            symbol.offset = self.globals_size
            self.globals_size += size
            return
        symbol.storage = "stack"
        symbol.offset = -(record.locals_size + size)
        record.locals.append(Slot(symbol.name, symbol.offset, size))

    def _open_record(self, function: FunctionSymbol, owners: list[str]) -> ActivationRecord:
        is_method = isinstance(function, MethodSymbol)
        record = ActivationRecord(
            name=function.name,
            label=self._function_label(function, owners),
            kind="method" if is_method else "function",
            captured=list(function.captured),
        )
        function.label = record.label
        offset = FRAME_HEADER
        if is_method:
            record.parameters.append(Slot("this", offset, WORD))
            offset += WORD
        for parameter in function.parameters:
            size = size_of(parameter.type)
            parameter.storage = "stack"
            parameter.size = size
            parameter.offset = offset
            record.parameters.append(Slot(parameter.name, offset, size))
            offset += size
        self.records[id(function)] = record
        return record

    @staticmethod
    def _function_label(function: FunctionSymbol, owners: list[str]) -> str:
        if isinstance(function, MethodSymbol) and function.owner_class:
            return f"{function.owner_class}_{function.name}"
        return "f_" + "_".join(owners + [function.name])

    # -- objects --------------------------------------------------------
    def _lay_out_class(self, symbol: ClassSymbol) -> int:
        if symbol.name in self._class_sizes:
            return self._class_sizes[symbol.name]
        self._class_sizes[symbol.name] = OBJECT_HEADER  # guards inheritance cycles
        offset = self._lay_out_class(symbol.parent) if symbol.parent else OBJECT_HEADER
        for attribute in symbol.attributes.values():
            size = size_of(attribute.type)
            attribute.storage = "heap"
            attribute.size = size
            attribute.offset = offset
            offset += size
        self._class_sizes[symbol.name] = offset
        return offset


def assign_addresses(table: SymbolTable) -> Layout:
    return Layout(table).run()
