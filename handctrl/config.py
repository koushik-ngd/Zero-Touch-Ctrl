"""
HandCtrl — Application configuration.

All configurable constants and default settings live here.
Settings are persisted to a local JSON file.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "settings.json"
CALIBRATION_FILE = APP_DIR / "calibration.json"
LOG_FILE = APP_DIR / "handctrl.log"

# ---------------------------------------------------------------------------
# Screen (populated at runtime)
# ---------------------------------------------------------------------------
SCREEN_WIDTH: int = 1920
SCREEN_HEIGHT: int = 1080

# ---------------------------------------------------------------------------
# Camera defaults
# ---------------------------------------------------------------------------
DEFAULT_CAMERA_INDEX: int = 0
CAMERA_WIDTH: int = 640
CAMERA_HEIGHT: int = 480
CAMERA_FPS: int = 30

# ---------------------------------------------------------------------------
# MediaPipe defaults
# ---------------------------------------------------------------------------
MP_MAX_HANDS: int = 1
MP_MIN_DETECTION_CONFIDENCE: float = 0.7
MP_MIN_TRACKING_CONFIDENCE: float = 0.6

# ---------------------------------------------------------------------------
# Gesture thresholds
# ---------------------------------------------------------------------------
PINCH_DISTANCE_THRESHOLD: float = 0.045  # normalised landmark distance
FINGER_EXTENDED_THRESHOLD: float = 0.03  # used for folded/extended checks
SCROLL_SENSITIVITY: float = 5.0
SWIPE_MIN_DISTANCE: float = 0.15  # normalised horizontal distance
SWIPE_MIN_SPEED: float = 0.4  # normalised units per second
DRAG_MOVEMENT_THRESHOLD: float = 10.0  # pixels before entering drag mode

# ---------------------------------------------------------------------------
# Cursor control
# ---------------------------------------------------------------------------
CURSOR_SMOOTHING: float = 0.4  # 0 = no smoothing, 1 = max smoothing
MAX_CURSOR_JUMP: int = 200  # max pixels the cursor may move in one frame
EDGE_DEAD_ZONE: float = 0.05  # fraction of camera frame ignored at edges

# ---------------------------------------------------------------------------
# Cooldowns (seconds)
# ---------------------------------------------------------------------------
MEDIA_ACTION_COOLDOWN: float = 1.0
SWIPE_COOLDOWN: float = 1.2
CLICK_DEBOUNCE: float = 0.25
EMERGENCY_HOLD_DURATION: float = 1.0

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------
MIN_ACTION_CONFIDENCE: float = 0.65
EMERGENCY_HOTKEY = "<ctrl>+<alt>+h"

# ---------------------------------------------------------------------------
# Gesture state names
# ---------------------------------------------------------------------------
class GestureState:
    IDLE = "IDLE"
    CURSOR = "CURSOR"
    PINCH_DETECTED = "PINCH_DETECTED"
    DRAGGING = "DRAGGING"
    SCROLLING = "SCROLLING"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"
    THUMBS_UP = "THUMBS_UP"
    SWIPE = "SWIPE"


# ---------------------------------------------------------------------------
# Persisted user settings
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    """User-configurable settings persisted to JSON."""

    camera_index: int = DEFAULT_CAMERA_INDEX
    cursor_smoothing: float = CURSOR_SMOOTHING
    pinch_threshold: float = PINCH_DISTANCE_THRESHOLD
    scroll_sensitivity: float = SCROLL_SENSITIVITY
    swipe_sensitivity: float = SWIPE_MIN_DISTANCE
    detection_confidence: float = MP_MIN_DETECTION_CONFIDENCE
    tracking_confidence: float = MP_MIN_TRACKING_CONFIDENCE
    max_cursor_jump: int = MAX_CURSOR_JUMP
    edge_dead_zone: float = EDGE_DEAD_ZONE
    media_cooldown: float = MEDIA_ACTION_COOLDOWN
    swipe_cooldown: float = SWIPE_COOLDOWN
    click_debounce: float = CLICK_DEBOUNCE

    # Per-gesture enable toggles
    enable_cursor: bool = True
    enable_click: bool = True
    enable_drag: bool = True
    enable_scroll: bool = True
    enable_thumbs_up: bool = True
    enable_swipe: bool = True
    enable_palm_pause: bool = True

    def save(self, path: Optional[Path] = None) -> None:
        target = path or CONFIG_FILE
        target.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        target = path or CONFIG_FILE
        if not target.exists():
            return cls()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            # Only keep keys that match dataclass fields
            valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**valid)
        except (json.JSONDecodeError, TypeError):
            return cls()
