"""Intermediate code generation: three-address code over the validated tree."""

from __future__ import annotations

from typing import Any

from .generator import TacGenerator
from .instructions import FunctionCode, Quad, TacProgram
from .layout import ActivationRecord, assign_addresses, size_of
from .temps import TempAllocator

__all__ = [
    "ActivationRecord",
    "FunctionCode",
    "Quad",
    "TacGenerator",
    "TacProgram",
    "TempAllocator",
    "assign_addresses",
    "generate",
    "size_of",
]


def generate(program_ctx: Any, semantic: Any) -> TacProgram:
    """Translate a tree that passed the semantic phase without errors."""
    if not semantic.success:
        raise ValueError("No se genera código intermedio de un programa con errores")
    return TacGenerator(semantic).generate(program_ctx)
