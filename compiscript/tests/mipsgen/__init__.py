"""MIPS back-end battery: register allocation, basic blocks, call sequence
and the end-to-end generator, run for real in a MIPS simulator.

Named ``mipsgen`` and not ``mips``, the same reasoning ``codegen`` is named
instead of ``tac``: this package sits next to ``program/mips``, and a test
package with that exact name would shadow it on ``sys.path`` when
``unittest discover`` adds ``tests/`` to it (first found wins).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
