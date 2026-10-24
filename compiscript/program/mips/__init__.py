"""MIPS back end: translates already-generated TAC to real MIPS assembly.

Layered the same way ``program/tac`` is:

* ``blocks.py`` — basic blocks and next-use/liveness info within a function;
* ``registers.py`` — ``get_reg()`` and the register/address descriptors;
* ``callseq.py`` — the call and return sequence (prologue, epilogue, call
  site);
* ``runtime.py`` — the handful of support routines MIPS has no instruction
  for (``tostr``, ``concat``, ``print`` dispatch by type);
* ``emitter.py`` — ``MipsGenerator``, which walks the TAC and ties the above
  together into a ``.data``/``.text`` program.
"""

from __future__ import annotations

from semantic.symbol_table import SymbolTable
from tac.instructions import TacProgram

from .emitter import MipsProgram, generate_mips

__all__ = ["MipsProgram", "generate", "generate_mips"]


def generate(tac_program: TacProgram, table: SymbolTable) -> MipsProgram:
    """Translate already-generated TAC to MIPS. ``table`` is the same
    ``SymbolTable`` ``tac.generate`` already mutated in place (every
    offset, frame and label this phase needs is already on it); this phase
    never recomputes any of that."""
    return generate_mips(tac_program, table)
