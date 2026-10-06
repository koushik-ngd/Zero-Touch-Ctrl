"""
HandCtrl — Mouse controller.

Translates gesture events into actual mouse actions using PyAutoGUI.
Handles coordinate mapping, smoothing, clamping, and jump protection.
"""

from __future__ import annotations

from typing import Tuple

import pyautogui

from handctrl.camera.calibration import CalibrationManager
from handctrl.config import Settings, SCREEN_WIDTH, SCREEN_HEIGHT
from handctrl.utils.smoothing import ExponentialSmoother
from handctrl.utils.logger import get_logger

log = get_logger()

# Disable PyAutoGUI fail-safe (we have our own emergency system)
pyautogui.FAILSAFE = False
# Disable pause between actions for responsiveness
pyautogui.PAUSE = 0


class MouseController:
    """Maps normalised hand positions to screen coordinates and controls the mouse."""

    def __init__(
        self,
        settings: Settings,
        calibration: Optional[CalibrationManager] = None,
    ) -> None:
        self._settings = settings
        self._calibration = calibration
        self._smoother = ExponentialSmoother(alpha=settings.cursor_smoothing)
        self._screen_w: int = 0
        self._screen_h: int = 0
        self._prev_screen_x: int | None = None
        self._prev_screen_y: int | None = None
        self._dragging = False
        self._detect_screen_size()

    def set_calibration(self, calibration: CalibrationManager) -> None:
        """Update calibration manager reference."""
        self._calibration = calibration

    def _detect_screen_size(self) -> None:
        """Get current screen resolution."""
        self._screen_w, self._screen_h = pyautogui.size()
        log.info("Screen size: %dx%d", self._screen_w, self._screen_h)

    # ------------------------------------------------------------------
    # Coordinate mapping
    # ------------------------------------------------------------------
    def map_to_screen(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """
        Map normalised camera coordinates (0-1) to screen pixels.

        If custom 4-point calibration is active, uses perspective transformation.
        Otherwise applies dead-zone cropping so edges of the camera frame
        are ignored, giving the user a comfortable working area.
        """
        if self._calibration is not None and self._calibration.data.is_calibrated:
            cx, cy = self._calibration.map_point(norm_x, norm_y, self._screen_w, self._screen_h)
            if cx >= 0 and cy >= 0:
                return cx, cy

        dz = self._settings.edge_dead_zone

        # Clamp to dead-zone range then remap to 0-1
        x = max(0.0, min(1.0, (norm_x - dz) / (1.0 - 2.0 * dz)))
        y = max(0.0, min(1.0, (norm_y - dz) / (1.0 - 2.0 * dz)))

        # Screen coordinates
        screen_x = int(x * self._screen_w)
        screen_y = int(y * self._screen_h)

        return screen_x, screen_y

    # ------------------------------------------------------------------
    # Cursor movement
    # ------------------------------------------------------------------
    def move_cursor(self, norm_x: float, norm_y: float) -> None:
        """Move the cursor to the mapped screen position with smoothing."""
        # Map to screen
        raw_x, raw_y = self.map_to_screen(norm_x, norm_y)

        # Apply smoothing
        self._smoother.alpha = self._settings.cursor_smoothing
        sx, sy = self._smoother.smooth(float(raw_x), float(raw_y))
        target_x, target_y = int(sx), int(sy)

        # Jump protection
        if self._prev_screen_x is not None and self._prev_screen_y is not None:
            dx = abs(target_x - self._prev_screen_x)
            dy = abs(target_y - self._prev_screen_y)
            max_jump = self._settings.max_cursor_jump
            if dx > max_jump or dy > max_jump:
                # Reject this frame — likely a tracking glitch
                return

        # Clamp to screen bounds
        target_x = max(0, min(self._screen_w - 1, target_x))
        target_y = max(0, min(self._screen_h - 1, target_y))

        self._prev_screen_x = target_x
        self._prev_screen_y = target_y

        pyautogui.moveTo(target_x, target_y, _pause=False)

    # ------------------------------------------------------------------
    # Click
    # ------------------------------------------------------------------
    def click(self) -> None:
        """Perform a single left click at the current cursor position."""
        try:
            pyautogui.click(_pause=False)
        except Exception as exc:
            log.error("Click failed: %s", exc)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------
    def drag_start(self) -> None:
        """Begin mouse drag (press and hold left button)."""
        if not self._dragging:
            try:
                pyautogui.mouseDown(button="left", _pause=False)
                self._dragging = True
            except Exception as exc:
                log.error("Drag start failed: %s", exc)

    def drag_move(self, norm_x: float, norm_y: float) -> None:
        """Move during drag (same as move_cursor but drag is active)."""
        self.move_cursor(norm_x, norm_y)

    def drag_end(self) -> None:
        """End mouse drag (release left button)."""
        if self._dragging:
            try:
                pyautogui.mouseUp(button="left", _pause=False)
                self._dragging = False
            except Exception as exc:
                log.error("Drag end failed: %s", exc)

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------
    def scroll(self, amount: float) -> None:
        """
        Scroll vertically.

        Positive amount = scroll up, negative = scroll down.
        MediaPipe y increases downward, so the gesture detector
        already handles the direction mapping.
        """
        clicks = int(-amount)  # pyautogui: positive = scroll up
        if clicks != 0:
            try:
                pyautogui.scroll(clicks, _pause=False)
            except Exception as exc:
                log.error("Scroll failed: %s", exc)

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------
    def release_all(self) -> None:
        """Release any held mouse buttons — safety cleanup."""
        if self._dragging:
            try:
                pyautogui.mouseUp(button="left", _pause=False)
            except Exception:
                pass
            self._dragging = False
        self._smoother.reset()
        self._prev_screen_x = None
        self._prev_screen_y = None

    def reset_smoother(self) -> None:
        """Reset the position smoother (e.g. after re-enable)."""
        self._smoother.reset()
        self._prev_screen_x = None
        self._prev_screen_y = None
