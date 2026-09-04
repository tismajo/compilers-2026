"""Classes: members, constructors, ``this`` and inheritance."""

from __future__ import annotations

import unittest

from support import SemanticTestCase

ANIMAL = (
    "class Animal {\n"
    "  let name: string;\n"
    "  function constructor(name: string) { this.name = name; }\n"
    '  function speak(): string { return this.name + " hace ruido."; }\n'
    "}\n"
)


class InstanceTests(SemanticTestCase):
    def test_instantiating_a_declared_class(self) -> None:
        self.assert_ok(ANIMAL + 'let pet: Animal = new Animal("Rex");\n')

    def test_instantiating_an_unknown_class(self) -> None:
        self.assert_diagnostic("let pet: Animal = new Animal();", "SEM501", line=1)

    def test_class_declared_after_its_use(self) -> None:
        # The first pass registers every class before the bodies are walked.
        self.assert_ok('let pet: Animal = new Animal("Rex");\n' + ANIMAL)


class MemberTests(SemanticTestCase):
    def test_attribute_and_method_access(self) -> None:
        source = ANIMAL + (
            'let pet: Animal = new Animal("Rex");\n'
            "let name: string = pet.name;\n"
            "print(pet.speak());\n"
        )
        self.assert_ok(source)

    def test_unknown_member_is_reported(self) -> None:
        source = ANIMAL + 'let pet: Animal = new Animal("Rex");\nprint(pet.edad);\n'
        self.assert_diagnostic(source, "SEM502", line=7)

    def test_member_access_on_a_primitive_is_reported(self) -> None:
        source = 'let name: string = "a";\nprint(name.largo);\n'
        self.assert_diagnostic(source, "SEM506", line=2)

    def test_property_assignment_is_type_checked(self) -> None:
        source = ANIMAL + 'let pet: Animal = new Animal("Rex");\npet.name = 1;\n'
        self.assert_diagnostic(source, "SEM105", line=7)

    def test_property_assignment_with_a_valid_type(self) -> None:
        source = ANIMAL + 'let pet: Animal = new Animal("Rex");\npet.name = "Toby";\n'
        self.assert_ok(source)


class ConstructorTests(SemanticTestCase):
    def test_constructor_arguments_are_validated(self) -> None:
        self.assert_diagnostic(ANIMAL + "new Animal();\n", "SEM504", line=6)

    def test_constructor_argument_types_are_validated(self) -> None:
        self.assert_diagnostic(ANIMAL + "new Animal(1);\n", "SEM302", line=6)

    def test_implicit_constructor_takes_no_arguments(self) -> None:
        self.assert_ok("class Punto {}\nlet p: Punto = new Punto();\n")

    def test_implicit_constructor_rejects_arguments(self) -> None:
        self.assert_diagnostic("class Punto {}\nnew Punto(1);\n", "SEM504", line=2)


class ThisTests(SemanticTestCase):
    def test_this_inside_a_method(self) -> None:
        self.assert_ok(ANIMAL)

    def test_this_outside_a_class_is_reported(self) -> None:
        self.assert_diagnostic("print(this);", "SEM503", line=1)

    def test_this_resolves_to_the_current_class(self) -> None:
        source = (
            "class Nodo {\n"
            "  let valor: integer;\n"
            "  function propio(): Nodo { return this; }\n"
            "}\n"
        )
        self.assert_ok(source)


class InheritanceTests(SemanticTestCase):
    def test_inherited_members_are_visible(self) -> None:
        source = ANIMAL + (
            "class Dog : Animal {\n"
            '  function speak(): string { return this.name + " ladra."; }\n'
            "}\n"
            'let pet: Dog = new Dog("Rex");\n'
            "print(pet.speak());\n"
            "print(pet.name);\n"
        )
        self.assert_ok(source)

    def test_subclass_is_assignable_to_its_parent(self) -> None:
        source = ANIMAL + (
            "class Dog : Animal {}\n" 'let pet: Animal = new Dog("Rex");\n'
        )
        self.assert_ok(source)

    def test_parent_is_not_assignable_to_a_subclass(self) -> None:
        source = ANIMAL + (
            "class Dog : Animal {}\n" 'let pet: Dog = new Animal("Rex");\n'
        )
        self.assert_diagnostic(source, "SEM105", line=7)

    def test_missing_parent_is_reported(self) -> None:
        self.assert_diagnostic("class Dog : Animal {}", "SEM206", line=1)

    def test_inheritance_cycle_is_reported(self) -> None:
        self.assert_diagnostic("class A : B {}\nclass B : A {}\n", "SEM207")

    def test_override_with_a_different_signature_is_reported(self) -> None:
        source = (
            "class Base { function saludar(): string { return \"hola\"; } }\n"
            "class Hija : Base { function saludar(): integer { return 1; } }\n"
        )
        self.assert_diagnostic(source, "SEM505", line=2)

    def test_override_with_the_same_signature_is_accepted(self) -> None:
        source = (
            "class Base { function saludar(): string { return \"hola\"; } }\n"
            "class Hija : Base { function saludar(): string { return \"hey\"; } }\n"
        )
        self.assert_ok(source)

    def test_duplicate_member_in_a_class_is_reported(self) -> None:
        source = "class Base { let a: integer; let a: string; }"
        self.assert_diagnostic(source, "SEM211", line=1)


if __name__ == "__main__":
    unittest.main()
