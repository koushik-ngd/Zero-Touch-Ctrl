"""
Zero-Touch-Ctrl — 3D Depth Tap ("Air Tap") Detector.

Enables touching a "virtual glass touchscreen in thin air" by pushing the index
finger forward towards the webcam along the Z-axis.
Features:
- Relative depth tracking (tip vs. MCP knuckle and wrist)
- Slow adaptive baseline that automatically adjusts to user distance
- Dynamic forward punch/velocity detection
- Anti-jitter aim stabilization (freezes aim during tap stroke)
- Automatic retraction/release debouncing
- Futuristic sci-fi ripple ring animation
"""

from __future__ import annotations

import time
from typing import Optional, Tuple, List
import cv2
import numpy as np

from handctrl.gestures.gesture_utils import (
    INDEX_TIP,
    INDEX_MCP,
    WRIST,
)
from handctrl.utils.logger import get_logger

log = get_logger()


class DepthTapDetector:
    """Detects forward taps along the Z-axis for virtual touchscreen clicking."""

    def __init__(
        self,
        penetration_threshold: float = 0.045,
        velocity_threshold: float = -0.28,
        cooldown: float = 0.35,
    ) -> None:
        self.penetration_threshold = penetration_threshold
        self.velocity_threshold = velocity_threshold
        self.cooldown = cooldown
        self.enabled: bool = True

        # Adaptive baseline for resting hand depth
        self._baseline_z: Optional[float] = None
        self._prev_z: Optional[float] = None
        self._prev_time: float = 0.0

        # State tracking
        self._is_pushed: bool = False
        self._last_tap_time: float = 0.0
        self._locked_aim_pos: Optional[Tuple[float, float]] = None

        # Visual ripple effects (start_time, (x, y), duration)
        self._active_ripples: List[dict] = []

    def reset(self) -> None:
        """Reset depth baseline and state."""
        self._baseline_z = None
        self._prev_z = None
        self._prev_time = 0.0
        self._is_pushed = False
        self._locked_aim_pos = None

    def update(
        self,
        lm: np.ndarray,
        is_index_pointing: bool,
    ) -> Tuple[bool, Optional[Tuple[float, float]]]:
        """
        Evaluate current hand landmarks for a forward depth tap.

        Args:
            lm: (21, 3) normalized hand landmarks [x, y, z]
            is_index_pointing: True if index finger is extended and aiming

        Returns:
            (tap_triggered: bool, stabilized_cursor_pos: Optional[Tuple[float, float]])
        """
        if not self.enabled:
            return False, None

        now = time.time()

        if not is_index_pointing or lm is None or len(lm) < 21:
            self._is_pushed = False
            self._locked_aim_pos = None
            return False, None

        # Relative depth metric:
        # MediaPipe: smaller/negative z is closer to camera.
        tip_z = float(lm[INDEX_TIP, 2])
        mcp_z = float(lm[INDEX_MCP, 2])
        wrist_z = float(lm[WRIST, 2])

        # Combined relative depth: tip relative to hand base
        current_z = (tip_z - mcp_z) * 0.7 + (tip_z - wrist_z) * 0.3

        curr_x = float(lm[INDEX_TIP, 0])
        curr_y = float(lm[INDEX_TIP, 1])

        # Initialize baseline on first frame
        if self._baseline_z is None:
            self._baseline_z = current_z
            self._prev_z = current_z
            self._prev_time = now
            return False, None

        # Forward penetration: how much closer to camera than resting baseline
        penetration = self._baseline_z - current_z

        # Compute instantaneous forward velocity (dz/dt)
        dt = max(1e-4, now - self._prev_time)
        velocity = (current_z - self._prev_z) / dt  # negative = moving towards camera

        self._prev_z = current_z
        self._prev_time = now

        # Update resting baseline slowly when not pushed
        if not self._is_pushed:
            # Slow adaptation (alpha = 0.04) so resting posture doesn't trigger false taps
            self._baseline_z = (self._baseline_z * 0.96) + (current_z * 0.04)

        # Check for tap trigger:
        time_since_last_tap = now - self._last_tap_time
        can_tap = (time_since_last_tap > self.cooldown) and not self._is_pushed

        # Forward push criteria:
        has_penetrated = penetration > self.penetration_threshold
        has_punched = (penetration > self.penetration_threshold * 0.6) and (velocity < self.velocity_threshold)

        tap_fired = False
        aim_pos = (curr_x, curr_y)

        if can_tap and (has_penetrated or has_punched):
            # Tap triggered!
            tap_fired = True
            self._is_pushed = True
            self._last_tap_time = now
            self._locked_aim_pos = (curr_x, curr_y)
            aim_pos = self._locked_aim_pos

            # Register visual ripple effect
            self._active_ripples.append({
                "pos": (curr_x, curr_y),
                "start_time": now,
                "duration": 0.45,
            })
            log.info("3D Depth Tap fired! Penetration: %.3f, Velocity: %.2f", penetration, velocity)

        # Check for retraction / release:
        elif self._is_pushed:
            if penetration < (self.penetration_threshold * 0.35) or velocity > 0.15:
                self._is_pushed = False
                self._locked_aim_pos = None

        # If currently in the active tap stroke, stabilize aim
        if self._is_pushed and self._locked_aim_pos is not None:
            aim_pos = self._locked_aim_pos

        return tap_fired, aim_pos

    def draw_ripples(self, frame_bgr: np.ndarray) -> None:
        """Render expanding futuristic holographic ripple rings on the camera frame."""
        if not self._active_ripples:
            return

        now = time.time()
        h, w = frame_bgr.shape[:2]
        remaining = []

        for rip in self._active_ripples:
            elapsed = now - rip["start_time"]
            dur = rip["duration"]
            if elapsed < dur:
                progress = elapsed / dur
                radius = int(12 + progress * 35)
                alpha = 1.0 - progress

                px = int(rip["pos"][0] * w)
                py = int(rip["pos"][1] * h)

                # Outer glowing cyan ring
                cv2.circle(frame_bgr, (px, py), radius, (240, 240, 0), max(1, int(3 * alpha)), cv2.LINE_AA)
                # Inner green pulse ring
                if radius > 14:
                    cv2.circle(frame_bgr, (px, py), int(radius * 0.6), (0, 255, 120), 1, cv2.LINE_AA)
                # Center point
                cv2.circle(frame_bgr, (px, py), 4, (255, 255, 255), -1, cv2.LINE_AA)

                # Floating "AIR TAP" label
                cv2.putText(
                    frame_bgr,
                    "AIR TAP",
                    (px - 28, max(20, py - radius - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 240, 255),
                    1,
                    cv2.LINE_AA,
                )

                remaining.append(rip)

        self._active_ripples = remaining
