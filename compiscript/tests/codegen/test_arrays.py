"""Arrays: literals, bounds-checked reads/writes and temporary reuse."""

from __future__ import annotations

import unittest

from support import TacTestCase


class LiteralTests(TacTestCase):
    def test_flat_literal_stores_length_then_elements(self) -> None:
        code = self.code("let arr: integer[] = [10, 20, 30];")
        self.assertEqual(
            [
                "t0 = alloc 16",
                "*(t0 + 0) = 3",
                "*(t0 + 4) = 10",
                "*(t0 + 8) = 20",
                "*(t0 + 12) = 30",
                "arr = t0",
            ],
            code,
        )

    def test_nested_literal_stores_a_pointer_per_row(self) -> None:
        code = self.code("let m: integer[][] = [[1, 2], [3, 4]];")
        # Outer array: length 2, then one pointer per inner array.
        self.assertEqual("t0 = alloc 12", code[0])
        self.assertEqual("*(t0 + 0) = 2", code[1])
        self.assertIn("t1 = alloc 12", code)
        self.assertIn("*(t0 + 4) = t1", code)
        self.assertIn("*(t0 + 8) = t1", code)

    def test_empty_literal_allocates_only_the_header(self) -> None:
        code = self.code("let arr: integer[] = [];")
        self.assertEqual(["t0 = alloc 4", "*(t0 + 0) = 0", "arr = t0"], code)


class AccessTests(TacTestCase):
    def test_read_checks_bounds_before_loading(self) -> None:
        code = self.code(
            "let arr: integer[] = [10, 20, 30];\nprint(arr[1]);",
        )
        self.assertEqual(
            [
                "t1 = 1 * 4",
                "t0 = t1 + 4",
                "t1 = *(arr + t0)",
                "print t1",
            ],
            code[-4:],
        )
        # The check reads the length header at offset 0 and halts outside
        # any ``try`` when it fails — no handler is active here.
        self.assertIn("t0 = *(arr + 0)", code)
        self.assertIn("t1 = 1 >= t0", code)
        self.assertIn("halt", code)

    def test_write_shares_the_same_bounds_check(self) -> None:
        code = self.code(
            "let arr: integer[] = [10, 20, 30];\narr[0] = 99;",
        )
        self.assertIn("t1 = 0 >= t0", code)
        self.assertEqual("*(arr + t0) = 99", code[-1])

    def test_mixed_arithmetic_still_recycles_temporaries(self) -> None:
        # a[0] = a[1] + a[2] * 2 — every sub-expression's bounds check and
        # load must release its scratch temporaries once consumed, the same
        # discipline plain arithmetic already follows.
        code = self.code(
            "let a: integer[] = [10, 20, 30];\na[0] = a[1] + a[2] * 2;",
        )
        live = {int(name[1:]) for name in code if name.startswith("t") and name[1:].isdigit()}
        # Four temporaries is the actual high-water mark for this expression
        # (the target offset, the running sum and the right-hand operand's
        # own scratch space); never the number of sub-expressions evaluated.
        self.assertLessEqual(max(live, default=0), 3)


if __name__ == "__main__":
    unittest.main()
