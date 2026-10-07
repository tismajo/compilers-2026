"""``foreach`` (lowered to an index loop) and ``switch`` (C-style fallthrough)."""

from __future__ import annotations

import unittest

from support import TacTestCase


class ForeachTests(TacTestCase):
    SOURCE = (
        "let nums: integer[] = [1, 2, 3];\n"
        "foreach (n in nums) {\n"
        "  if (n == 2) { continue; }\n"
        "  print(n);\n"
        "  if (n == 3) { break; }\n"
        "}\n"
    )

    def test_index_starts_at_zero_and_reads_the_length_once(self) -> None:
        code = self.code(self.SOURCE)
        after_literal = code[6:8]
        self.assertEqual(["t0 = 0", "t1 = *(nums + 0)"], after_literal)

    def test_continue_skips_to_the_increment_break_leaves_the_loop(self) -> None:
        code = self.code(self.SOURCE)
        # ``continue`` -> increment label (``L1``); ``break`` -> the loop's
        # end label (``L2``), reusing the same ``state.loops`` stack as
        # ``while``/``for``.
        self.assertEqual("goto L1", code[code.index("ifFalse t3 goto L3") + 1])
        self.assertEqual("goto L2", code[code.index("ifFalse t3 goto L4") + 1])
        self.assertEqual(["L1:", "t0 = t0 + 1", "goto L0", "L2:"], code[-4:])

    def test_element_is_loaded_through_the_same_array_primitives(self) -> None:
        code = self.code(self.SOURCE)
        self.assertIn("n = *(nums + t3)", code)


class SwitchTests(TacTestCase):
    SOURCE = (
        "let x: integer = 1;\n"
        "switch (x) {\n"
        "  case 1:\n"
        "    print(\"one\");\n"
        "  case 2:\n"
        "    print(\"two\");\n"
        "    break;\n"
        "  default:\n"
        "    print(\"other\");\n"
        "}\n"
    )

    def test_bodies_are_compared_then_laid_out_back_to_back(self) -> None:
        code = self.code(self.SOURCE)
        self.assertEqual(
            [
                "x = 1",
                "t0 = x == 1",
                "if t0 goto L1",
                "t0 = x == 2",
                "if t0 goto L2",
                "goto L3",
                "L1:",
                'print "one"',
                "L2:",
                'print "two"',
                "goto L0",
                "L3:",
                'print "other"',
                "L0:",
            ],
            code,
        )

    def test_case_without_break_falls_through_to_the_next_body(self) -> None:
        code = self.code(self.SOURCE)
        # Nothing separates ``L1:`` (case 1's body) from ``L2:`` (case 2's):
        # falling off the first body runs straight into the second.
        one = code.index("L1:")
        self.assertEqual('print "one"', code[one + 1])
        self.assertEqual("L2:", code[one + 2])

    def test_break_jumps_past_every_remaining_case(self) -> None:
        code = self.code(self.SOURCE)
        self.assertIn("goto L0", code)
        self.assertEqual("L0:", code[-1])

    def test_switch_without_default_falls_through_to_the_end_label(self) -> None:
        code = self.code(
            "let x: integer = 5;\nswitch (x) { case 5: print(1); }\n",
        )
        self.assertEqual("goto L0", code[code.index("if t0 goto L1") + 1])
        self.assertEqual(["L0:"], code[-1:])

    def test_continue_inside_a_switch_still_targets_the_enclosing_loop(self) -> None:
        source = (
            "let i: integer = 0;\n"
            "while (i < 3) {\n"
            "  switch (i) {\n"
            "    case 0:\n"
            "      continue;\n"
            "  }\n"
            "  i = i + 1;\n"
            "}\n"
        )
        code = self.code(source)
        # The ``while`` condition is checked at ``L0``; ``continue`` inside
        # the switch must still go there, not to the switch's own end label.
        self.assertEqual("L0:", code[1])
        self.assertIn("goto L0", code)


if __name__ == "__main__":
    unittest.main()
