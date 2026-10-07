"""Quadruples and the program that groups them by function.

Every instruction is stored as ``Quad(op, arg1, arg2, result)`` and printed in
the three-address notation described in ``docs/lenguaje-intermedio.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

BINARY_OPS = {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="}
UNARY_OPS = {"minus": "-", "not": "!"}
CONVERSIONS = {"itof", "tostr"}


@dataclass
class Quad:
    op: str
    arg1: Optional[str] = None
    arg2: Optional[str] = None
    result: Optional[str] = None

    def render(self) -> str:
        op, a, b, r = self.op, self.arg1, self.arg2, self.result
        if op == "label":
            return f"{a}:"
        if op == "assign":
            return f"{r} = {a}"
        if op in BINARY_OPS:
            return f"{r} = {a} {op} {b}"
        if op in UNARY_OPS:
            return f"{r} = {UNARY_OPS[op]} {a}"
        if op in CONVERSIONS:
            return f"{r} = {op} {a}"
        if op == "concat":
            return f"{r} = concat {a}, {b}"
        if op == "goto":
            return f"goto {a}"
        if op == "if_false":
            return f"ifFalse {a} goto {b}"
        if op == "if_true":
            return f"if {a} goto {b}"
        if op == "param":
            return f"param {a}"
        if op == "call":
            return f"{r} = call {a}, {b}" if r else f"call {a}, {b}"
        if op == "calli":
            return f"{r} = calli {a}, {b}" if r else f"calli {a}, {b}"
        if op == "alloc":
            return f"{r} = alloc {a}"
        if op == "load":
            # Raw byte-offset memory access (array/object header, element,
            # attribute, vtable slot) — deliberately not ``a[b]``, which would
            # read as source-level indexing and is a different thing (that is
            # ``offset = idx*stride + header`` computed first, then loaded).
            return f"{r} = *({a} + {b})"
        if op == "store":
            return f"*({a} + {b}) = {r}"
        if op == "halt":
            return "halt"
        if op == "return":
            return f"return {a}" if a is not None else "return"
        if op == "print":
            return f"print {a}"
        if op == "begin_func":
            return f"begin_func {a}"
        if op == "end_func":
            return "end_func"
        if op == "comment":
            return f"# {a}"
        if op == "todo":
            return f"{r} = ?  # TODO {a}" if r else f"# TODO {a}"
        return f"{op} {a} {b} {r}"  # pragma: no cover - unknown op

    def as_dict(self) -> dict[str, Any]:
        return {"op": self.op, "arg1": self.arg1, "arg2": self.arg2, "result": self.result}


@dataclass
class FunctionCode:
    name: str
    label: str
    record: Any = None
    quads: list[Quad] = field(default_factory=list)

    def emit(self, op: str, arg1: Any = None, arg2: Any = None, result: Any = None) -> Quad:
        quad = Quad(
            op,
            None if arg1 is None else str(arg1),
            None if arg2 is None else str(arg2),
            None if result is None else str(result),
        )
        self.quads.append(quad)
        return quad

    def lines(self) -> list[str]:
        rendered = [f"{self.label}:"]
        for quad in self.quads:
            text = quad.render()
            rendered.append(text if quad.op == "label" else f"    {text}")
        return rendered

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "frame": self.record.as_dict() if self.record is not None else None,
            "quads": [item.as_dict() for item in self.quads],
        }


@dataclass
class VTableData:
    """Static dispatch table of one class: ``slots[i]`` is the label called
    for the method at index ``i``, overridden in place by subclasses so every
    class in the hierarchy agrees on the index of a given method name."""

    class_name: str
    label: str
    slots: list[str] = field(default_factory=list)

    def render(self) -> str:
        return f"vtable {self.label}: [{', '.join(self.slots)}]"

    def as_dict(self) -> dict[str, Any]:
        return {"className": self.class_name, "label": self.label, "slots": list(self.slots)}


@dataclass
class TacProgram:
    functions: list[FunctionCode] = field(default_factory=list)
    vtables: list[VTableData] = field(default_factory=list)

    def render(self) -> str:
        header = "\n".join(item.render() for item in self.vtables)
        blocks = ["\n".join(item.lines()) for item in self.functions]
        body = "\n\n".join(blocks)
        return f"{header}\n\n{body}" if header else body

    def quads(self) -> list[Quad]:
        return [quad for item in self.functions for quad in item.quads]

    def function(self, label: str) -> Optional[FunctionCode]:
        return next((item for item in self.functions if item.label == label), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "functions": [item.as_dict() for item in self.functions],
            "vtables": [item.as_dict() for item in self.vtables],
            "text": self.render(),
        }
