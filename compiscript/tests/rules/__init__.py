"""Semantic rule battery: one passing and one failing case per rule."""

import sys
from pathlib import Path

# ``support`` lives in ``tests/``; make it importable from this package.
sys.path.append(str(Path(__file__).resolve().parents[1]))
