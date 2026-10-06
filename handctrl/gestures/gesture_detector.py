"""
HandCtrl — Gesture detector.

Classifies the raw hand pose each frame, then runs the state machine
to produce discrete GestureEvents. This is the central bridge between
hand tracking and computer control.
"""

from __future__ import annotations

import time
from typing import List, Optional

import numpy as np

from handctrl.config import Settings
from handctrl.camera.hand_tracker import HandData
from handctrl.gestures.gesture_state import (
    GestureState,
    GestureName,
    GestureEvent,
    GestureStateData,
)
from handctrl.gestures.gesture_utils import (
    get_finger_states,
    pinch_distance,
    is_thumbs_up,
    is_open_palm,
    is_index_only,
    is_two_fingers,
    index_tip_position,
    hand_center,
)
from handctrl.gestures.depth_tap import DepthTapDetector
from handctrl.utils.logger import get_logger

log = get_logger()


class GestureDetector:
    """
    Per-frame gesture classification and state machine.

    Call ``update()`` each frame with hand data to get a list of events.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._state = GestureStateData()
        self._depth_tap = DepthTapDetector(
            penetration_threshold=getattr(settings, "depth_tap_threshold", 0.045),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def depth_tap(self) -> DepthTapDetector:
        return self._depth_tap

    def draw_effects(self, frame_bgr: np.ndarray) -> None:
        """Render active gesture visual effects (e.g. depth tap ripples)."""
        self._depth_tap.draw_ripples(frame_bgr)

    @property
    def state(self) -> GestureStateData:
        return self._state

    @property
    def current_gesture_name(self) -> str:
        return self._state.current_gesture.value

    @property
    def gesture_state(self) -> GestureState:
        return self._state.state

    def enable(self) -> None:
        """Enable gesture control (transition from DISABLED → IDLE)."""
        if self._state.state == GestureState.DISABLED:
            self._state.state = GestureState.IDLE
            log.info("Gesture control ENABLED")

    def disable(self) -> None:
        """Disable gesture control immediately."""
        events = []
        # Clean up any active state
        if self._state.state == GestureState.DRAGGING:
            events.append(GestureEvent("drag_end"))
        self._state.state = GestureState.DISABLED
        self._state.current_gesture = GestureName.NONE
        self._state.confidence = 0.0
        self._state.reset_pinch()
        self._state.reset_scroll()
        self._state.reset_palm()
        self._depth_tap.reset()
        log.info("Gesture control DISABLED")
        return events

    def update(self, hand: Optional[HandData]) -> List[GestureEvent]:
        """
        Process one frame of hand data and return any triggered events.

        Args:
            hand: The detected hand, or None if no hand visible.

        Returns:
            List of GestureEvent objects to be executed.
        """
        if self._state.state == GestureState.DISABLED:
            return []

        if hand is None:
            return self._handle_no_hand()

        # Check confidence threshold
        if hand.detection_confidence < self._settings.detection_confidence:
            return self._handle_no_hand()

        self._state.confidence = hand.detection_confidence
        lm = hand.landmark_array

        # Classify the raw gesture
        gesture = self._classify(lm)
        self._state.current_gesture = gesture

        # Run state machine transitions
        return self._transition(gesture, lm)

    # ------------------------------------------------------------------
    # Classification (pure — no side effects)
    # ------------------------------------------------------------------
    def _classify(self, lm: np.ndarray) -> GestureName:
        """Classify the current hand pose into a gesture name."""
        # Check open palm first (most fingers up)
        if is_open_palm(lm):
            return GestureName.OPEN_PALM

        # Thumbs up
        if is_thumbs_up(lm):
            return GestureName.THUMBS_UP

        # Check pinch (thumb + index close)
        pdist = pinch_distance(lm)
        if pdist < self._settings.pinch_threshold:
            return GestureName.PINCH

        # Two fingers (scroll)
        if is_two_fingers(lm):
            return GestureName.TWO_FINGERS

        # Index only (cursor)
        if is_index_only(lm):
            return GestureName.INDEX_CURSOR

        # Nothing recognised
        states = get_finger_states(lm)
        if not any(states.values()):
            return GestureName.FIST

        return GestureName.NONE

    # ------------------------------------------------------------------
    # State machine transitions
    # ------------------------------------------------------------------
    def _transition(self, gesture: GestureName, lm: np.ndarray) -> List[GestureEvent]:
        """Apply state transitions based on the classified gesture."""
        events: List[GestureEvent] = []
        now = time.time()
        s = self._state

        # ---- OPEN PALM = pause / emergency stop ----
        if gesture == GestureName.OPEN_PALM:
            return self._handle_open_palm(lm, now, events)

        # Palm no longer held → reset emergency timer
        s.reset_palm()

        # ---- THUMBS UP = media play/pause ----
        if gesture == GestureName.THUMBS_UP:
            return self._handle_thumbs_up(now, events)

        # ---- PINCH ----
        if gesture == GestureName.PINCH:
            return self._handle_pinch(lm, now, events)

        # ---- If we were in a pinch/drag state and now we aren't ----
        if s.state in (GestureState.PINCH_DETECTED, GestureState.PINCH_HOLD):
            s.state = GestureState.IDLE
            s.reset_pinch()
        elif s.state == GestureState.DRAGGING:
            events.append(GestureEvent("drag_end"))
            s.state = GestureState.IDLE
            s.reset_pinch()
            log.info("Drag ended")

        # ---- TWO FINGERS = scroll ----
        if gesture == GestureName.TWO_FINGERS:
            return self._handle_scroll(lm, events)

        # Exit scrolling if we were
        if s.state == GestureState.SCROLLING:
            s.state = GestureState.IDLE
            s.reset_scroll()

        # ---- INDEX CURSOR & 3D DEPTH TAP ----
        if gesture == GestureName.INDEX_CURSOR:
            tap_fired = False
            aim_x, aim_y = index_tip_position(lm)

            if getattr(self._settings, "enable_depth_tap", True):
                self._depth_tap.penetration_threshold = getattr(self._settings, "depth_tap_threshold", 0.045)
                tap_fired, tap_pos = self._depth_tap.update(lm, is_index_pointing=True)
                if tap_pos is not None:
                    aim_x, aim_y = tap_pos

            if tap_fired:
                s.state = GestureState.TAP_DETECTED
                s.current_gesture = GestureName.AIR_TAP
                events.append(GestureEvent("click", {"x": aim_x, "y": aim_y}))
                log.info("3D Depth Tap triggered click at (%.3f, %.3f)", aim_x, aim_y)
            else:
                s.state = GestureState.CURSOR
                events.append(GestureEvent("cursor_move", {"x": aim_x, "y": aim_y}))

            return events
        else:
            # Inform depth tap that finger is no longer pointing
            self._depth_tap.update(lm, is_index_pointing=False)

        # ---- PAUSED → IDLE if gesture changed from OPEN_PALM ----
        if s.state == GestureState.PAUSED and gesture != GestureName.OPEN_PALM:
            s.state = GestureState.IDLE

        # Default: IDLE
        if s.state not in (GestureState.DISABLED, GestureState.PAUSED):
            s.state = GestureState.IDLE

        return events

    # ------------------------------------------------------------------
    # Individual gesture handlers
    # ------------------------------------------------------------------
    def _handle_no_hand(self) -> List[GestureEvent]:
        """Handle frames where no hand is detected."""
        events: List[GestureEvent] = []
        s = self._state
        if s.state == GestureState.DRAGGING:
            events.append(GestureEvent("drag_end"))
            log.info("Drag ended (hand lost)")
        if s.state != GestureState.PAUSED:
            s.state = GestureState.IDLE
        s.current_gesture = GestureName.NONE
        s.confidence = 0.0
        s.reset_pinch()
        s.reset_scroll()
        s.reset_palm()
        self._depth_tap.reset()
        return events

    def _handle_open_palm(
        self, lm: np.ndarray, now: float, events: List[GestureEvent]
    ) -> List[GestureEvent]:
        s = self._state

        # End any active drag
        if s.state == GestureState.DRAGGING:
            events.append(GestureEvent("drag_end"))
            s.reset_pinch()

        # Emergency stop: hold open palm for EMERGENCY_HOLD_DURATION
        from handctrl.config import EMERGENCY_HOLD_DURATION

        if s.palm_hold_start == 0.0:
            s.palm_hold_start = now
        elif now - s.palm_hold_start >= EMERGENCY_HOLD_DURATION:
            if not s.emergency_palm_active:
                s.emergency_palm_active = True
                s.state = GestureState.DISABLED
                events.append(GestureEvent("emergency_stop"))
                log.info("Emergency stop triggered by open palm hold")
                return events

        s.state = GestureState.PAUSED
        events.append(GestureEvent("paused"))
        return events

    def _handle_thumbs_up(
        self, now: float, events: List[GestureEvent]
    ) -> List[GestureEvent]:
        s = self._state

        if now - s.last_thumbs_up_time >= self._settings.media_cooldown:
            events.append(GestureEvent("media_play_pause"))
            s.last_thumbs_up_time = now
            log.info("Thumbs up -> media play/pause")

        s.state = GestureState.THUMBS_UP
        return events

    def _handle_pinch(
        self, lm: np.ndarray, now: float, events: List[GestureEvent]
    ) -> List[GestureEvent]:
        s = self._state
        x, y = index_tip_position(lm)

        if s.state not in (
            GestureState.PINCH_DETECTED,
            GestureState.PINCH_HOLD,
            GestureState.DRAGGING,
        ):
            # --- PINCH START → click ---
            if now - s.last_click_time >= self._settings.click_debounce:
                s.state = GestureState.PINCH_DETECTED
                s.pinch_start_time = now
                s.pinch_start_pos = (x, y)
                s.drag_threshold_met = False
                events.append(GestureEvent("click", {"x": x, "y": y}))
                s.last_click_time = now
                log.debug("Pinch start → click at (%.3f, %.3f)", x, y)
            return events

        # Already pinching — check for drag
        if s.state == GestureState.PINCH_DETECTED:
            s.state = GestureState.PINCH_HOLD

        if s.state == GestureState.PINCH_HOLD:
            # Check if we've moved enough to enter drag mode
            dx = x - s.pinch_start_pos[0]
            dy = y - s.pinch_start_pos[1]
            dist = (dx ** 2 + dy ** 2) ** 0.5
            # Convert normalised distance to approximate pixels for threshold
            from handctrl.config import CAMERA_WIDTH, DRAG_MOVEMENT_THRESHOLD
            pixel_dist = dist * CAMERA_WIDTH
            if pixel_dist > DRAG_MOVEMENT_THRESHOLD:
                s.state = GestureState.DRAGGING
                s.drag_threshold_met = True
                events.append(GestureEvent("drag_start", {"x": x, "y": y}))
                log.info("Drag started")

        if s.state == GestureState.DRAGGING:
            events.append(GestureEvent("drag_move", {"x": x, "y": y}))

        return events

    def _handle_scroll(
        self, lm: np.ndarray, events: List[GestureEvent]
    ) -> List[GestureEvent]:
        s = self._state
        _, y = index_tip_position(lm)

        if s.state != GestureState.SCROLLING:
            # Just entered scroll mode — record starting y
            s.state = GestureState.SCROLLING
            s.last_scroll_y = y
            return events

        # Calculate vertical delta
        dy = y - s.last_scroll_y
        # Apply sensitivity — only scroll if movement exceeds threshold
        min_scroll_delta = 0.005  # normalised — prevents micro-scrolls
        if abs(dy) > min_scroll_delta:
            scroll_amount = dy * self._settings.scroll_sensitivity
            events.append(GestureEvent("scroll", {"amount": scroll_amount}))
            s.last_scroll_y = y

        return events

    # ------------------------------------------------------------------
    # Swipe detection (called externally per frame with position history)
    # ------------------------------------------------------------------
    def check_swipe(self, lm: np.ndarray) -> Optional[GestureEvent]:
        """
        Detect horizontal swipes from hand center movement.

        Should be called each frame independently of the state machine.
        Returns a swipe event or None.
        Will NOT trigger during normal cursor movement, pinch, drag, or scroll.
        """
        s = self._state
        now = time.time()

        # Do NOT trigger a swipe from normal cursor movement, pinch, drag, or scroll
        if s.state in (
            GestureState.CURSOR,
            GestureState.PINCH_DETECTED,
            GestureState.PINCH_HOLD,
            GestureState.DRAGGING,
            GestureState.SCROLLING,
        ):
            s.swipe_start_time = 0.0
            return None

        # Minimum gesture confidence required
        from handctrl.config import MIN_ACTION_CONFIDENCE
        if s.confidence < MIN_ACTION_CONFIDENCE:
            s.swipe_start_time = 0.0
            return None

        if now - s.last_swipe_time < self._settings.swipe_cooldown:
            return None

        cx, _ = hand_center(lm)

        if s.swipe_start_time == 0.0:
            s.swipe_start_x = cx
            s.swipe_start_time = now
            return None

        dx = cx - s.swipe_start_x
        dt = now - s.swipe_start_time

        # Reset tracking window if too much time passed
        if dt > 0.5:
            s.swipe_start_x = cx
            s.swipe_start_time = now
            return None

        if abs(dx) >= self._settings.swipe_sensitivity:
            speed = abs(dx) / dt if dt > 0 else 0
            from handctrl.config import SWIPE_MIN_SPEED
            if speed >= SWIPE_MIN_SPEED:
                direction = "right" if dx > 0 else "left"
                s.last_swipe_time = now
                s.swipe_start_x = cx
                s.swipe_start_time = now
                log.info("Swipe %s detected (dx=%.3f, speed=%.2f)", direction, dx, speed)
                return GestureEvent(f"swipe_{direction}")

        return None
