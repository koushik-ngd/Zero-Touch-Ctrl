"""
HandCtrl — Entry point.

Launches the full HandCtrl desktop application with:
  - Live webcam preview with hand landmark overlay
  - Gesture detection and state machine
  - Mouse/keyboard control via hand gestures
  - Dark desktop UI with settings
  - Ctrl+Alt+H emergency hotkey

Usage:
    python main.py
"""

from __future__ import annotations

import sys

from handctrl.ui.app import HandCtrlApp
from handctrl.utils.logger import get_logger

log = get_logger()


def main() -> None:
    log.info("HandCtrl starting")

    try:
        app = HandCtrlApp()
        app.run()
    except Exception as exc:
        log.error("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
