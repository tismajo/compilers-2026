"""Register allocation: the classic register/address descriptors and
``get_reg()`` (Aho & Ullman's algorithm, restricted to one basic block at a
time using the next-use info ``blocks.py`` computes).

Only ``$t0``-``$t9`` (caller-saved — a call may clobber them, so nothing in
them survives one) and ``$s0``-``$s7`` (callee-saved) are handed out
dynamically. Everything else (``$ra``, ``$sp``, ``$fp``, ``$v0``, ``$v1``,
``$zero``) has a single fixed job and is never part of this pool — see
``callseq.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .blocks import UseInfo

T_REGISTERS = [f"$t{i}" for i in range(10)]
S_REGISTERS = [f"$s{i}" for i in range(8)]
ALL_REGISTERS = T_REGISTERS + S_REGISTERS


@dataclass
class AddressDescriptor:
    """Where a name's current value can be found: any number of registers
    and/or its fixed memory home. A name with no registers set and
    ``in_memory=True`` must be reloaded before it can be used again."""

    registers: set[str] = field(default_factory=set)
    in_memory: bool = True  # every name starts out only in its home address


class SpillPolicy:
    """Picks which register to evict when none is free.

    Prefers one already mirrored in memory (evicting it costs nothing, no
    store needed) over one that would need a spill store; among several
    equally cheap candidates, prefers the one whose contents are needed
    furthest away — or never again within this block.
    """

    def __init__(self, allocator: "RegisterAllocator") -> None:
        self.allocator = allocator

    def choose(self, pool: list[str], info: dict[str, UseInfo]) -> str:
        candidates = [reg for reg in pool if self.allocator.register_holds[reg]]
        if not candidates:
            raise RegisterPoolExhausted(pool)

        def cost(reg: str) -> tuple[bool, int]:
            names = self.allocator.register_holds[reg]
            # Spilling is free if every name in the register already has a
            # memory copy; otherwise at least one store is needed.
            needs_store = any(
                not self.allocator.descriptor(name).in_memory for name in names
            )
            # Farthest next use wins (None, i.e. "not needed again", wins
            # outright — treat it as "infinitely far").
            furthest = -1
            for name in names:
                use = info.get(name)
                if use is None or not use.live:
                    return (needs_store, 10**9)
                furthest = max(furthest, use.next_use if use.next_use is not None else 10**9)
            return (needs_store, furthest)

        return max(candidates, key=cost)


class RegisterPoolExhausted(Exception):
    """Raised only if a pool is asked for a register while every one of its
    registers holds a name whose value cannot be reconstructed (should not
    happen: ``SpillPolicy`` always finds a victim to spill instead)."""

    def __init__(self, pool: list[str]) -> None:
        super().__init__(f"no hay registros libres ni para derramar en {pool}")
        self.pool = pool


class RegisterAllocator:
    """One instance per function. ``homes`` maps every TAC name the function
    can reference (locals, parameters, globals, temporaries with a spill
    slot) to the MIPS operand text of its memory address — already resolved
    from ``program/tac/layout.py``'s offsets, not recomputed here."""

    def __init__(self, homes: dict[str, str]) -> None:
        self.homes = homes
        self.register_holds: dict[str, set[str]] = {reg: set() for reg in ALL_REGISTERS}
        self.address_of: dict[str, AddressDescriptor] = {}
        self._spill_policy = SpillPolicy(self)
        # Every ``spill``/``reload`` call appends the MIPS text it needed;
        # the emitter drains this after each quad.
        self.emitted: list[str] = []

    def descriptor(self, name: str) -> AddressDescriptor:
        return self.address_of.setdefault(name, AddressDescriptor())

    def home_of(self, name: str) -> str:
        try:
            return self.homes[name]
        except KeyError as exc:
            raise KeyError(f"'{name}' no tiene dirección asignada") from exc

    # -- the algorithm ----------------------------------------------------
    def get_reg(
        self,
        quad_uses: list[str],
        definition: Optional[str],
        info: dict[str, UseInfo],
        prefer_saved: bool = False,
    ) -> str:
        """Register for ``definition`` (or a scratch value when ``definition``
        is ``None``), following Aho & Ullman's three rules in order:

        1. reuse an operand's own register, when that operand dies here (its
           value is not needed again and nothing else shares the register);
        2. an empty register in the pool;
        3. spill the best candidate (:class:`SpillPolicy`) and reuse it.
        """
        pool = S_REGISTERS if prefer_saved else T_REGISTERS

        for operand in quad_uses:
            use = info.get(operand)
            if use is not None and use.live:
                continue  # still needed after this quad, cannot reuse its register
            for reg in self.descriptor(operand).registers:
                if reg in pool and self.register_holds[reg] <= {operand}:
                    self._evict(reg)
                    return reg

        for reg in pool:
            if not self.register_holds[reg]:
                return reg

        victim = self._spill_policy.choose(pool, info)
        self.spill(victim)
        return victim

    # -- bookkeeping --------------------------------------------------------
    def bind(self, name: str, reg: str) -> None:
        """Record that ``reg`` now holds ``name``'s value and nothing else
        (the caller already emitted the instruction that put it there)."""
        self._evict(reg)
        self.register_holds[reg] = {name}
        descriptor = self.descriptor(name)
        descriptor.registers = {reg}
        descriptor.in_memory = False

    def reset(self) -> None:
        """Forget every register binding, keeping the memory homes.

        Must run at the start of every basic block. A label can be reached
        from more than one predecessor (an ``if``'s two branches joining, a
        loop's back edge), so whatever the allocator believes is cached in a
        register at the *end* of one block is not a safe assumption at the
        *start* of a different one — the runtime path actually taken may not
        be the one that last updated that bookkeeping at compile time. Since
        a named variable is always written through to its memory home on
        every definition (see ``emitter.py``) and a temporary never survives
        past the end of its own block (``blocks.py``), starting each block
        with "nothing is in a register yet" is always safe: anything a block
        needs gets reloaded from a home that is guaranteed up to date.
        """
        for reg in self.register_holds:
            self.register_holds[reg] = set()
        self.address_of = {}

    def mark_stale(self, name: str) -> None:
        """A definition just overwrote ``name``'s old value everywhere: drop
        every register and the memory flag that used to hold it."""
        descriptor = self.descriptor(name)
        for reg in descriptor.registers:
            self.register_holds[reg].discard(name)
        descriptor.registers = set()
        descriptor.in_memory = False

    def spill(self, reg: str) -> None:
        """Store every name in ``reg`` that is not already safely in memory,
        then free the register."""
        for name in self.register_holds[reg]:
            descriptor = self.descriptor(name)
            if not descriptor.in_memory:
                self.emitted.append(f"    sw {reg}, {self.home_of(name)}")
                descriptor.in_memory = True
            descriptor.registers.discard(reg)
        self.register_holds[reg] = set()

    def ensure_in_register(self, name: str, prefer_saved: bool = False) -> str:
        """A value the emitter needs available in *some* register right now
        (an operand about to be read): return one of its current registers,
        or reload it from memory into a fresh one."""
        descriptor = self.descriptor(name)
        if descriptor.registers:
            return next(iter(descriptor.registers))
        reg = self.get_reg([], None, {}, prefer_saved=prefer_saved)
        self.emitted.append(f"    lw {reg}, {self.home_of(name)}")
        self.bind(name, reg)
        return reg

    def spill_all(self) -> None:
        """Flush every live register to memory — used before a call, since
        ``$t0``-``$t9`` are caller-saved and do not survive one."""
        for reg in list(self.register_holds):
            if self.register_holds[reg]:
                self.spill(reg)

    def drain(self) -> list[str]:
        """Pop the MIPS lines ``get_reg``/``spill``/``ensure_in_register``
        queued (spills and reloads), for the emitter to place before the
        instruction that triggered them."""
        lines, self.emitted = self.emitted, []
        return lines

    def _evict(self, reg: str) -> None:
        for name in self.register_holds[reg]:
            self.descriptor(name).registers.discard(reg)
        self.register_holds[reg] = set()
