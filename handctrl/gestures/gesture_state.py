"""
HandCtrl — Gesture state machine.

Manages explicit gesture states and transitions to prevent
repeated action triggering. Every frame, the detector classifies
the hand pose and the state machine decides what action (if any)
should fire.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class GestureState(Enum):
    """All possible states of the gesture control system."""

    IDLE = auto()
    CURSOR = auto()
    PINCH_DETECTED = auto()  # pinch just started → trigger click
    PINCH_HOLD = auto()  # pinch held, waiting for drag or release
    DRAGGING = auto()
    SCROLLING = auto()
    PAUSED = auto()  # open-palm pause
    THUMBS_UP = auto()
    SWIPING = auto()
    TAP_DETECTED = auto()
    DISABLED = auto()


class GestureName(Enum):
    """The raw classified gesture (from finger states)."""

    NONE = "NONE"
    INDEX_CURSOR = "INDEX CURSOR"
    AIR_TAP = "AIR TAP"
    PINCH = "PINCH"
    TWO_FINGERS = "TWO FINGERS"
    OPEN_PALM = "OPEN PALM"
    THUMBS_UP = "THUMBS UP"
    FIST = "FIST"


@dataclass
class GestureEvent:
    """A discrete action the control system should execute."""

    action: str  # e.g. "click", "drag_start", "drag_end", "scroll", "media_play_pause", etc.
    data: dict = field(default_factory=dict)


@dataclass
class GestureStateData:
    """Mutable data tracking the gesture state machine."""

    state: GestureState = GestureState.DISABLED
    current_gesture: GestureName = GestureName.NONE
    confidence: float = 0.0

    # Timing
    pinch_start_time: float = 0.0
    palm_hold_start: float = 0.0
    last_thumbs_up_time: float = 0.0
    last_swipe_time: float = 0.0
    last_click_time: float = 0.0

    # Positions (normalised)
    pinch_start_pos: tuple[float, float] = (0.0, 0.0)
    last_scroll_y: float = 0.0
    swipe_start_x: float = 0.0
    swipe_start_time: float = 0.0

    # Flags
    drag_threshold_met: bool = False
    emergency_palm_active: bool = False

    def reset_pinch(self) -> None:
        self.pinch_start_time = 0.0
        self.pinch_start_pos = (0.0, 0.0)
        self.drag_threshold_met = False

    def reset_scroll(self) -> None:
        self.last_scroll_y = 0.0

    def reset_palm(self) -> None:
        self.palm_hold_start = 0.0
        self.emergency_palm_active = False
