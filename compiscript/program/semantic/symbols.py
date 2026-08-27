"""Symbols stored in the Compiscript symbol table.

Every symbol keeps the data required by the current semantic phase plus a
reserved block (``offset``, ``size``, ``storage``, ``label``) that the future
TAC and MIPS phases can fill in without changing this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .types import ERROR, ClassType, FunctionType, Type


class SymbolCategory(str, Enum):
    VARIABLE = "variable"
    CONSTANT = "constant"
    PARAMETER = "parameter"
    FUNCTION = "function"
    CLASS = "class"
    ATTRIBUTE = "attribute"
    METHOD = "method"


@dataclass
class Symbol:
    name: str
    type: Type = ERROR
    line: int = 0
    column: int = 0
    category: SymbolCategory = SymbolCategory.VARIABLE
    mutable: bool = True
    scope_name: str = "global"
    initialized: bool = False
    # Reserved for the TAC and MIPS phases.
    offset: Optional[int] = None
    size: Optional[int] = None
    storage: Optional[str] = None
    label: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "type": str(self.type),
            "line": self.line,
            "column": self.column,
            "scope": self.scope_name,
            "mutable": self.mutable,
            "initialized": self.initialized,
            "offset": self.offset,
            "size": self.size,
            "storage": self.storage,
            "label": self.label,
        }


@dataclass
class VariableSymbol(Symbol):
    category: SymbolCategory = SymbolCategory.VARIABLE
    mutable: bool = True


@dataclass
class ConstantSymbol(Symbol):
    category: SymbolCategory = SymbolCategory.CONSTANT
    mutable: bool = False


@dataclass
class ParameterSymbol(Symbol):
    category: SymbolCategory = SymbolCategory.PARAMETER
    mutable: bool = True
    initialized: bool = True
    index: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload["index"] = self.index
        return payload


@dataclass
class FunctionSymbol(Symbol):
    category: SymbolCategory = SymbolCategory.FUNCTION
    mutable: bool = False
    initialized: bool = True
    parameters: list[ParameterSymbol] = field(default_factory=list)
    return_type: Type = ERROR
    return_annotated: bool = False
    owner_class: Optional[str] = None
    captured: list[str] = field(default_factory=list)
    body_scope: Any = None

    @property
    def signature(self) -> FunctionType:
        return FunctionType([item.type for item in self.parameters], self.return_type)

    def capture(self, name: str) -> None:
        if name not in self.captured:
            self.captured.append(name)

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload.update(
            {
                "signature": str(self.signature),
                "parameters": [item.as_dict() for item in self.parameters],
                "returnType": str(self.return_type),
                "ownerClass": self.owner_class,
                "captured": list(self.captured),
            }
        )
        return payload


@dataclass
class AttributeSymbol(Symbol):
    category: SymbolCategory = SymbolCategory.ATTRIBUTE
    owner_class: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload["ownerClass"] = self.owner_class
        return payload


@dataclass
class MethodSymbol(FunctionSymbol):
    category: SymbolCategory = SymbolCategory.METHOD


@dataclass
class ClassSymbol(Symbol):
    category: SymbolCategory = SymbolCategory.CLASS
    mutable: bool = False
    initialized: bool = True
    parent_name: Optional[str] = None
    parent: Optional["ClassSymbol"] = None
    attributes: dict[str, AttributeSymbol] = field(default_factory=dict)
    methods: dict[str, MethodSymbol] = field(default_factory=dict)
    constructor: Optional[MethodSymbol] = None
    class_scope: Any = None

    @property
    def class_type(self) -> ClassType:
        assert isinstance(self.type, ClassType)
        return self.type

    def ancestors(self) -> list["ClassSymbol"]:
        chain: list[ClassSymbol] = []
        seen: set[str] = {self.name}
        current = self.parent
        while current is not None and current.name not in seen:
            seen.add(current.name)
            chain.append(current)
            current = current.parent
        return chain

    def lookup_attribute(self, name: str) -> Optional[AttributeSymbol]:
        if name in self.attributes:
            return self.attributes[name]
        for ancestor in self.ancestors():
            if name in ancestor.attributes:
                return ancestor.attributes[name]
        return None

    def lookup_method(self, name: str) -> Optional[MethodSymbol]:
        if name in self.methods:
            return self.methods[name]
        for ancestor in self.ancestors():
            if name in ancestor.methods:
                return ancestor.methods[name]
        return None

    def lookup_constructor(self) -> Optional[MethodSymbol]:
        if self.constructor is not None:
            return self.constructor
        for ancestor in self.ancestors():
            if ancestor.constructor is not None:
                return ancestor.constructor
        return None

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload.update(
            {
                "parent": self.parent_name,
                "attributes": [item.as_dict() for item in self.attributes.values()],
                "methods": [item.as_dict() for item in self.methods.values()],
                "constructor": self.constructor.as_dict() if self.constructor else None,
            }
        )
        return payload
