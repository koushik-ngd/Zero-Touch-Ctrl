"""
HandCtrl — Keyboard controller.

Sends media keyboard commands (play/pause, next/previous track).
"""

from __future__ import annotations

import pyautogui

from handctrl.utils.logger import get_logger

log = get_logger()

# Disable PyAutoGUI fail-safe (we have our own emergency system)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


class KeyboardController:
    """Sends keyboard shortcuts for media control."""

    @staticmethod
    def media_play_pause() -> None:
        """Send the media play/pause key."""
        try:
            pyautogui.press("playpause", _pause=False)
            log.info("Sent media play/pause")
        except Exception as exc:
            log.error("media_play_pause failed: %s", exc)

    @staticmethod
    def media_next_track() -> None:
        """Send the next track key."""
        try:
            pyautogui.press("nexttrack", _pause=False)
            log.info("Sent media next track")
        except Exception as exc:
            log.error("media_next_track failed: %s", exc)

    @staticmethod
    def media_prev_track() -> None:
        """Send the previous track key."""
        try:
            pyautogui.press("prevtrack", _pause=False)
            log.info("Sent media previous track")
        except Exception as exc:
            log.error("media_prev_track failed: %s", exc)
