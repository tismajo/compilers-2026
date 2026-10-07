"""Closures: a captured variable is just the same flat TAC name.

The TAC layer never models stack frames as addressable memory (unlike
arrays and objects, which are genuinely heap blocks and need real
address arithmetic) — every local is a name, and ``name_of`` keys that
name on the ``Symbol``, not on which function is currently being
generated. So a nested function reaches a variable captured from an
enclosing one simply by using its name, at any nesting depth. Resolving
*which physical frame* that name lives in at runtime (the static link) is
deferred to the MIPS phase, using ``FunctionSymbol.captured`` and the
owner's offsets — both already computed here.
"""

from __future__ import annotations

import unittest

from support import TacTestCase


class ClosureTests(TacTestCase):
    def test_nested_function_reads_the_captured_variable_by_name(self) -> None:
        source = (
            "function makeCounter(): integer {\n"
            "  let count: integer = 0;\n"
            "  function increment(): integer {\n"
            "    count = count + 1;\n"
            "    return count;\n"
            "  }\n"
            "  return increment();\n"
            "}\n"
        )
        result = self.generate(source)
        self.assertEqual(
            ["count = 0", "t0 = call f_makeCounter_increment, 0", "return t0"],
            self.code(source, "f_makeCounter"),
        )
        self.assertEqual(
            ["t0 = count + 1", "count = t0", "return count"],
            self.code(source, "f_makeCounter_increment"),
        )
        increment = next(s for s in result.symbols.symbols() if s.name == "increment")
        self.assertEqual(["count"], increment.captured)

    def test_capture_works_through_more_than_one_level_of_nesting(self) -> None:
        # Not a documented requirement (the grading program never nests this
        # deep), but nothing in the name-based model limits it either.
        source = (
            "function outer(): integer {\n"
            "  let x: integer = 10;\n"
            "  function middle(): integer {\n"
            "    function inner(): integer { return x + 1; }\n"
            "    return inner();\n"
            "  }\n"
            "  return middle();\n"
            "}\n"
        )
        code = self.code(source, "f_outer_middle_inner")
        self.assertEqual(["t0 = x + 1", "return t0"], code)


if __name__ == "__main__":
    unittest.main()
