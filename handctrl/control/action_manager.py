"""
HandCtrl — Action manager.

Central dispatcher that translates GestureEvents into actual
mouse/keyboard actions. This is the single point where all
computer control happens, making it easy to enable/disable.
"""

from __future__ import annotations

from typing import List, Optional

from handctrl.camera.calibration import CalibrationManager
from handctrl.config import Settings
from handctrl.control.mouse_controller import MouseController
from handctrl.control.keyboard_controller import KeyboardController
from handctrl.gestures.gesture_state import GestureEvent
from handctrl.utils.logger import get_logger

log = get_logger()


class ActionManager:
    """
    Dispatches gesture events to the appropriate controller.

    All computer interaction flows through here. When control is disabled,
    no actions are dispatched.
    """

    def __init__(
        self,
        settings: Settings,
        calibration: Optional[CalibrationManager] = None,
    ) -> None:
        self._settings = settings
        self._mouse = MouseController(settings, calibration=calibration)
        self._keyboard = KeyboardController()
        self._enabled = False

    def set_calibration(self, calibration: CalibrationManager) -> None:
        """Update calibration on the mouse controller."""
        self._mouse.set_calibration(calibration)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        self._mouse.reset_smoother()
        log.info("Action manager ENABLED")

    def disable(self) -> None:
        self._enabled = False
        self._mouse.release_all()
        log.info("Action manager DISABLED")

    def dispatch(self, events: List[GestureEvent]) -> None:
        """
        Process a list of gesture events and execute the corresponding actions.

        Does nothing when disabled, except for emergency_stop which always fires.
        """
        for event in events:
            # Emergency stop always works
            if event.action == "emergency_stop":
                self.disable()
                continue

            if not self._enabled:
                continue

            self._dispatch_one(event)

    def _dispatch_one(self, event: GestureEvent) -> None:
        """Dispatch a single event."""
        action = event.action
        data = event.data

        if action == "cursor_move":
            if self._settings.enable_cursor:
                self._mouse.move_cursor(data["x"], data["y"])

        elif action == "click":
            if self._settings.enable_click:
                self._mouse.click()

        elif action == "drag_start":
            if self._settings.enable_drag:
                self._mouse.drag_start()

        elif action == "drag_move":
            if self._settings.enable_drag:
                self._mouse.drag_move(data["x"], data["y"])

        elif action == "drag_end":
            if self._settings.enable_drag:
                self._mouse.drag_end()

        elif action == "scroll":
            if self._settings.enable_scroll:
                self._mouse.scroll(data["amount"])

        elif action == "media_play_pause":
            if self._settings.enable_thumbs_up:
                self._keyboard.media_play_pause()

        elif action == "swipe_left":
            if self._settings.enable_swipe:
                self._keyboard.media_prev_track()

        elif action == "swipe_right":
            if self._settings.enable_swipe:
                self._keyboard.media_next_track()

        elif action == "paused":
            pass  # UI display only

        else:
            log.warning("Unknown event action: %s", action)

    def release_all(self) -> None:
        """Safety: release all held state."""
        self._mouse.release_all()
