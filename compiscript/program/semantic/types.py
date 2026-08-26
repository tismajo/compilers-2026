"""Type model for Compiscript.

The analyzer walks the ANTLR parse tree directly, so this module is the only
place that knows how Compiscript types relate to each other. Later phases
(TAC, MIPS) can reuse it without touching the parse tree.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence


class Type:
    """Base of every Compiscript type."""

    name: str = "?"

    @property
    def is_error(self) -> bool:
        return False

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.__class__.__name__} {self}>"


class PrimitiveType(Type):
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PrimitiveType) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("primitive", self.name))


class ErrorType(Type):
    """Absorbing type used to stop cascading diagnostics."""

    name = "error"

    @property
    def is_error(self) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ErrorType)

    def __hash__(self) -> int:
        return hash("error")


class ArrayType(Type):
    def __init__(self, element: Type) -> None:
        self.element = element

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"{self.element}[]"

    @property
    def dimensions(self) -> int:
        return 1 + self.element.dimensions if isinstance(self.element, ArrayType) else 1

    @property
    def base_element(self) -> Type:
        current: Type = self.element
        while isinstance(current, ArrayType):
            current = current.element
        return current

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ArrayType) and other.element == self.element

    def __hash__(self) -> int:
        return hash(("array", self.element))


class ClassType(Type):
    """Nominal type of a Compiscript class.

    ``symbol`` is filled in by the collector with the matching ``ClassSymbol``;
    it is kept as ``Any`` so this module stays free of import cycles.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.parent: Optional["ClassType"] = None
        self.symbol: Any = None

    def ancestors(self) -> Iterable["ClassType"]:
        seen: set[str] = set()
        current = self.parent
        while current is not None and current.name not in seen:
            seen.add(current.name)
            yield current
            current = current.parent

    def is_subclass_of(self, other: "ClassType") -> bool:
        if self.name == other.name:
            return True
        return any(item.name == other.name for item in self.ancestors())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ClassType) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("class", self.name))


class FunctionType(Type):
    def __init__(self, parameters: Sequence[Type], return_type: Type) -> None:
        self.parameters = tuple(parameters)
        self.return_type = return_type

    @property
    def name(self) -> str:  # type: ignore[override]
        joined = ", ".join(str(item) for item in self.parameters)
        return f"({joined}) -> {self.return_type}"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FunctionType)
            and other.parameters == self.parameters
            and other.return_type == self.return_type
        )

    def __hash__(self) -> int:
        return hash(("function", self.parameters, self.return_type))


INTEGER = PrimitiveType("integer")
FLOAT = PrimitiveType("float")
STRING = PrimitiveType("string")
BOOLEAN = PrimitiveType("boolean")
NULL = PrimitiveType("null")
VOID = PrimitiveType("void")
ERROR = ErrorType()

BUILTIN_TYPES = {
    "integer": INTEGER,
    "float": FLOAT,
    "string": STRING,
    "boolean": BOOLEAN,
    "void": VOID,
}


def is_numeric(candidate: Type) -> bool:
    return candidate in (INTEGER, FLOAT)


def is_printable(candidate: Type) -> bool:
    """Types accepted by ``print`` and by string concatenation."""
    if candidate.is_error:
        return True
    if candidate in (INTEGER, FLOAT, STRING, BOOLEAN, NULL):
        return True
    return isinstance(candidate, (ArrayType, ClassType))


def is_assignable(target: Type, value: Type) -> bool:
    """Return whether a value of type ``value`` can be stored in ``target``."""
    if target.is_error or value.is_error:
        return True
    if target == value:
        return True
    if target == FLOAT and value == INTEGER:
        return True
    if value == NULL:
        return isinstance(target, (ClassType, ArrayType, FunctionType))
    if isinstance(target, ClassType) and isinstance(value, ClassType):
        return value.is_subclass_of(target)
    if isinstance(target, ArrayType) and isinstance(value, ArrayType):
        if target.element.is_error or value.element.is_error:
            return True
        return target.element == value.element
    return False


def is_comparable(left: Type, right: Type) -> bool:
    """Types accepted by ``==`` and ``!=``."""
    if left.is_error or right.is_error:
        return True
    if left == right:
        return True
    if is_numeric(left) and is_numeric(right):
        return True
    if NULL in (left, right):
        other = right if left == NULL else left
        return isinstance(other, (ClassType, ArrayType, FunctionType)) or other == NULL
    if isinstance(left, ClassType) and isinstance(right, ClassType):
        return left.is_subclass_of(right) or right.is_subclass_of(left)
    return False


def arithmetic_result(left: Type, right: Type) -> Type:
    """Result of a numeric operation; ``FLOAT`` wins over ``INTEGER``."""
    if left.is_error or right.is_error:
        return ERROR
    if not (is_numeric(left) and is_numeric(right)):
        return ERROR
    return FLOAT if FLOAT in (left, right) else INTEGER


def common_type(left: Type, right: Type) -> Optional[Type]:
    """Least type able to hold both operands, or ``None`` when incompatible."""
    if left.is_error:
        return right
    if right.is_error:
        return left
    if left == right:
        return left
    if is_numeric(left) and is_numeric(right):
        return FLOAT
    if left == NULL:
        return right if isinstance(right, (ClassType, ArrayType, FunctionType)) else None
    if right == NULL:
        return left if isinstance(left, (ClassType, ArrayType, FunctionType)) else None
    if isinstance(left, ClassType) and isinstance(right, ClassType):
        if right.is_subclass_of(left):
            return left
        if left.is_subclass_of(right):
            return right
        for ancestor in left.ancestors():
            if right.is_subclass_of(ancestor):
                return ancestor
        return None
    if isinstance(left, ArrayType) and isinstance(right, ArrayType):
        element = common_type(left.element, right.element)
        return ArrayType(element) if element is not None else None
    return None
