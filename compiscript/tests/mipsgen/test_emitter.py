"""End-to-end TAC -> MIPS, checked structurally (real MARS execution is a
separate suite, ``test_simulator.py``, that only runs once ``Mars.jar`` is
vendored — see ``docs/generacion-mips.md``)."""

from __future__ import annotations

import unittest

import support  # noqa: F401 - importing it puts ``program/`` on sys.path

import mips


class MipsTestCase(unittest.TestCase):
    def mips_text(self, source: str) -> str:
        result = support.analyze_code(source)
        self.assertTrue(result.success, result.diagnostics)
        tac_program = result.generate_tac()
        self.assertIsNotNone(tac_program)
        mips_program = mips.generate(tac_program, result.symbols)
        return mips_program.render()

    def assert_no_todo(self, text: str) -> None:
        todo_lines = [line for line in text.splitlines() if "TODO MIPS" in line]
        self.assertEqual([], todo_lines)


FACTORIAL = (
    "function factorial(n: integer): integer {\n"
    "  if (n <= 1) { return 1; }\n"
    "  return n * factorial(n - 1);\n"
    "}\n"
    "print(factorial(5));\n"
)


class StructureTests(MipsTestCase):
    def test_every_function_gets_a_label_prologue_and_epilogue(self) -> None:
        text = self.mips_text(FACTORIAL)
        self.assertIn("main:", text)
        self.assertIn("f_factorial:", text)
        self.assertIn("f_factorial__ret:", text)
        self.assertIn("jr $ra", text)

    def test_frame_size_matches_header_plus_one_temp(self) -> None:
        text = self.mips_text(FACTORIAL)
        # 8 bytes of header (already reserved by the first ``addiu``) + one
        # temporary (4 bytes) = 12 total, so the *second* reservation —
        # everything beyond the header — is exactly 4.
        lines = text.splitlines()
        start = lines.index("f_factorial:")
        reservations = [line for line in lines[start : start + 6] if "addiu $sp, $sp, -" in line]
        self.assertEqual(["    addiu $sp, $sp, -8", "    addiu $sp, $sp, -4"], reservations)

    def test_recursive_call_and_arithmetic_have_no_todo(self) -> None:
        self.assert_no_todo(self.mips_text(FACTORIAL))

    def test_two_sibling_blocks_shadowing_the_same_global_name_get_distinct_labels(
        self,
    ) -> None:
        # Regression: both loops declare their own top-level ``i`` (shadowing
        # across sibling blocks is legal), and main has no real stack frame,
        # so both are TAC-level globals. Using the symbol's plain source name
        # as the .data label collided the two under one address; it must use
        # each one's own resolved TAC name instead (``i`` / ``i#2``).
        source = (
            "for (let i: integer = 0; i < 2; i = i + 1) { print(i); }\n"
            "for (let i: integer = 10; i < 12; i = i + 1) { print(i); }\n"
        )
        text = self.mips_text(source)
        self.assertIn("i: .word 0", text)
        self.assertIn("i#2: .word 0", text)

    def test_arguments_go_on_the_stack_not_in_a_registers(self) -> None:
        text = self.mips_text(FACTORIAL)
        self.assertNotIn("$a0, ", text.split("jal f_factorial")[0].split("main:")[1])

class ControlFlowTests(MipsTestCase):
    def test_if_else_reloads_the_variable_at_the_join_point(self) -> None:
        # The register-allocator-reset regression this guards against: both
        # branches define x in whatever register they each picked; the
        # label where they join must not trust either one, since at runtime
        # only one branch actually ran. It must reload x from memory instead.
        source = (
            "let x: integer = 0;\n"
            "if (x == 0) { x = 1; } else { x = 2; }\n"
            "print(x);\n"
        )
        lines = [line.strip() for line in self.mips_text(source).splitlines()]
        join = lines.index("L1:")
        self.assertEqual("lw $t0, x", lines[join + 1])

    def test_while_loop_has_no_todo(self) -> None:
        source = (
            "let i: integer = 0;\n"
            "while (i < 5) { i = i + 1; }\n"
            "print(i);\n"
        )
        self.assert_no_todo(self.mips_text(source))

    def test_foreach_index_and_length_survive_the_loop(self) -> None:
        # Regression: ``idx``/``length`` are plain TAC temps reused across
        # every iteration (``tac/generator.py``'s ``visitForeachStatement``),
        # which crosses several basic blocks — the one case a temp does not
        # die inside the block that created it. Without writing them through
        # to memory on every definition, the loop condition reads garbage
        # the moment a block boundary resets the register allocator.
        source = (
            "let numbers: integer[] = [1, 2, 3];\n"
            "foreach (n in numbers) { print(n); }\n"
        )
        self.assert_no_todo(self.mips_text(source))

    def test_switch_fallthrough_has_no_todo(self) -> None:
        source = (
            "let x: integer = 7;\n"
            "switch (x) {\n"
            "  case 7:\n"
            "    print(\"seven\");\n"
            "  default:\n"
            "    print(\"other\");\n"
            "}\n"
        )
        self.assert_no_todo(self.mips_text(source))

    def test_try_catch_bounds_failure_has_no_todo(self) -> None:
        source = (
            "let numbers: integer[] = [1, 2, 3];\n"
            "try {\n"
            "  print(numbers[10]);\n"
            "} catch (err) {\n"
            "  print(err);\n"
            "}\n"
        )
        self.assert_no_todo(self.mips_text(source))


class StringTests(MipsTestCase):
    def test_concat_and_tostr_use_the_runtime_routines(self) -> None:
        text = self.mips_text('let x: integer = 5;\nprint("x = " + x);\n')
        self.assertIn("jal __tostr_int", text)
        self.assertIn("jal __concat", text)
        self.assertIn("jal __alloc", text)
        self.assert_no_todo(text)

    def test_boolean_print_calls_the_runtime_helper(self) -> None:
        text = self.mips_text("print(true);\n")
        self.assertIn("jal __print_bool", text)


class ArraysClassesAndDispatchTests(MipsTestCase):
    def test_array_literal_and_indexed_read_have_no_todo(self) -> None:
        text = self.mips_text("let a: integer[] = [1, 2, 3];\nprint(a[0]);\n")
        self.assert_no_todo(text)
        self.assertIn("jal __alloc", text)
        # header (element count) then the three elements, in order
        self.assertIn("sw $t1, 0($t0)", text)

    def test_class_construction_and_virtual_dispatch_have_no_todo(self) -> None:
        # Dynamic dispatch always goes through the vtable (even with no
        # override in sight), so a plain method call should still compile
        # to an indirect jump, not a direct ``jal`` to the method's label.
        source = (
            "class Animal { let name: string; function speak(): string { return this.name; } }\n"
            'let a: Animal = new Animal();\n'
            "print(a.speak());\n"
        )
        text = self.mips_text(source)
        self.assert_no_todo(text)
        self.assertIn("Animal_vtable: .word Animal_speak", text)
        self.assertIn("jalr", text)
        self.assertNotIn("jal Animal_speak", text)

    def test_overriding_subclass_gets_its_own_vtable_slot(self) -> None:
        source = (
            "class Animal { function speak(): string { return \"...\"; } }\n"
            "class Dog : Animal { function speak(): string { return \"woof\"; } }\n"
            'let d: Dog = new Dog();\n'
        )
        text = self.mips_text(source)
        self.assert_no_todo(text)
        self.assertIn("Dog_vtable: .word Dog_speak", text)


if __name__ == "__main__":
    unittest.main()
