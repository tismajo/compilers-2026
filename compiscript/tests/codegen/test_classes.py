"""Classes: object layout, static constructors and vtable dispatch."""

from __future__ import annotations

import unittest

from support import TacTestCase

ANIMAL_DOG = (
    "class Animal {\n"
    "  let name: string;\n"
    "  function constructor(name: string) { this.name = name; }\n"
    "  function speak(): string { return this.name + \" makes a sound.\"; }\n"
    "}\n"
    "class Dog : Animal {\n"
    "  function speak(): string { return this.name + \" barks.\"; }\n"
    "}\n"
)


class VTableTests(TacTestCase):
    def test_override_replaces_the_same_slot(self) -> None:
        result = self.generate(ANIMAL_DOG + 'let a: Animal = new Dog("Rex");\nprint(a.speak());\n')
        vtables = {item.class_name: item.slots for item in result.tac.vtables}
        self.assertEqual(["Animal_speak"], vtables["Animal"])
        self.assertEqual(["Dog_speak"], vtables["Dog"])

    def test_inherited_method_keeps_its_slot_new_one_is_appended(self) -> None:
        source = (
            "class Animal {\n"
            "  function eat(): string { return \"eating\"; }\n"
            "  function speak(): string { return \"...\"; }\n"
            "}\n"
            "class Dog : Animal {\n"
            "  function speak(): string { return \"woof\"; }\n"
            "  function fetch(): string { return \"fetch\"; }\n"
            "}\n"
        )
        result = self.generate(source)
        vtables = {item.class_name: item.slots for item in result.tac.vtables}
        self.assertEqual(["Animal_eat", "Animal_speak"], vtables["Animal"])
        # ``eat`` is not overridden: same slot (0), same label as the parent.
        self.assertEqual(["Animal_eat", "Dog_speak", "Dog_fetch"], vtables["Dog"])

    def test_constructor_never_enters_the_vtable(self) -> None:
        result = self.generate(ANIMAL_DOG)
        for item in result.tac.vtables:
            self.assertNotIn("constructor", " ".join(item.slots).lower())

    def test_polymorphic_call_dispatches_through_the_vtable(self) -> None:
        code = self.code(
            ANIMAL_DOG + 'let a: Animal = new Dog("Rex");\nprint(a.speak());\n'
        )
        self.assertEqual(
            [
                "t0 = *(a + 0)",
                "t1 = *(t0 + 0)",
                "param a",
                "t1 = calli t1, 1",
                "print t1",
            ],
            code[-5:],
        )


class ObjectTests(TacTestCase):
    def test_new_allocates_stores_the_vtable_and_calls_the_constructor(self) -> None:
        code = self.code(ANIMAL_DOG + 'let a: Animal = new Dog("Rex");\n')
        self.assertEqual(
            [
                "t0 = alloc 8",
                "*(t0 + 0) = Dog_vtable",
                "param t0",
                'param "Rex"',
                "call Animal_constructor, 2",
                "a = t0",
            ],
            code,
        )

    def test_class_without_its_own_constructor_calls_the_inherited_one(self) -> None:
        code = self.code(ANIMAL_DOG + "let d: Dog = new Dog(\"Rex\");\n")
        self.assertIn("call Animal_constructor, 2", code)

    def test_attribute_read_and_write_use_the_computed_offset(self) -> None:
        code = self.code(ANIMAL_DOG, "Animal_speak")
        self.assertEqual("t0 = *(this + 4)", code[0])
        write_code = self.code(ANIMAL_DOG, "Animal_constructor")
        self.assertEqual(["*(this + 4) = name"], write_code)

    def test_method_body_runs_in_its_own_frame_with_this_first(self) -> None:
        result = self.generate(ANIMAL_DOG)
        frame = self.frame(result, "Dog_speak")
        self.assertEqual(["this"], [item.name for item in frame.parameters])


if __name__ == "__main__":
    unittest.main()
