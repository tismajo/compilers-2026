"""Basic blocks and next-use/liveness info within one function's quads.

A basic block is a maximal run of quads with a single entry (its first
instruction) and a single exit (its last): control only enters at the top and
only leaves at the bottom. Splitting a function into blocks is what lets
``get_reg`` (``program/mips/registers.py``) make a *local* decision — which
register to reuse, and when a value already in one is safe to evict — using
only what happens inside that one block, the classic algorithm from the
Dragon Book instead of a global, whole-function analysis.

Liveness at a block's exit would normally need a fixed-point pass over the
whole control-flow graph. This TAC does not: ``program/tac/temps.py``
guarantees a temporary (``t0``, ``t1``...) is always released right after its
last use, in the same block that created it, so a temporary is *never* live
past the block it is born in. Every other name (a declared variable or
parameter) is treated conservatively as live at every block's exit, since it
may be read in a block reached later. Both are the standard textbook
assumption for a per-block allocator; here the temporary half is not even an
assumption, it is a guarantee the generator already upholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from tac.instructions import Quad
from tac.temps import TempAllocator

BINARY_OPS = {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="}

# Which operand fields a quad *reads*, by op. Anything not listed here (a
# label, ``goto``'s target, a call's own label/argument-count) touches no
# variable and is left out on purpose.
_USE_FIELDS: dict[str, tuple[str, ...]] = {
    "assign": ("arg1",),
    "minus": ("arg1",),
    "not": ("arg1",),
    "itof": ("arg1",),
    "tostr": ("arg1",),
    "concat": ("arg1", "arg2"),
    "if_false": ("arg1",),
    "if_true": ("arg1",),
    "param": ("arg1",),
    "return": ("arg1",),
    "print": ("arg1",),
    "calli": ("arg1",),
    "load": ("arg1", "arg2"),
    # ``store``'s own ``result`` field carries the value being written, not a
    # destination — see ``Quad.render``'s ``*(a + b) = r``.
    "store": ("arg1", "arg2", "result"),
}
for _op in BINARY_OPS:
    _USE_FIELDS[_op] = ("arg1", "arg2")

# Which field a quad *writes*. ``store`` is deliberately absent: it has no
# field that is a definition.
_DEF_FIELD: dict[str, str] = {
    "assign": "result",
    "minus": "result",
    "not": "result",
    "itof": "result",
    "tostr": "result",
    "concat": "result",
    "call": "result",
    "calli": "result",
    "alloc": "result",
    "load": "result",
    "todo": "result",
}
for _op in BINARY_OPS:
    _DEF_FIELD[_op] = "result"

# A quad whose op is here always starts a new block right after it: the
# control flow it carries never falls through to the next quad unconditionally.
_UNCONDITIONAL_ENDERS = {"goto", "return", "halt"}
_JUMP_OPS = {"goto", "if_true", "if_false"}


def _is_literal(token: str) -> bool:
    if token in ("true", "false", "null"):
        return True
    if token.startswith('"'):
        return True
    try:
        float(token)
        return True
    except ValueError:
        return False


def operand_names(quad: Quad) -> tuple[list[str], Optional[str]]:
    """``(uses, definition)`` — the variable/temp names a quad reads and the
    one it writes, filtering out labels and literals."""
    uses = []
    for field_name in _USE_FIELDS.get(quad.op, ()):
        value = getattr(quad, field_name)
        if value is not None and not _is_literal(value):
            uses.append(value)
    def_field = _DEF_FIELD.get(quad.op)
    definition = getattr(quad, def_field) if def_field else None
    if definition is not None and _is_literal(definition):
        definition = None
    return uses, definition


@dataclass
class UseInfo:
    """Where a name stands *just before* a quad runs: still needed later in
    this block (``live``) and, if so, the index of the next quad that reads
    it (``next_use``; ``None`` when the only reason it is live is that it
    survives past the end of the block)."""

    live: bool
    next_use: Optional[int] = None


def _live_on_exit(name: str) -> UseInfo:
    # A temporary never survives its block (guaranteed, see module docstring);
    # a declared variable or parameter conservatively might.
    return UseInfo(live=not TempAllocator.is_temp(name))


@dataclass
class Block:
    """One basic block: a slice of a function's body quads, plus per-quad
    liveness filled in by :meth:`annotate`."""

    start: int
    quads: list[Quad]
    info: list[dict[str, UseInfo]] = field(default_factory=list)

    def annotate(self) -> None:
        """Backward scan: for each quad, record the live/next-use state of
        every name it touches, as of just before that quad executes."""
        state: dict[str, UseInfo] = {}
        self.info = [dict() for _ in self.quads]
        for index in range(len(self.quads) - 1, -1, -1):
            quad = self.quads[index]
            uses, definition = operand_names(quad)
            names = list(uses)
            if definition is not None and definition not in names:
                names.append(definition)
            self.info[index] = {
                name: state.get(name) or _live_on_exit(name) for name in names
            }
            if definition is not None:
                state[definition] = UseInfo(live=False, next_use=None)
            for name in uses:
                state[name] = UseInfo(live=True, next_use=index)


def split_blocks(quads: list[Quad]) -> list[Block]:
    """Partition a function's body (``begin_func``/``end_func`` excluded,
    they are not real instructions) into basic blocks, each already
    annotated with next-use info."""
    body = [quad for quad in quads if quad.op not in ("begin_func", "end_func")]
    if not body:
        return []
    label_index = {quad.arg1: i for i, quad in enumerate(body) if quad.op == "label"}
    leaders = {0}
    for index, quad in enumerate(body):
        if quad.op in _JUMP_OPS:
            target = quad.arg2 if quad.op in ("if_true", "if_false") else quad.arg1
            if target in label_index:
                leaders.add(label_index[target])
        if quad.op in _UNCONDITIONAL_ENDERS or quad.op in _JUMP_OPS:
            if index + 1 < len(body):
                leaders.add(index + 1)
    ordered = sorted(leaders)
    blocks: list[Block] = []
    for position, start in enumerate(ordered):
        end = ordered[position + 1] if position + 1 < len(ordered) else len(body)
        block = Block(start=start, quads=body[start:end])
        block.annotate()
        blocks.append(block)
    return blocks
