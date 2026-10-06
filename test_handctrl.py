"""
Automated unit & integration test suite for HandCtrl.
Tests all gesture states, coordinate transforms, calibration, and safety systems.
"""

from __future__ import annotations

import os
import sys
import time
import numpy as np

from handctrl.config import Settings
from handctrl.camera.calibration import CalibrationManager, CornerPoint
from handctrl.camera.camera_manager import CameraManager
from handctrl.gestures.gesture_state import GestureState, GestureName, GestureEvent
from handctrl.gestures.gesture_utils import (
    WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP,
    INDEX_MCP, INDEX_PIP, INDEX_DIP,
    MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP,
    RING_MCP, RING_PIP, RING_DIP,
    PINKY_MCP, PINKY_PIP, PINKY_DIP,
    THUMB_MCP, THUMB_IP,
    get_finger_states, pinch_distance, is_open_palm, is_thumbs_up, is_index_only, is_two_fingers
)
from handctrl.gestures.gesture_detector import GestureDetector
from handctrl.control.mouse_controller import MouseController
from handctrl.control.action_manager import ActionManager
from handctrl.camera.hand_tracker import HandData


def create_base_hand() -> np.ndarray:
    """Create a default fist/folded hand where all fingers are folded toward the palm."""
    lm = np.zeros((21, 3), dtype=np.float32)
    # Wrist at center bottom
    lm[WRIST] = [0.5, 0.8, 0.0]

    # Thumb folded
    lm[1] = [0.45, 0.7, 0.0]
    lm[2] = [0.42, 0.65, 0.0]
    lm[3] = [0.45, 0.62, 0.0]
    lm[THUMB_TIP] = [0.48, 0.60, 0.0]

    # Knuckles (MCP)
    lm[INDEX_MCP] = [0.45, 0.55, 0.0]
    lm[MIDDLE_MCP] = [0.50, 0.53, 0.0]
    lm[RING_MCP] = [0.55, 0.55, 0.0]
    lm[PINKY_MCP] = [0.60, 0.58, 0.0]

    # Folded fingers (tips closer to wrist/MCP than PIP)
    for mcp, pip, dip, tip in [
        (INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
        (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
        (RING_MCP, RING_PIP, RING_DIP, RING_TIP),
        (PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP),
    ]:
        lm[pip] = lm[mcp] + [0.0, -0.08, 0.0]
        lm[dip] = lm[pip] + [0.0, 0.04, 0.0]  # folded back down
        lm[tip] = lm[mcp] + [0.0, 0.02, 0.0]  # curled into palm

    return lm


def extend_finger(lm: np.ndarray, mcp: int, pip: int, dip: int, tip: int) -> None:
    """Extend a finger straight up away from the wrist."""
    lm[pip] = lm[mcp] + [0.0, -0.08, 0.0]
    lm[dip] = lm[pip] + [0.0, -0.06, 0.0]
    lm[tip] = lm[dip] + [0.0, -0.06, 0.0]


def extend_thumb_up(lm: np.ndarray) -> None:
    """Position thumb sticking straight up."""
    lm[1] = [0.42, 0.65, 0.0]
    lm[THUMB_MCP] = [0.40, 0.55, 0.0]
    lm[THUMB_IP] = [0.40, 0.45, 0.0]
    lm[THUMB_TIP] = [0.40, 0.35, 0.0]


def extend_thumb_side(lm: np.ndarray) -> None:
    """Position thumb spread sideways for open palm."""
    lm[1] = [0.35, 0.65, 0.0]
    lm[THUMB_MCP] = [0.30, 0.60, 0.0]
    lm[THUMB_IP] = [0.25, 0.55, 0.0]
    lm[THUMB_TIP] = [0.20, 0.50, 0.0]


def test_calibration():
    print("--- Testing CalibrationManager ---")
    cal = CalibrationManager()
    cal.start_calibration()
    assert cal.is_calibrating
    assert cal.current_step_index == 0

    # Step 1: Top-Left
    finished = cal.record_point(0.15, 0.15)
    assert not finished
    assert cal.current_step_index == 1

    # Step 2: Top-Right
    finished = cal.record_point(0.85, 0.15)
    assert not finished
    assert cal.current_step_index == 2

    # Step 3: Bottom-Right
    finished = cal.record_point(0.85, 0.85)
    assert not finished
    assert cal.current_step_index == 3

    # Step 4: Bottom-Left
    finished = cal.record_point(0.15, 0.85)
    assert finished
    assert not cal.is_calibrating
    assert cal.data.is_calibrated

    # Map a point in the center of the calibrated box (0.5, 0.5) to a 1920x1080 screen
    sx, sy = cal.map_point(0.5, 0.5, 1920, 1080)
    print(f"Calibrated center map: (0.5, 0.5) -> ({sx}, {sy})")
    assert 900 <= sx <= 1020, f"Expected center x ~960, got {sx}"
    assert 500 <= sy <= 580, f"Expected center y ~540, got {sy}"

    # Map top-left corner
    sx, sy = cal.map_point(0.15, 0.15, 1920, 1080)
    print(f"Calibrated top-left map: (0.15, 0.15) -> ({sx}, {sy})")
    assert 0 <= sx <= 50
    assert 0 <= sy <= 50

    cal.reset_to_defaults()
    print("CalibrationManager test passed!")


def test_gesture_detection():
    print("--- Testing Gesture Detection & State Machine ---")
    settings = Settings()
    detector = GestureDetector(settings)
    detector.enable()

    # 1. Test INDEX FINGER = CURSOR
    lm_index = create_base_hand()
    extend_finger(lm_index, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP)
    hand = HandData(landmarks=[], landmark_array=lm_index, handedness="Right", detection_confidence=0.95, tracking_confidence=0.90)

    events = detector.update(hand)
    print(f"Index gesture: {detector.current_gesture_name}, state: {detector.gesture_state.name}")
    assert detector.current_gesture_name == GestureName.INDEX_CURSOR.value
    assert detector.gesture_state == GestureState.CURSOR
    assert len(events) == 1
    assert events[0].action == "cursor_move"

    # 2. Test TWO FINGERS = SCROLL
    lm_two = create_base_hand()
    extend_finger(lm_two, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP)
    extend_finger(lm_two, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP)
    hand = HandData(landmarks=[], landmark_array=lm_two, handedness="Right", detection_confidence=0.95, tracking_confidence=0.90)

    events = detector.update(hand)
    print(f"Two fingers gesture: {detector.current_gesture_name}, state: {detector.gesture_state.name}")
    assert detector.current_gesture_name == GestureName.TWO_FINGERS.value
    assert detector.gesture_state == GestureState.SCROLLING

    # 3. Test THUMBS UP = MEDIA PLAY/PAUSE
    lm_thumb = create_base_hand()
    extend_thumb_up(lm_thumb)
    hand = HandData(landmarks=[], landmark_array=lm_thumb, handedness="Right", detection_confidence=0.95, tracking_confidence=0.90)

    events = detector.update(hand)
    print(f"Thumbs up gesture: {detector.current_gesture_name}, state: {detector.gesture_state.name}")
    assert detector.current_gesture_name == GestureName.THUMBS_UP.value
    assert detector.gesture_state == GestureState.THUMBS_UP
    assert any(ev.action == "media_play_pause" for ev in events)

    # 4. Test OPEN PALM = PAUSE
    lm_palm = create_base_hand()
    extend_thumb_side(lm_palm)
    extend_finger(lm_palm, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP)
    extend_finger(lm_palm, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP)
    extend_finger(lm_palm, RING_MCP, RING_PIP, RING_DIP, RING_TIP)
    extend_finger(lm_palm, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP)
    hand = HandData(landmarks=[], landmark_array=lm_palm, handedness="Right", detection_confidence=0.95, tracking_confidence=0.90)

    detector.state.palm_hold_start = 0.0  # fresh palm
    events = detector.update(hand)
    print(f"Open palm gesture: {detector.current_gesture_name}, state: {detector.gesture_state.name}")
    assert detector.current_gesture_name == GestureName.OPEN_PALM.value
    assert detector.gesture_state == GestureState.PAUSED
    assert any(ev.action == "paused" for ev in events)

    # 5. Test OPEN PALM HOLD (1 second) -> EMERGENCY STOP
    # Simulate holding palm past EMERGENCY_HOLD_DURATION
    detector.state.palm_hold_start = time.time() - 1.5
    events = detector.update(hand)
    print(f"Held palm emergency stop state: {detector.gesture_state.name}")
    assert any(ev.action == "emergency_stop" for ev in events)
    assert detector.gesture_state == GestureState.DISABLED

    # 6. Test PINCH = LEFT CLICK and DRAG
    detector.enable()  # re-enable
    lm_pinch = create_base_hand()
    # Put thumb tip and index tip extremely close (distance < 0.02)
    lm_pinch[THUMB_TIP] = [0.40, 0.40, 0.0]
    lm_pinch[INDEX_TIP] = [0.41, 0.40, 0.0]
    hand = HandData(landmarks=[], landmark_array=lm_pinch, handedness="Right", detection_confidence=0.95, tracking_confidence=0.90)

    events = detector.update(hand)
    print(f"Pinch start: gesture={detector.current_gesture_name}, state={detector.gesture_state.name}, events={[e.action for e in events]}")
    assert detector.current_gesture_name == GestureName.PINCH.value
    assert detector.gesture_state == GestureState.PINCH_DETECTED
    assert any(ev.action == "click" for ev in events)

    # Frame 2: PINCH HOLD (should NOT click again)
    events2 = detector.update(hand)
    print(f"Pinch hold: state={detector.gesture_state.name}, events={[e.action for e in events2]}")
    assert detector.gesture_state == GestureState.PINCH_HOLD
    assert not any(ev.action == "click" for ev in events2)

    # Frame 3: PINCH + MOVEMENT -> DRAG
    lm_pinch_drag = lm_pinch.copy()
    lm_pinch_drag[THUMB_TIP] = [0.55, 0.40, 0.0]
    lm_pinch_drag[INDEX_TIP] = [0.56, 0.40, 0.0]
    hand_drag = HandData(landmarks=[], landmark_array=lm_pinch_drag, handedness="Right", detection_confidence=0.95, tracking_confidence=0.90)
    events3 = detector.update(hand_drag)
    print(f"Pinch drag: state={detector.gesture_state.name}, events={[e.action for e in events3]}")
    assert detector.gesture_state == GestureState.DRAGGING
    assert any(ev.action == "drag_start" for ev in events3)

    # Frame 4: PINCH RELEASE
    events4 = detector.update(None)
    print(f"Pinch release: state={detector.gesture_state.name}, events={[e.action for e in events4]}")
    assert any(ev.action == "drag_end" for ev in events4)

    print("Gesture Detection & State Machine test passed!")


def test_mouse_controller_and_safety():
    print("--- Testing MouseController & Safety Systems ---")
    settings = Settings()
    mouse = MouseController(settings)

    # Test coordinate mapping
    sx, sy = mouse.map_to_screen(0.5, 0.5)
    print(f"Uncalibrated center mapped: (0.5, 0.5) -> ({sx}, {sy})")
    assert 0 <= sx <= 3840
    assert 0 <= sy <= 2160

    # Test release_all safety
    mouse._dragging = True
    mouse.release_all()
    assert not mouse._dragging

    # Test ActionManager disabled state (must NOT dispatch actions)
    mgr = ActionManager(settings)
    assert not mgr.is_enabled
    # Dispatching click when disabled should do nothing safely
    mgr.dispatch([GestureEvent("click")])
    mgr.dispatch([GestureEvent("cursor_move", {"x": 0.5, "y": 0.5})])

    # Emergency stop action always fires and disables manager
    mgr.enable()
    assert mgr.is_enabled
    mgr.dispatch([GestureEvent("emergency_stop")])
    assert not mgr.is_enabled

    print("MouseController & Safety test passed!")


if __name__ == "__main__":
    test_calibration()
    test_gesture_detection()
    test_mouse_controller_and_safety()
    print("\n[SUCCESS] ALL TESTS COMPLETED AND PASSED PERFECTLY!")
