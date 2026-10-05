"""Intermediate code battery: translation, temporaries and runtime layout.

Named ``codegen`` instead of ``tac`` so it does not shadow ``program/tac``.
"""

import sys
from pathlib import Path

# ``support`` lives in ``tests/``; make it importable from this package.
sys.path.append(str(Path(__file__).resolve().parents[1]))
