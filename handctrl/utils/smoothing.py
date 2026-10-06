"""
HandCtrl — Smoothing utilities.

Exponential moving average and cursor position smoothing.
"""

from __future__ import annotations

from typing import Tuple


class ExponentialSmoother:
    """
    Exponential Moving Average smoother for cursor positions.

    smoothed = alpha * previous + (1 - alpha) * current

    Higher alpha = more smoothing (slower response).
    Lower alpha = less smoothing (faster response, more jitter).
    """

    def __init__(self, alpha: float = 0.4) -> None:
        self._alpha = max(0.0, min(1.0, alpha))
        self._prev_x: float | None = None
        self._prev_y: float | None = None

    @property
    def alpha(self) -> float:
        return self._alpha

    @alpha.setter
    def alpha(self, value: float) -> None:
        self._alpha = max(0.0, min(1.0, value))

    def smooth(self, x: float, y: float) -> Tuple[float, float]:
        """
        Apply exponential smoothing to (x, y) coordinates.

        First call initialises with the raw value (no smoothing).
        """
        if self._prev_x is None or self._prev_y is None:
            self._prev_x = x
            self._prev_y = y
            return x, y

        sx = self._alpha * self._prev_x + (1 - self._alpha) * x
        sy = self._alpha * self._prev_y + (1 - self._alpha) * y
        self._prev_x = sx
        self._prev_y = sy
        return sx, sy

    def reset(self) -> None:
        """Clear smoother state."""
        self._prev_x = None
        self._prev_y = None
