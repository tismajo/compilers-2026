"""try/catch: the only runtime fault modeled is an out-of-range array access."""

from __future__ import annotations

import unittest

from support import TacTestCase


class TryCatchTests(TacTestCase):
    def test_bounds_failure_inside_try_jumps_to_its_catch(self) -> None:
        source = (
            "let arr: integer[] = [1, 2, 3];\n"
            "try {\n"
            "  print(arr[10]);\n"
            "} catch (err) {\n"
            "  print(err);\n"
            "}\n"
        )
        code = self.code(source)
        fail_index = code.index("if t1 goto L2")
        self.assertEqual("L2:", code[fail_index + 2])
        self.assertEqual(
            ["err = \"Índice fuera de rango\"", "goto L0"],
            code[fail_index + 3 : fail_index + 5],
        )
        # The normal path (no fault) skips the handler entirely.
        self.assertIn("goto L1", code)
        self.assertEqual(["L0:", "print err", "L1:"], code[-3:])

    def test_bounds_failure_outside_any_try_halts(self) -> None:
        source = "let arr: integer[] = [1, 2, 3];\nprint(arr[10]);\n"
        code = self.code(source)
        self.assertIn("halt", code)
        self.assertNotIn("err", " ".join(code))

    def test_nested_try_catch_targets_its_own_handler(self) -> None:
        source = (
            "let arr: integer[] = [1, 2, 3];\n"
            "try {\n"
            "  try {\n"
            "    print(arr[10]);\n"
            "  } catch (innerErr) {\n"
            "    print(innerErr);\n"
            "  }\n"
            "} catch (outerErr) {\n"
            "  print(outerErr);\n"
            "}\n"
        )
        code = self.code(source)
        # The failing access is only ever guarded by the inner handler.
        fail_index = next(i for i, line in enumerate(code) if "innerErr =" in line)
        self.assertIn("goto L", code[fail_index + 1])
        self.assertNotIn("outerErr", " ".join(code[: fail_index + 2]))
        self.assertIn("print outerErr", code)


if __name__ == "__main__":
    unittest.main()
