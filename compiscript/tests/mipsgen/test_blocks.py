"""Basic-block splitting and the next-use/liveness scan that feeds ``get_reg()``."""

from __future__ import annotations

import unittest

import support  # noqa: F401 - importing it puts ``program/`` on sys.path

from mips.blocks import operand_names, split_blocks
from tac.instructions import Quad


def quads(*rows: tuple) -> list[Quad]:
    return [Quad(*row) for row in rows]


class OperandNamesTests(unittest.TestCase):
    def test_binary_op_uses_both_operands_and_defines_the_result(self) -> None:
        uses, definition = operand_names(Quad("+", "a", "b", "t0"))
        self.assertEqual(["a", "b"], uses)
        self.assertEqual("t0", definition)

    def test_literals_are_not_treated_as_names(self) -> None:
        uses, definition = operand_names(Quad("+", "a", "3", "t0"))
        self.assertEqual(["a"], uses)
        self.assertEqual("t0", definition)

    def test_call_only_defines_its_result_the_label_is_not_a_name(self) -> None:
        uses, definition = operand_names(Quad("call", "f_factorial", "1", "t0"))
        self.assertEqual([], uses)
        self.assertEqual("t0", definition)

    def test_store_has_no_definition_its_result_field_is_a_use(self) -> None:
        uses, definition = operand_names(Quad("store", "base", "4", "x"))
        self.assertEqual(["base", "x"], uses)
        self.assertIsNone(definition)

    def test_label_and_goto_touch_no_name(self) -> None:
        self.assertEqual(([], None), operand_names(Quad("label", "L0")))
        self.assertEqual(([], None), operand_names(Quad("goto", "L0")))


class SplitBlocksTests(unittest.TestCase):
    def test_a_straight_line_function_is_a_single_block(self) -> None:
        body = quads(
            ("assign", "1", None, "a"),
            ("assign", "2", None, "b"),
            ("+", "a", "b", "t0"),
            ("return", "t0"),
        )
        blocks = split_blocks(body)
        self.assertEqual(1, len(blocks))
        self.assertEqual(4, len(blocks[0].quads))

    def test_an_if_splits_into_condition_then_and_join_blocks(self) -> None:
        # if (a > 0) { b = 1; } ; print(b);
        body = quads(
            (">", "a", "0", "t0"),
            ("if_false", "t0", "L0"),
            ("assign", "1", None, "b"),
            ("label", "L0"),
            ("print", "b"),
        )
        blocks = split_blocks(body)
        # Leaders: 0 (start), 2 (right after the conditional jump), 3 (L0,
        # the jump's target) — three blocks.
        self.assertEqual(3, len(blocks))
        self.assertEqual([0, 2, 3], [block.start for block in blocks])

    def test_a_loop_back_edge_is_its_own_leader(self) -> None:
        body = quads(
            ("label", "L0"),
            ("<", "i", "3", "t0"),
            ("if_false", "t0", "L1"),
            ("+", "i", "1", "i"),
            ("goto", "L0"),
            ("label", "L1"),
        )
        blocks = split_blocks(body)
        self.assertEqual([0, 3, 5], [block.start for block in blocks])

    def test_begin_and_end_func_are_not_part_of_any_block(self) -> None:
        body = quads(
            ("begin_func", "8"),
            ("return", None),
            ("end_func",),
        )
        blocks = split_blocks(body)
        self.assertEqual(1, len(blocks))
        self.assertEqual(["return"], [quad.op for quad in blocks[0].quads])


class NextUseTests(unittest.TestCase):
    def test_a_temp_used_once_is_dead_right_after(self) -> None:
        # t0 = a + b ; c = t0  -> at "c = t0", t0 is used and then dead.
        block = split_blocks(
            quads(
                ("+", "a", "b", "t0"),
                ("assign", "t0", None, "c"),
            )
        )[0]
        at_definition = block.info[0]["t0"]
        self.assertTrue(at_definition.live)
        self.assertEqual(1, at_definition.next_use)

    def test_a_declared_variable_is_conservatively_live_past_the_block(self) -> None:
        block = split_blocks(quads(("assign", "1", None, "x")))[0]
        self.assertTrue(block.info[0]["x"].live)

    def test_a_temp_is_never_live_past_the_end_of_its_block(self) -> None:
        # t0 is defined and consumed entirely within this one block (the
        # generator's own discipline guarantees this — see blocks.py).
        block = split_blocks(
            quads(
                ("+", "a", "b", "t0"),
                ("print", "t0"),
            )
        )[0]
        # The info recorded at an instruction answers "is this operand still
        # needed *after* this point" — not "is it used here" (it obviously
        # is, that is why it is in the dict at all). t0's only use is this
        # very ``print``, so it must come back not live, with no next use:
        # exactly the signal that lets ``get_reg`` reuse its register right
        # after for something else.
        last_quad_info = block.info[1]
        self.assertFalse(last_quad_info["t0"].live)
        self.assertIsNone(last_quad_info["t0"].next_use)

    def test_an_operand_needed_twice_reports_the_nearer_use_first(self) -> None:
        # t0 = a + 1 ; t1 = a + 2  -- scanning backward, at the first
        # instruction 'a' must report its next use is the second one.
        block = split_blocks(
            quads(
                ("+", "a", "1", "t0"),
                ("+", "a", "2", "t1"),
            )
        )[0]
        self.assertEqual(1, block.info[0]["a"].next_use)


if __name__ == "__main__":
    unittest.main()
