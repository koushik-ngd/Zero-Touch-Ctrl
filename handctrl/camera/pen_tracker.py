"""
Zero-Touch-Ctrl — Optical & AI Pen Tracker.

Enables using any physical pen, stylus, marker, or pencil to control the cursor.
Supports:
1. Optical Pen Tip Tracking:
   - High-speed HSV color segmentation with contour tip detection
   - Pre-configured color presets (Blue, Red, Green, Yellow, Orange)
   - Click-to-lock color sampling (click on any pen in the video preview to lock onto it)
2. AI Hand "Writing Grip" (Tripod Grip):
   - Detects natural pen-holding hand posture via MediaPipe landmarks
   - Projects virtual pen tip forward from finger grip
3. Automatic Fallback:
   - Prioritizes physical optical pen tip; seamlessly falls back to hand grip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
import cv2
import numpy as np

from handctrl.camera.hand_tracker import HandData
from handctrl.gestures.gesture_utils import (
    THUMB_TIP,
    INDEX_TIP,
    INDEX_DIP,
    INDEX_PIP,
    INDEX_MCP,
    MIDDLE_TIP,
    distance_2d,
    get_finger_states,
)
from handctrl.utils.logger import get_logger

log = get_logger()


@dataclass
class PenResult:
    """Detection output for pen tracking."""

    detected: bool
    tip_norm: Optional[Tuple[float, float]] = None  # (x, y) normalized 0..1
    pixel_pos: Optional[Tuple[int, int]] = None  # (x, y) pixels
    source: str = "none"  # "optical" or "grip"
    is_clicking: bool = False
    confidence: float = 0.0
    status_text: str = "No pen detected"


# Pre-configured HSV ranges for common pens: (lower_hsv, upper_hsv)
COLOR_PRESETS: Dict[str, List[Tuple[np.ndarray, np.ndarray]]] = {
    "BLUE": [
        (np.array([95, 80, 50], dtype=np.uint8), np.array([135, 255, 255], dtype=np.uint8)),
    ],
    "RED": [
        # Red wraps around HSV 0/180
        (np.array([0, 100, 70], dtype=np.uint8), np.array([10, 255, 255], dtype=np.uint8)),
        (np.array([168, 100, 70], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8)),
    ],
    "GREEN": [
        (np.array([35, 70, 50], dtype=np.uint8), np.array([88, 255, 255], dtype=np.uint8)),
    ],
    "YELLOW": [
        (np.array([18, 90, 90], dtype=np.uint8), np.array([35, 255, 255], dtype=np.uint8)),
    ],
    "ORANGE": [
        (np.array([10, 110, 80], dtype=np.uint8), np.array([22, 255, 255], dtype=np.uint8)),
    ],
}


class PenTracker:
    """Tracks physical pens (optical tip) or hand writing grips."""

    def __init__(self) -> None:
        self._active_color_name: str = "CUSTOM"  # Default to custom sampled or preset
        self._custom_hsv: Optional[Tuple[int, int, int]] = None
        self._custom_ranges: List[Tuple[np.ndarray, np.ndarray]] = []

        # Default fallback to blue if no sample yet
        self.set_preset("BLUE")

        # Click detection via tap / velocity tracking
        self._prev_y: Optional[float] = None
        self._prev_time: float = 0.0
        self._tap_cooldown: float = 0.0

    # ------------------------------------------------------------------
    # Color Calibration & Presets
    # ------------------------------------------------------------------
    def set_preset(self, preset_name: str) -> None:
        """Set active tracking color from presets."""
        name = preset_name.upper()
        if name in COLOR_PRESETS:
            self._active_color_name = name
            self._custom_ranges = COLOR_PRESETS[name]
            log.info("PenTracker color preset set to: %s", name)

    def sample_color_at_pixel(self, frame_bgr: np.ndarray, px: int, py: int) -> None:
        """
        Sample HSV color at (px, py) on the frame and set adaptive HSV bounds.
        Samples a 13x13 window around the click point to resist noise.
        """
        h, w = frame_bgr.shape[:2]
        px = max(6, min(w - 7, px))
        py = max(6, min(h - 7, py))

        roi = frame_bgr[py - 6 : py + 7, px - 6 : px + 7]
        roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Median HSV
        med_h = int(np.median(roi_hsv[:, :, 0]))
        med_s = int(np.median(roi_hsv[:, :, 1]))
        med_v = int(np.median(roi_hsv[:, :, 2]))

        self._custom_hsv = (med_h, med_s, med_v)
        self._active_color_name = "CUSTOM"

        # Adaptive range
        h_tol = 15
        s_tol = 60
        v_tol = 70

        if med_h - h_tol < 0:
            # Wrap around 0
            r1_lower = np.array([0, max(30, med_s - s_tol), max(30, med_v - v_tol)], dtype=np.uint8)
            r1_upper = np.array([med_h + h_tol, 255, 255], dtype=np.uint8)
            r2_lower = np.array([180 + (med_h - h_tol), max(30, med_s - s_tol), max(30, med_v - v_tol)], dtype=np.uint8)
            r2_upper = np.array([180, 255, 255], dtype=np.uint8)
            self._custom_ranges = [(r1_lower, r1_upper), (r2_lower, r2_upper)]
        elif med_h + h_tol > 180:
            # Wrap around 180
            r1_lower = np.array([med_h - h_tol, max(30, med_s - s_tol), max(30, med_v - v_tol)], dtype=np.uint8)
            r1_upper = np.array([180, 255, 255], dtype=np.uint8)
            r2_lower = np.array([0, max(30, med_s - s_tol), max(30, med_v - v_tol)], dtype=np.uint8)
            r2_upper = np.array([(med_h + h_tol) - 180, 255, 255], dtype=np.uint8)
            self._custom_ranges = [(r1_lower, r1_upper), (r2_lower, r2_upper)]
        else:
            lower = np.array([med_h - h_tol, max(30, med_s - s_tol), max(30, med_v - v_tol)], dtype=np.uint8)
            upper = np.array([med_h + h_tol, min(255, med_s + s_tol + 40), 255], dtype=np.uint8)
            self._custom_ranges = [(lower, upper)]

        log.info("PenTracker locked to custom color: H=%d S=%d V=%d", med_h, med_s, med_v)

    @property
    def active_color_name(self) -> str:
        return self._active_color_name

    # ------------------------------------------------------------------
    # Main Processing
    # ------------------------------------------------------------------
    def process(
        self,
        frame_bgr: np.ndarray,
        hand: Optional[HandData] = None,
        draw: bool = True,
    ) -> Tuple[PenResult, np.ndarray]:
        """
        Detect pen tip in the frame via optical color tracking or hand grip.

        Returns:
            (PenResult, annotated_frame)
        """
        annotated = frame_bgr.copy() if draw else frame_bgr
        h, w = frame_bgr.shape[:2]

        # 1. Try Optical Pen Tip Tracking first
        optical_res = self._track_optical_pen(frame_bgr, annotated, draw)
        if optical_res.detected:
            return optical_res, annotated

        # 2. Try Hand Pen/Writing Grip fallback if hand data is present
        if hand is not None:
            grip_res = self._track_hand_grip(hand, annotated, w, h, draw)
            if grip_res.detected:
                return grip_res, annotated

        # 3. Nothing detected
        return PenResult(detected=False, status_text="Searching for pen..."), annotated

    # ------------------------------------------------------------------
    # Optical Color Tracker
    # ------------------------------------------------------------------
    def _track_optical_pen(
        self,
        frame_bgr: np.ndarray,
        annotated: np.ndarray,
        draw: bool,
    ) -> PenResult:
        """Segment pen tip using HSV mask and find the extreme tip coordinate."""
        if not self._custom_ranges:
            return PenResult(detected=False)

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

        for lower, upper in self._custom_ranges:
            part_mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.bitwise_or(mask, part_mask)

        # Morphological filtering to clean noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return PenResult(detected=False)

        # Filter by contour area (ignore tiny specks or huge screen-wide blobs)
        min_area = 40
        max_area = frame_bgr.shape[0] * frame_bgr.shape[1] * 0.25

        valid_contours = [c for c in contours if min_area <= cv2.contourArea(c) <= max_area]
        if not valid_contours:
            return PenResult(detected=False)

        # Select largest valid contour (the pen tip or cap)
        best_c = max(valid_contours, key=cv2.contourArea)
        area = cv2.contourArea(best_c)

        # Find the extreme top point of the pen tip (lowest y)
        topmost = tuple(best_c[best_c[:, :, 1].argmin()][0])
        tip_x, tip_y = int(topmost[0]), int(topmost[1])

        h, w = frame_bgr.shape[:2]
        norm_x = float(tip_x / w)
        norm_y = float(tip_y / h)

        # Draw optical pen reticle
        if draw:
            self._draw_pen_reticle(annotated, tip_x, tip_y, label=f"PEN ({self._active_color_name})")

        return PenResult(
            detected=True,
            tip_norm=(norm_x, norm_y),
            pixel_pos=(tip_x, tip_y),
            source="optical",
            confidence=min(1.0, area / 1500.0),
            status_text=f"Locked ({self._active_color_name} Pen)",
        )

    # ------------------------------------------------------------------
    # AI Hand Pen/Writing Grip Tracker
    # ------------------------------------------------------------------
    def _track_hand_grip(
        self,
        hand: HandData,
        annotated: np.ndarray,
        w: int,
        h: int,
        draw: bool,
    ) -> PenResult:
        """
        Detect if hand is holding a pen in a natural tripod writing grip.
        Tripod Grip Criteria:
        - Thumb tip and Index tip are close together (pinching/holding).
        - Ring and pinky fingers are folded inward.
        - Pen tip extends along the index finger axis.
        """
        lm = hand.landmark_array
        pdist = distance_2d(lm, THUMB_TIP, INDEX_TIP)
        states = get_finger_states(lm)

        # In a pen grip: thumb and index are pinched close (< 0.09)
        # Ring and pinky are curled inward
        is_pinching = pdist < 0.09
        ring_pinky_folded = not states["ring"] and not states["pinky"]

        if not (is_pinching and ring_pinky_folded):
            return PenResult(detected=False)

        # Calculate projected pen tip:
        # Vector from Index MCP (5) through Index DIP (7) / TIP (8)
        # Extending 20% past index tip represents the physical pen tip protruding from hand
        idx_tip = lm[INDEX_TIP, :2]
        idx_dip = lm[INDEX_DIP, :2]

        dir_vec = idx_tip - idx_dip
        norm_len = np.linalg.norm(dir_vec)
        if norm_len > 1e-5:
            dir_unit = dir_vec / norm_len
            # Project forward by ~35% of finger segment length
            proj_tip = idx_tip + (dir_unit * 0.04)
        else:
            proj_tip = idx_tip

        proj_norm_x = float(np.clip(proj_tip[0], 0.0, 1.0))
        proj_norm_y = float(np.clip(proj_tip[1], 0.0, 1.0))

        tip_px = int(proj_norm_x * w)
        tip_py = int(proj_norm_y * h)

        is_clicking = pdist < 0.045
        label = "AIR PEN (CLICK)" if is_clicking else "AIR PEN (GRIP)"

        if draw:
            self._draw_pen_reticle(annotated, tip_px, tip_py, label=label)

        return PenResult(
            detected=True,
            tip_norm=(proj_norm_x, proj_norm_y),
            pixel_pos=(tip_px, tip_py),
            source="grip",
            is_clicking=is_clicking,
            confidence=hand.detection_confidence,
            status_text="Air Pen (Writing Grip)" if not is_clicking else "Air Pen (Down / Click)",
        )

    # ------------------------------------------------------------------
    # Visual HUD Overlay
    # ------------------------------------------------------------------
    def _draw_pen_reticle(self, frame: np.ndarray, x: int, y: int, label: str) -> None:
        """Draw a sci-fi laser crosshair and target reticle on the pen tip."""
        # Outer glow ring
        cv2.circle(frame, (x, y), 16, (0, 220, 255), 1, cv2.LINE_AA)
        # Inner solid ring
        cv2.circle(frame, (x, y), 7, (0, 255, 120), 2, cv2.LINE_AA)
        # Center dot
        cv2.circle(frame, (x, y), 2, (255, 255, 255), -1, cv2.LINE_AA)

        # Crosshairs
        cv2.line(frame, (x - 22, y), (x - 10, y), (0, 220, 255), 1, cv2.LINE_AA)
        cv2.line(frame, (x + 10, y), (x + 22, y), (0, 220, 255), 1, cv2.LINE_AA)
        cv2.line(frame, (x, y - 22), (x, y - 10), (0, 220, 255), 1, cv2.LINE_AA)
        cv2.line(frame, (x, y + 10), (x, y + 22), (0, 220, 255), 1, cv2.LINE_AA)

        # Badge pill
        text = label
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.4
        thick = 1
        (tw, th), _ = cv2.getTextSize(text, font, scale, thick)

        badge_x = max(10, x - tw // 2)
        badge_y = max(th + 14, y - 22)

        cv2.rectangle(
            frame,
            (badge_x - 4, badge_y - th - 4),
            (badge_x + tw + 4, badge_y + 4),
            (20, 20, 24),
            -1,
        )
        cv2.rectangle(
            frame,
            (badge_x - 4, badge_y - th - 4),
            (badge_x + tw + 4, badge_y + 4),
            (0, 220, 255),
            1,
        )
        cv2.putText(
            frame,
            text,
            (badge_x, badge_y),
            font,
            scale,
            (255, 255, 255),
            thick,
            cv2.LINE_AA,
        )
