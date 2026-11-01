"""``get_reg()`` in isolation: the register/address descriptors, picking an
empty register before spilling, and spilling the right victim when none is
free — the "successful and failing cases" the assignment asks for on the
register-allocation algorithm specifically."""

from __future__ import annotations

import unittest

import support  # noqa: F401 - importing it puts ``program/`` on sys.path

from mips.blocks import UseInfo
from mips.registers import RegisterAllocator, RegisterPoolExhausted, T_REGISTERS


def live(next_use: int) -> UseInfo:
    return UseInfo(live=True, next_use=next_use)


def dead() -> UseInfo:
    return UseInfo(live=False)


class EmptyRegisterTests(unittest.TestCase):
    def test_first_allocation_gets_an_empty_register(self) -> None:
        allocator = RegisterAllocator(homes={})
        reg = allocator.get_reg([], "x", {})
        self.assertEqual("$t0", reg)
        self.assertEqual([], allocator.drain())  # no spill/reload needed

    def test_successive_allocations_fill_the_pool_in_order(self) -> None:
        allocator = RegisterAllocator(homes={})
        picked = []
        for index in range(len(T_REGISTERS)):
            reg = allocator.get_reg([], f"x{index}", {})
            allocator.bind(f"x{index}", reg)
            picked.append(reg)
        self.assertEqual(T_REGISTERS, picked)


class ReuseTests(unittest.TestCase):
    def test_reuses_an_operands_register_when_it_dies_here(self) -> None:
        # t0 = y op z, where y's last use is this very instruction: its
        # register is free to become the result's register, no spill at all.
        allocator = RegisterAllocator(homes={})
        allocator.bind("y", "$t0")
        reg = allocator.get_reg(["y"], "t5", {"y": dead()})
        self.assertEqual("$t0", reg)

    def test_does_not_reuse_a_register_still_needed_later(self) -> None:
        allocator = RegisterAllocator(homes={})
        allocator.bind("y", "$t0")
        reg = allocator.get_reg(["y"], "t5", {"y": live(next_use=7)})
        self.assertNotEqual("$t0", reg)
        self.assertEqual("$t1", reg)

    def test_does_not_reuse_a_register_shared_with_another_live_name(self) -> None:
        allocator = RegisterAllocator(homes={})
        allocator.bind("y", "$t0")
        # ``z`` also lives in $t0 (e.g. a prior ``z = y``); evicting it would
        # silently lose z's value even though y itself dies here.
        allocator.register_holds["$t0"].add("z")
        allocator.descriptor("z").registers.add("$t0")
        reg = allocator.get_reg(["y"], "t5", {"y": dead(), "z": live(next_use=3)})
        self.assertNotEqual("$t0", reg)


class SpillTests(unittest.TestCase):
    def test_spills_when_the_pool_is_full(self) -> None:
        allocator = RegisterAllocator(homes={"old": "-4($fp)"})
        for index, reg in enumerate(T_REGISTERS):
            allocator.bind(f"x{index}", reg)
        allocator.bind("old", "$t0")  # overwrite x0's slot with 'old'
        reg = allocator.get_reg([], "new", {})
        self.assertEqual("$t0", reg)
        self.assertIn("    sw $t0, -4($fp)", allocator.drain())

    def test_spilling_a_name_already_in_memory_needs_no_store(self) -> None:
        allocator = RegisterAllocator(homes={"a": "-4($fp)"})
        for reg in T_REGISTERS:
            allocator.bind(f"filler{reg}", reg)
        allocator.register_holds["$t3"] = {"a"}
        descriptor = allocator.descriptor("a")
        descriptor.registers = {"$t3"}
        descriptor.in_memory = True  # already has a safe copy at its home
        allocator.spill("$t3")
        self.assertEqual([], allocator.drain())

    def test_prefers_the_victim_needed_furthest_away(self) -> None:
        allocator = RegisterAllocator(homes={"soon": "-4($fp)", "later": "-8($fp)"})
        allocator.bind("soon", "$t0")
        allocator.bind("later", "$t1")
        info = {"soon": live(next_use=1), "later": live(next_use=50)}
        victim = allocator._spill_policy.choose(T_REGISTERS[:2], info)
        self.assertEqual("$t1", victim)

    def test_prefers_a_name_never_used_again_over_one_still_live(self) -> None:
        allocator = RegisterAllocator(homes={"dead_var": "-4($fp)", "live_var": "-8($fp)"})
        allocator.bind("dead_var", "$t0")
        allocator.bind("live_var", "$t1")
        info = {"dead_var": dead(), "live_var": live(next_use=2)}
        victim = allocator._spill_policy.choose(T_REGISTERS[:2], info)
        self.assertEqual("$t0", victim)

    def test_exhausted_pool_without_a_spill_policy_raises(self) -> None:
        allocator = RegisterAllocator(homes={})
        with self.assertRaises(RegisterPoolExhausted):
            allocator._spill_policy.choose([], {})


class ReloadTests(unittest.TestCase):
    def test_ensure_in_register_reloads_a_spilled_value(self) -> None:
        allocator = RegisterAllocator(homes={"a": "-4($fp)"})
        allocator.bind("a", "$t0")
        allocator.spill("$t0")
        self.assertEqual(["    sw $t0, -4($fp)"], allocator.drain())
        self.assertTrue(allocator.descriptor("a").in_memory)
        self.assertEqual(set(), allocator.descriptor("a").registers)
        reg = allocator.ensure_in_register("a")
        self.assertEqual([f"    lw {reg}, -4($fp)"], allocator.drain())
        self.assertIn(reg, allocator.descriptor("a").registers)

    def test_ensure_in_register_is_free_when_already_loaded(self) -> None:
        allocator = RegisterAllocator(homes={"a": "-4($fp)"})
        allocator.bind("a", "$t0")
        reg = allocator.ensure_in_register("a")
        self.assertEqual("$t0", reg)
        self.assertEqual([], allocator.drain())


class CallBoundaryTests(unittest.TestCase):
    def test_spill_all_flushes_every_caller_saved_register(self) -> None:
        allocator = RegisterAllocator(homes={"a": "-4($fp)", "b": "-8($fp)"})
        allocator.bind("a", "$t0")
        allocator.bind("b", "$t1")
        allocator.spill_all()
        self.assertEqual(set(), allocator.register_holds["$t0"])
        self.assertEqual(set(), allocator.register_holds["$t1"])
        lines = allocator.drain()
        self.assertIn("    sw $t0, -4($fp)", lines)
        self.assertIn("    sw $t1, -8($fp)", lines)


if __name__ == "__main__":
    unittest.main()
