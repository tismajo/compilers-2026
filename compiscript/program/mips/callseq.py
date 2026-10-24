"""Call and return sequence: prologue, epilogue, and the call site.

Follows the team's own diagrams exactly. Two simplifications on top of them,
both explicit, both consistent with the formulas the diagrams already give
(they just take the simplest value of a term the diagrams leave open):

* No value is ever promoted into a ``$s`` register by this stage — every
  live ``$t`` is spilled to memory before a ``call``/``calli``
  (``RegisterAllocator.spill_all``) instead of being kept across it in a
  callee-saved register. The diagram's own frame formula already has a
  ``+ 4 × (#$s used)`` term for this; it is simply 0 here. Promoting hot
  values into ``$s`` registers is a real optimization, left for later.
* The access link (closures) is not wired yet — closures are out of scope
  for this stage (see ``docs/generacion-mips.md``). The formula's
  ``+ 4 if access link`` term is likewise 0 for every function this stage
  emits.

Frame addresses below the locals extend the exact same fp-relative scheme
``program/tac/layout.py`` already uses, downward, for the two things MIPS
needs that TAC never had to: a fixed memory home per temporary (TAC only
tracked their *count*, enough to size a generic spill area; MIPS needs an
address) and the extra 4 bytes a temporary needs on the occasions it holds a
``float`` instead of an ``integer``/reference, since this stage never
register-allocates floats at all — see ``runtime.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from tac.instructions import FunctionCode, Quad
from tac.layout import WORD, ActivationRecord, Slot

FLOAT_WORD = 8


@dataclass
class FrameLayout:
    """Every MIPS-only address a function's body needs, plus the real frame
    size this stage ends up reserving (the TAC-computed one, stretched for
    whichever temporaries turned out to hold a ``float``)."""

    record: ActivationRecord
    temp_home: dict[str, str] = field(default_factory=dict)
    size: int = 0

    @classmethod
    def build(cls, record: ActivationRecord, float_temps: set[str]) -> "FrameLayout":
        offset = -record.locals_size
        temp_home: dict[str, str] = {}
        for index in range(record.temps):
            name = f"t{index}"
            width = FLOAT_WORD if name in float_temps else WORD
            offset -= width
            temp_home[name] = f"{offset}($fp)"
        extra = WORD * len(float_temps)  # each promoted from 4 to 8 bytes
        return cls(record=record, temp_home=temp_home, size=record.frame_size + extra)

    def homes(self) -> dict[str, str]:
        """Every name with a *fixed* MIPS address: parameters, locals and
        temporaries. Globals are addressed by label, not by this map — the
        emitter resolves those separately (``la``/data-segment symbol)."""
        addresses = dict(self.temp_home)
        for slot in self.record.parameters:
            addresses[_slot_name(slot)] = f"{slot.offset}($fp)"
        for slot in self.record.locals:
            addresses[_slot_name(slot)] = f"{slot.offset}($fp)"
        return addresses


def _slot_name(slot: Slot) -> str:
    """The exact TAC-level name this slot's quads use, not its source name:
    two sibling blocks may legitimately shadow the same source name
    (``for (let i ...)`` twice in the same function), in which case
    ``TacGenerator.name_of`` already told them apart with a ``#2`` suffix —
    recorded on the symbol's own ``label``, the only thing this can key on
    without colliding. Falls back to the slot's own name for ``this`` (no
    backing symbol) and for a parameter the body never reads (no ``label``
    yet, because ``name_of`` is never called for it) — safe in both cases,
    since nothing that was never named through ``name_of`` can appear in a
    quad under any other name either.
    """
    if slot.symbol is not None and slot.symbol.label is not None:
        return slot.symbol.label
    return slot.name


def prologue(code: FunctionCode, frame: FrameLayout) -> list[str]:
    lines = [
        f"{code.label}:",
        "    addiu $sp, $sp, -8",
        "    sw $ra, 4($sp)",
        "    sw $fp, 0($sp)",
        "    move $fp, $sp",
    ]
    reserved = frame.size - 8  # the 8 bytes above are already accounted for
    if reserved > 0:
        lines.append(f"    addiu $sp, $sp, -{reserved}")
    return lines


def epilogue(return_label: str, is_main: bool = False) -> list[str]:
    if is_main:
        # ``main`` is the program's entry point, never reached through a
        # ``jal`` — there is no caller for ``jr $ra`` to return to ($ra is
        # whatever garbage the simulator starts with), so it must terminate
        # the program instead of trying to return from it.
        return [f"{return_label}:", "    li $v0, 10", "    syscall"]
    return [
        f"{return_label}:",
        "    move $sp, $fp",
        "    lw $ra, 4($sp)",
        "    lw $fp, 0($sp)",
        "    addiu $sp, $sp, 8",
        "    jr $ra",
    ]


@dataclass
class PendingCall:
    """Accumulates the ``param`` quads between two calls, so the whole
    group can be emitted as one reserve/store/jump/release unit — the
    caller side of the sequence."""

    sizes: list[int] = field(default_factory=list)

    def add(self, size: int) -> int:
        """Record one more argument; return the ``$sp``-relative byte offset
        (from the *start* of the reserved area) it will be stored at."""
        offset = sum(self.sizes)
        self.sizes.append(size)
        return offset

    @property
    def total(self) -> int:
        return sum(self.sizes)


def call_site(label: str, total_args_bytes: int, indirect_register: Optional[str] = None) -> list[str]:
    """``jal``/``jalr`` plus releasing the argument area — the part of the
    call sequence that runs after every argument is already stored."""
    jump = f"    jalr {indirect_register}" if indirect_register else f"    jal {label}"
    lines = [jump]
    if total_args_bytes > 0:
        lines.append(f"    addiu $sp, $sp, {total_args_bytes}")
    return lines


def reserve_args(total_args_bytes: int) -> list[str]:
    if total_args_bytes <= 0:
        return []
    return [f"    addiu $sp, $sp, -{total_args_bytes}"]
