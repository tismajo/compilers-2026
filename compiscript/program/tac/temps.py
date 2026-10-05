"""Temporary allocation with recycling.

A temporary is released as soon as an instruction consumes it as an operand,
so ``a + b * c - d`` needs a single temporary instead of three. Released names
go back to a LIFO pool and are handed out again before a new one is created.
"""

from __future__ import annotations

import re

TEMP_PATTERN = re.compile(r"^t\d+$")


class TempAllocator:
    def __init__(self) -> None:
        self._next = 0
        self._free: list[str] = []
        self._live: set[str] = set()
        self.peak = 0

    @staticmethod
    def is_temp(name: str) -> bool:
        return bool(TEMP_PATTERN.match(name))

    def new(self) -> str:
        if self._free:
            name = self._free.pop()
        else:
            name = f"t{self._next}"
            self._next += 1
        self._live.add(name)
        self.peak = max(self.peak, len(self._live))
        return name

    def release(self, *names: str) -> None:
        """Return temporaries to the pool; anything else is ignored."""
        for name in names:
            if name in self._live:
                self._live.remove(name)
                self._free.append(name)

    @property
    def live(self) -> int:
        return len(self._live)
