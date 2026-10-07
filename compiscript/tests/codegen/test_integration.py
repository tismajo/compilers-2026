"""End-to-end: the official sample program must fully translate to TAC."""

from __future__ import annotations

import unittest

from support import PROGRAM, TacTestCase


class OfficialProgramTests(TacTestCase):
    def test_program_cps_has_no_remaining_todo(self) -> None:
        source = (PROGRAM / "program.cps").read_text(encoding="utf-8")
        result = self.generate(source)
        todo_lines = [line for line in result.tac.render().splitlines() if "TODO" in line]
        self.assertEqual([], todo_lines)


if __name__ == "__main__":
    unittest.main()
