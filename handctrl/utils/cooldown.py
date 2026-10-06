"""
HandCtrl — Cooldown timer utility.
"""

from __future__ import annotations

import time


class Cooldown:
    """Simple cooldown timer — returns True only after the cooldown period."""

    def __init__(self, duration: float) -> None:
        self._duration = duration
        self._last_trigger: float = 0.0

    @property
    def duration(self) -> float:
        return self._duration

    @duration.setter
    def duration(self, value: float) -> None:
        self._duration = max(0.0, value)

    def ready(self) -> bool:
        """Check if cooldown has elapsed since last trigger."""
        return time.time() - self._last_trigger >= self._duration

    def trigger(self) -> bool:
        """Trigger the cooldown if ready. Returns True if it fired."""
        if self.ready():
            self._last_trigger = time.time()
            return True
        return False

    def reset(self) -> None:
        """Reset the cooldown timer."""
        self._last_trigger = 0.0
