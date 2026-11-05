"""``MipsGenerator``: walks already-generated TAC and emits real MIPS.

Dispatches by quad op, the same shape ``program/tac/generator.py`` already
uses by AST node type — one small method per construct instead of one large
``if``/``elif`` chain. ``load``/``store`` (array elements, object attributes,
vtable slots), ``calli`` (indirect dispatch through a vtable slot) and
``halt`` (an uncaught bounds failure) are all translated — see ``_load``,
``_store``, ``_calli`` and ``_halt`` below. ``foreach``, ``switch`` and
``try``/``catch`` need no handler of their own: the TAC phase already lowers
all three to comparisons, branches and (for ``foreach``/``try``) ``load``, so
once those exist there is nothing construct-specific left to translate. A
quad whose op is still genuinely unhandled (none, for any construct this
stage's test programs exercise) falls back to a ``# TODO MIPS <op>`` comment
instead of failing, the same mechanism ``generator.py`` itself used in the
TAC phase while constructs were still pending. Closures that capture a
variable from an *enclosing* function (as opposed to one in the same frame)
remain out of scope — see ``docs/generacion-mips.md``.

Two register disciplines, by design (see ``callseq.py`` and ``runtime.py``
for why):

* **Integer / boolean / reference values** go through ``RegisterAllocator``
  (``$t0``-``$t9``), with real liveness-driven reuse and spilling.
* **Named variables (locals, parameters, globals) write through to memory
  immediately** after every definition — they are never left dirty only in a
  register. Only temporaries benefit from the full lazy-spill discipline.
  This trades a (deliberately out of scope) ``$s``-register optimization for
  a much smaller surface of "is this copy still valid" bugs.
* **``float`` values are never register-allocated at all** — every float
  operation loads straight from memory into a couple of fixed scratch ``$f``
  registers, computes, and stores straight back. Simple, correct, not
  optimized; the explicit trade-off from ``docs/generacion-mips.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from semantic.symbol_table import SymbolTable
from tac.instructions import FunctionCode, Quad, TacProgram
from tac.temps import TempAllocator

from .blocks import UseInfo, operand_names, split_blocks
from .callseq import FrameLayout, call_site, epilogue, prologue, reserve_args
from .registers import RegisterAllocator
from .runtime import (
    ALLOC_LABEL,
    CONCAT_LABEL,
    PRINT_BOOL_LABEL,
    RUNTIME_DATA,
    RUNTIME_TEXT,
    TOSTR_INT_LABEL,
)

ARITH_INT = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem"}
ARITH_FLOAT = {"+": "add.s", "-": "sub.s", "*": "mul.s", "/": "div.s"}
COMPARISON = {"==": "seq", "!=": "sne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}


def _is_literal_int(token: str) -> bool:
    try:
        int(token)
        return True
    except ValueError:
        return False


@dataclass
class DataItem:
    label: str
    directive: str  # ``.asciiz "..."`` or ``.word 0`` etc.

    def as_dict(self) -> dict[str, str]:
        return {"label": self.label, "directive": self.directive}


@dataclass
class MipsProgram:
    data: list[DataItem] = field(default_factory=list)
    text: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [".data"]
        lines += [f"{item.label}: {item.directive}" for item in self.data]
        lines.append(RUNTIME_DATA)
        lines.append("")
        lines.append(".text")
        lines.append(".globl main")
        lines += self.text
        lines.append(RUNTIME_TEXT)
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "data": [item.as_dict() for item in self.data],
            "instructions": list(self.text),
            "text": self.render(),
        }


class MipsGenerator:
    def __init__(self, tac: TacProgram, table: SymbolTable) -> None:
        self.tac = tac
        self.table = table
        self.program = MipsProgram()
        self._string_labels: dict[str, str] = {}
        self._string_counter = 0
        self._global_homes: dict[str, str] = {}
        # Every class's dispatch-table label, e.g. "Dog_vtable" — the one
        # place a ``store``'s value operand is a bare code/data label rather
        # than a name or literal (see ``tac/generator.py``'s ``_new_object``
        # and ``_store``/``_load_operand`` below).
        self._vtable_labels = {item.label for item in tac.vtables}
        self.allocator: RegisterAllocator  # set per function, in ``_function``
        self.frame: FrameLayout
        self.return_label: str
        self._param_queue: list[tuple[str, int, str]] = []  # (place, size, type)
        self._cross_block_temps: set = set()  # recomputed per function, in ``_function``

    # -- entry point ------------------------------------------------------
    def generate(self) -> MipsProgram:
        self._declare_globals()
        self._declare_vtables()
        for code in self.tac.functions:
            self._function(code)
        return self.program

    def _declare_vtables(self) -> None:
        # ``.word`` with label operands: MARS resolves each to that label's
        # own address, the same way a C compiler's literal pool would — so
        # ``load vtable_ptr+slot*4`` at runtime reads a real code address.
        # A class with no methods still needs a one-word placeholder (``.word
        # 0``, never dereferenced — nothing dispatches through an empty
        # table) because ``.word`` needs at least one operand.
        for item in self.tac.vtables:
            directive = ".word " + ", ".join(item.slots) if item.slots else ".word 0"
            self.program.data.append(DataItem(item.label, directive))

    def _declare_globals(self) -> None:
        # Walks every scope reachable from the global one, not just its own
        # direct symbols: a variable declared inside a top-level block (a
        # ``for``'s own index, say) is still ``storage == "global"`` — main
        # has no real stack frame — but lives in a *nested* scope. Two
        # sibling blocks may legitimately shadow the same source name (a
        # second, unrelated ``for (let i ...)`` elsewhere in main), so the
        # ``.data`` label has to be each symbol's own resolved TAC name
        # (``symbol.label``, set by ``TacGenerator.name_of``), never its
        # plain ``.name`` — those can collide where the labels cannot.
        for scope in self.table.global_scope.walk():
            for symbol in scope.symbols.values():
                if symbol.storage != "global" or symbol.label is None:
                    continue
                if symbol.label in self._global_homes:
                    continue  # already declared (name_of is memoized per symbol)
                is_float = symbol.type is not None and str(symbol.type) == "float"
                directive = ".float 0.0" if is_float else ".word 0"
                self.program.data.append(DataItem(symbol.label, directive))
                # Same address-string shape as an fp-relative home
                # ("-4($fp)"): a bare label is just as valid as the second
                # operand of lw/sw, so the register allocator never needs to
                # know the difference between a global and a stack slot.
                self._global_homes[symbol.label] = symbol.label

    # -- per function -------------------------------------------------------
    def _function(self, code: FunctionCode) -> None:
        record = code.record
        float_temps = {
            quad.result
            for quad in code.quads
            if quad.type == "float" and quad.result and TempAllocator.is_temp(quad.result)
        }
        self.frame = FrameLayout.build(record, float_temps)
        self.allocator = RegisterAllocator(homes={**self._global_homes, **self.frame.homes()})
        self.return_label = f"{code.label}__ret"
        self._param_queue = []

        blocks = split_blocks(code.quads)
        self._cross_block_temps = self._find_cross_block_temps(blocks)
        self.program.text += prologue(code, self.frame)
        for block in blocks:
            # A label can be reached from more than one predecessor; nothing
            # a previous block left in a register can be trusted here. See
            # ``RegisterAllocator.reset``.
            self.allocator.reset()
            for index, quad in enumerate(block.quads):
                self._quad(quad, block.info[index])
        self.program.text += epilogue(self.return_label, is_main=record.kind == "main")

    @staticmethod
    def _find_cross_block_temps(blocks: list) -> set:
        """Temps that ``blocks.py``'s own guarantee does not cover: most TAC
        temps die inside the block that creates them, but a few — a
        ``foreach``'s index and cached array length (``tac/generator.py``'s
        ``visitForeachStatement``), or a ``switch``'s subject when it is an
        expression rather than a bare variable — are deliberately reused
        across the whole construct because ``Layout`` had already run and
        left them nowhere else to live. Such a temp is bound to a register
        in one block and read again in a later one, where ``reset()`` has
        already forgotten that binding — so it must be written through to
        memory on every definition, exactly like a named variable, instead
        of taking ``_finish_definition``'s register-only fast path."""
        owner: dict[str, int] = {}
        cross: set = set()
        for block_index, block in enumerate(blocks):
            for quad in block.quads:
                uses, definition = operand_names(quad)
                names = list(uses) + ([definition] if definition else [])
                for name in names:
                    if not TempAllocator.is_temp(name):
                        continue
                    seen_in = owner.setdefault(name, block_index)
                    if seen_in != block_index:
                        cross.add(name)
        return cross

    # -- dispatch -----------------------------------------------------------
    def _quad(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        if quad.op == "label":
            self.program.text.append(f"{quad.arg1}:")
            return
        if quad.op == "goto":
            self.program.text.append(f"    j {quad.arg1}")
            return
        if quad.op in ("if_true", "if_false"):
            self._branch(quad, info)
            return
        if quad.op == "param":
            self._param(quad, info)
            return
        if quad.op == "call":
            self._call(quad, info)
            return
        if quad.op == "calli":
            self._calli(quad, info)
            return
        if quad.op == "load":
            self._load(quad, info)
            return
        if quad.op == "store":
            self._store(quad, info)
            return
        if quad.op == "halt":
            self._halt(quad, info)
            return
        if quad.op == "return":
            self._return(quad, info)
            return
        if quad.op == "print":
            self._print(quad, info)
            return
        if quad.op == "alloc":
            self._alloc(quad, info)
            return
        if quad.op == "assign":
            self._assign(quad, info)
            return
        if quad.op in ("minus", "not"):
            self._unary(quad, info)
            return
        if quad.op == "itof":
            self._itof(quad, info)
            return
        if quad.op == "tostr":
            self._tostr(quad, info)
            return
        if quad.op == "concat":
            self._concat(quad, info)
            return
        if quad.op in ARITH_INT or quad.op in COMPARISON:
            self._binary(quad, info)
            return
        self.program.text.append(f"    # TODO MIPS {quad.op}: {quad.render()}")

    # -- operands -------------------------------------------------------
    def _load_operand(
        self,
        token: str,
        float_value: bool,
        scratch: str = "$f0",
        info: Optional[dict[str, UseInfo]] = None,
    ) -> str:
        """Get ``token`` (a name or a literal) into a register and return its
        name — ``$t``-pool for int/bool/reference, the given ``$f`` scratch
        for float (never cached, per the module docstring).

        ``info`` should be the current quad's own next-use info whenever the
        caller has it. ``token`` itself is never a key in it (a literal is
        filtered out by ``operand_names``, and a name being *loaded* here is
        not this quad's own ``result``) — it is there purely so that, if
        loading ``token`` forces a spill, the victim is judged against
        what this quad's *other* operands still need, not against an empty
        map that would make a register holding one of them look dead."""
        if float_value:
            if _looks_like_float_literal(token):
                self._emit_float_literal_load(token, scratch)
            else:
                self.program.text.append(f"    l.s {scratch}, {self._address_of(token)}")
            return scratch
        if token in ("true", "false", "null"):
            value = "1" if token == "true" else "0"
            return self._load_literal(token, f"    li {{reg}}, {value}", info)
        if _is_literal_int(token):
            return self._load_literal(token, f"    li {{reg}}, {token}", info)
        if token.startswith('"'):
            return self._string_pointer(token, info)
        reg = self.allocator.ensure_in_register(token, info)
        self._flush(self.allocator.drain())
        return reg

    def _load_literal(
        self, token: str, instruction: str, info: Optional[dict[str, UseInfo]] = None
    ) -> str:
        """Load a literal and ``bind`` the register to the literal's own
        text. Without this, two literals loaded back to back (``3 - 10``,
        say) could both land in whatever register ``get_reg`` considers
        "free" — nothing marks a literal's register as occupied otherwise,
        so the second load can silently clobber the first before either is
        used. Binding to the literal text itself is enough: nothing in
        ``info`` ever names a literal, so this can never cause an incorrect
        reuse, only prevent one register from serving two live literals."""
        reg = self.allocator.get_reg([], None, info or {})
        self._flush(self.allocator.drain())
        self.program.text.append(instruction.format(reg=reg))
        self.allocator.bind(token, reg)
        # A literal has no memory home to spill to (``home_of`` would raise)
        # and never needs one: nothing ever calls ``ensure_in_register`` on a
        # literal's own text, so marking it "already in memory" just tells
        # ``spill`` there is nothing to write back if this register is
        # evicted later — true in effect, since a literal is only ever read
        # once, right after this call.
        self.allocator.descriptor(token).in_memory = True
        return reg

    def _address_of(self, name: str) -> str:
        homes = self.frame.homes()
        if name in homes:
            return homes[name]
        return f"{name}"  # a global's own label

    def _flush(self, lines: list[str]) -> None:
        self.program.text += lines

    def _store_through(self, name: str, reg: str, float_value: bool = False) -> None:
        """Write ``reg`` to ``name``'s memory home and, for the non-float
        register-allocated path, keep it bound (write-through, not
        write-back — see the module docstring)."""
        address = self._address_of(name)
        if float_value:
            self.program.text.append(f"    s.s {reg}, {address}")
            return
        self.program.text.append(f"    sw {reg}, {address}")
        self.allocator.bind(name, reg)
        self.allocator.descriptor(name).in_memory = True

    def _definition_register(
        self, quad: Quad, info: dict[str, UseInfo], uses: list[str]
    ) -> str:
        reg = self.allocator.get_reg(uses, quad.result, info)
        self._flush(self.allocator.drain())
        return reg

    # -- literals and strings ---------------------------------------------
    def _string_pointer(self, literal: str, info: Optional[dict[str, UseInfo]] = None) -> str:
        label = self._string_labels.get(literal)
        if label is None:
            label = f"__str{self._string_counter}"
            self._string_counter += 1
            self._string_labels[literal] = label
            self.program.data.append(DataItem(label, f'.asciiz {literal}'))
        return self._load_literal(literal, f"    la {{reg}}, {label}", info)

    def _emit_float_literal_load(self, token: str, scratch: str) -> None:
        label = self._string_labels.get(token)
        if label is None:
            label = f"__flt{self._string_counter}"
            self._string_counter += 1
            self._string_labels[token] = label
            self.program.data.append(DataItem(label, f".float {token}"))
        self.program.text.append(f"    l.s {scratch}, {label}")

    # -- control flow -------------------------------------------------------
    def _branch(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        reg = self._load_operand(quad.arg1, False, info=info)
        op = "beqz" if quad.op == "if_false" else "bnez"
        self.program.text.append(f"    {op} {reg}, {quad.arg2}")

    # -- assignment and conversions -----------------------------------------
    def _assign(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        is_float = quad.type == "float"
        if is_float:
            self._load_operand(quad.arg1, True, info=info)
            self._store_through(quad.result, "$f0", float_value=True)
            return
        src = self._load_operand(quad.arg1, False, info=info)
        self._store_through(quad.result, src)

    def _unary(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        operand = self._load_operand(quad.arg1, quad.type == "float", info=info)
        if quad.type == "float":
            self.program.text.append(f"    neg.s $f0, {operand}")
            self._store_through(quad.result, "$f0", float_value=True)
            return
        uses, _ = operand_names(quad)
        result = self._definition_register(quad, info, uses)
        if quad.op == "not":
            self.program.text.append(f"    xori {result}, {operand}, 1")
        else:
            self.program.text.append(f"    sub {result}, $zero, {operand}")
        self._finish_definition(quad.result, result)

    def _itof(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        src = self._load_operand(quad.arg1, False, info=info)
        self.program.text += [
            f"    mtc1 {src}, $f0",
            "    cvt.s.w $f0, $f0",
        ]
        self._store_through(quad.result, "$f0", float_value=True)

    def _tostr(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        # Only integer -> string is needed by this stage (strings are
        # already strings; booleans print without going through ``tostr``,
        # see ``_print``; floats are out of scope for text conversion here).
        src = self._load_operand(quad.arg1, False, info=info)
        self.program.text.append(f"    move $a0, {src}")
        # The runtime routine freely uses $t0-$t9 internally; nothing this
        # emitter currently has cached in one would survive the jal, so it
        # must be protected exactly like a user-level call.
        self.allocator.spill_all()
        self._flush(self.allocator.drain())
        self.program.text.append(f"    jal {TOSTR_INT_LABEL}")
        result = self.allocator.get_reg([], quad.result, info)
        self._flush(self.allocator.drain())
        self.program.text.append(f"    move {result}, $v0")
        self._finish_definition(quad.result, result)

    def _concat(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        left = self._load_operand(quad.arg1, False, info=info)
        self.program.text.append(f"    move $a0, {left}")
        right = self._load_operand(quad.arg2, False, info=info)
        self.program.text.append(f"    move $a1, {right}")
        self.allocator.spill_all()  # see the note in ``_tostr``
        self._flush(self.allocator.drain())
        self.program.text.append(f"    jal {CONCAT_LABEL}")
        result = self.allocator.get_reg([], quad.result, info)
        self._flush(self.allocator.drain())
        self.program.text.append(f"    move {result}, $v0")
        self._finish_definition(quad.result, result)

    def _binary(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        # NOTE: a comparison's own ``quad.type`` is always "boolean" (it is
        # the *result*'s type), so this only ever takes the float path for
        # arithmetic. Comparing two floats (``1.5 < 2.0``) is not detected
        # here yet and falls through to the integer path, which is wrong for
        # that one case — a known gap, not exercised by this stage's target
        # programs (arithmetic/control-flow/functions), called out in
        # ``docs/generacion-mips.md`` rather than silently mishandled.
        if quad.type == "float":
            self._binary_float(quad, info)
            return
        uses, _ = operand_names(quad)
        left = self._load_operand(quad.arg1, False, info=info)
        right = self._load_operand(quad.arg2, False, info=info)
        result = self._definition_register(quad, info, uses)
        mnemonic = ARITH_INT.get(quad.op) or COMPARISON[quad.op]
        self.program.text.append(f"    {mnemonic} {result}, {left}, {right}")
        self._finish_definition(quad.result, result)

    def _binary_float(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        # Only reached for arithmetic: ``_binary`` gates on ``quad.type``,
        # which is "boolean" for every comparison regardless of its
        # operands' types (see the note in ``_binary``).
        self._load_operand(quad.arg1, True, scratch="$f0", info=info)
        self._load_operand(quad.arg2, True, scratch="$f2", info=info)
        mnemonic = ARITH_FLOAT[quad.op]
        self.program.text.append(f"    {mnemonic} $f4, $f0, $f2")
        self._store_through(quad.result, "$f4", float_value=True)

    def _finish_definition(self, name: str, reg: str) -> None:
        if TempAllocator.is_temp(name) and name not in self._cross_block_temps:
            self.allocator.bind(name, reg)
            return
        self._store_through(name, reg)

    # -- calls ----------------------------------------------------------
    def _param(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        is_float = quad.type == "float"
        size = 8 if is_float else 4
        self._param_queue.append((quad.arg1, size, quad.type or "integer"))

    def _emit_arguments(self, info: dict[str, UseInfo]) -> int:
        """Store every queued ``param`` onto the stack (reserving the space
        first) and protect whatever is still live across the ``jal``/``jalr``
        that follows — the part identical between a direct and an indirect
        call. Returns the total bytes reserved, for ``call_site``."""
        total = sum(size for _, size, _ in self._param_queue)
        self._flush(reserve_args(total))
        offset = 0
        for place, size, kind in self._param_queue:
            if kind == "float":
                self._load_operand(place, True, scratch="$f0", info=info)
                self.program.text.append(f"    s.s $f0, {offset}($sp)")
            else:
                reg = self._load_operand(place, False, info=info)
                self.program.text.append(f"    sw {reg}, {offset}($sp)")
            offset += size
        self._param_queue = []
        self.allocator.spill_all()
        self._flush(self.allocator.drain())
        return total

    def _finish_call_result(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        if not quad.result:
            return
        if quad.type == "float":
            # ``_return`` moved the raw bits out of $f0 into $v0 with
            # ``mfc1``; storing those same bits straight from $v0 with a
            # plain ``sw`` lands the identical IEEE-754 pattern that ``s.s``
            # would have, no ``$f`` register needed on this side. Not routed
            # through ``_store_through``/``bind``: $v0 is not part of the
            # $t/$s pool those track, and a float is never kept in a
            # register across instructions anyway.
            self.program.text.append(f"    sw $v0, {self._address_of(quad.result)}")
            return
        result = self.allocator.get_reg([], quad.result, info)
        self._flush(self.allocator.drain())
        self.program.text.append(f"    move {result}, $v0")
        self._finish_definition(quad.result, result)

    def _call(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        total = self._emit_arguments(info)
        self._flush(call_site(quad.arg1, total))
        self._finish_call_result(quad, info)

    def _calli(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        """Indirect dispatch through a vtable slot: identical call sequence
        to ``_call``, except the target is whatever address ``quad.arg1``
        (a temp, holding the slot's method pointer) currently holds, not a
        fixed label. Reloaded *after* ``_emit_arguments``'s ``spill_all`` —
        never kept in a register across the argument-store loop — because
        storing earlier arguments could otherwise reuse (and overwrite) the
        exact register this one is still sitting in; reloading fresh from
        its home, which ``spill_all`` just guaranteed is up to date, sidesteps
        that regardless of which register either ends up in."""
        total = self._emit_arguments(info)
        fn_reg = self._load_operand(quad.arg1, False, info=info)
        self._flush(call_site(None, total, indirect_register=fn_reg))
        self._finish_call_result(quad, info)

    def _return(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        if quad.arg1 is not None:
            if quad.type == "float":
                self._load_operand(quad.arg1, True, scratch="$f0", info=info)
                self.program.text.append("    mfc1 $v0, $f0")
            else:
                reg = self._load_operand(quad.arg1, False, info=info)
                self.program.text.append(f"    move $v0, {reg}")
        self.program.text.append(f"    j {self.return_label}")

    def _print(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        kind = quad.type or "integer"
        if kind == "boolean":
            reg = self._load_operand(quad.arg1, False, info=info)
            self.program.text += [f"    move $a0, {reg}", f"    jal {PRINT_BOOL_LABEL}"]
            return
        if kind == "float":
            self._load_operand(quad.arg1, True, scratch="$f12", info=info)
            self.program.text += ["    li $v0, 2", "    syscall"]
            return
        reg = self._load_operand(quad.arg1, False, info=info)
        syscall = 4 if kind == "string" else 1
        self.program.text += [f"    move $a0, {reg}", f"    li $v0, {syscall}", "    syscall"]

    def _alloc(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        size = self._load_operand(quad.arg1, False, info=info)
        self.program.text.append(f"    move $a0, {size}")
        self.allocator.spill_all()  # see the note in ``_tostr``
        self._flush(self.allocator.drain())
        self.program.text.append(f"    jal {ALLOC_LABEL}")
        result = self.allocator.get_reg([], quad.result, info)
        self._flush(self.allocator.drain())
        self.program.text.append(f"    move {result}, $v0")
        self._finish_definition(quad.result, result)

    # -- arrays, attributes and vtable slots --------------------------------
    def _effective_address(
        self, base_reg: str, offset_token: str, uses: list[str], info: dict[str, UseInfo]
    ) -> str:
        """``offset_token`` is always a byte count: a literal folds straight
        into the instruction's own offset field; a name (a temp holding a
        computed index*stride) needs one ``add`` into a scratch register
        first, since MIPS addressing has no register+register form."""
        if _is_literal_int(offset_token):
            return f"{offset_token}({base_reg})"
        offset_reg = self._load_operand(offset_token, False, info=info)
        addr_reg = self.allocator.get_reg(uses, None, info)
        self._flush(self.allocator.drain())
        self.program.text.append(f"    add {addr_reg}, {base_reg}, {offset_reg}")
        return f"0({addr_reg})"

    def _load(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        uses, _ = operand_names(quad)
        base_reg = self._load_operand(quad.arg1, False, info=info)
        address = self._effective_address(base_reg, quad.arg2, uses, info)
        if quad.type == "float":
            self.program.text.append(f"    l.s $f0, {address}")
            self._store_through(quad.result, "$f0", float_value=True)
            return
        result = self._definition_register(quad, info, uses)
        self.program.text.append(f"    lw {result}, {address}")
        self._finish_definition(quad.result, result)

    def _store(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        uses, _ = operand_names(quad)
        base_reg = self._load_operand(quad.arg1, False, info=info)
        is_float = quad.type == "float"
        value_reg: Optional[str] = None
        if is_float:
            self._load_operand(quad.result, True, scratch="$f0", info=info)
        elif quad.result in self._vtable_labels:
            # The one case a ``store``'s value is a bare code/data label
            # (an object's vtable pointer, set by ``new``) rather than a
            # name or an ordinary literal — needs its *address* (``la``),
            # not a value load.
            value_reg = self._load_literal(quad.result, f"    la {{reg}}, {quad.result}", info)
        else:
            value_reg = self._load_operand(quad.result, False, info=info)
        address = self._effective_address(base_reg, quad.arg2, uses, info)
        if is_float:
            self.program.text.append(f"    s.s $f0, {address}")
        else:
            self.program.text.append(f"    sw {value_reg}, {address}")

    def _halt(self, quad: Quad, info: dict[str, UseInfo]) -> None:
        # An uncaught runtime fault (today, only an array bounds check with
        # no active ``try``) — terminate unconditionally, the same exit
        # ``epilogue`` uses for ``main``. Nothing is worth preserving: the
        # program never resumes after this.
        self.program.text += ["    li $v0, 10", "    syscall"]


def _looks_like_float_literal(token: str) -> bool:
    if "." not in token:
        return False
    try:
        float(token)
        return True
    except ValueError:
        return False


def generate_mips(tac: TacProgram, table: SymbolTable) -> MipsProgram:
    return MipsGenerator(tac, table).generate()
