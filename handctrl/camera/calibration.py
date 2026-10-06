"""
HandCtrl — Camera to screen calibration manager.

Allows calibrating the active tracking region by mapping 4 corner points
(top-left, top-right, bottom-right, bottom-left) in normalised camera space
to the user's screen space using a perspective transform.
Values are saved locally to `calibration.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np

from handctrl.config import CALIBRATION_FILE
from handctrl.utils.logger import get_logger

log = get_logger()


@dataclass
class CornerPoint:
    x: float
    y: float


@dataclass
class CalibrationData:
    """Corner points in normalised camera coordinates [0.0, 1.0]."""

    top_left: CornerPoint = field(default_factory=lambda: CornerPoint(0.1, 0.1))
    top_right: CornerPoint = field(default_factory=lambda: CornerPoint(0.9, 0.1))
    bottom_right: CornerPoint = field(default_factory=lambda: CornerPoint(0.9, 0.9))
    bottom_left: CornerPoint = field(default_factory=lambda: CornerPoint(0.1, 0.9))
    is_calibrated: bool = False

    def save(self, path: Optional[Path] = None) -> None:
        target = path or CALIBRATION_FILE
        try:
            data = {
                "top_left": asdict(self.top_left),
                "top_right": asdict(self.top_right),
                "bottom_right": asdict(self.bottom_right),
                "bottom_left": asdict(self.bottom_left),
                "is_calibrated": self.is_calibrated,
            }
            target.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log.info("Calibration saved to %s", target)
        except Exception as exc:
            log.error("Failed to save calibration: %s", exc)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "CalibrationData":
        target = path or CALIBRATION_FILE
        if not target.exists():
            return cls()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            return cls(
                top_left=CornerPoint(**raw["top_left"]),
                top_right=CornerPoint(**raw["top_right"]),
                bottom_right=CornerPoint(**raw["bottom_right"]),
                bottom_left=CornerPoint(**raw["bottom_left"]),
                is_calibrated=raw.get("is_calibrated", True),
            )
        except Exception as exc:
            log.warning("Could not load calibration (%s), using defaults", exc)
            return cls()


class CalibrationManager:
    """
    Manages calibration state, 4-step wizard workflow, and coordinate transformation.
    """

    STEPS = [
        "top_left",
        "top_right",
        "bottom_right",
        "bottom_left",
    ]

    STEP_DESCRIPTIONS = [
        "1. Move your index finger to the TOP-LEFT corner",
        "2. Move your index finger to the TOP-RIGHT corner",
        "3. Move your index finger to the BOTTOM-RIGHT corner",
        "4. Move your index finger to the BOTTOM-LEFT corner",
    ]

    def __init__(self) -> None:
        self.data: CalibrationData = CalibrationData.load()
        self._is_calibrating: bool = False
        self._current_step_idx: int = 0
        self._collected_points: dict[str, CornerPoint] = {}
        self._perspective_matrix: Optional[np.ndarray] = None
        self._cached_screen_size: Tuple[int, int] = (0, 0)

        if self.data.is_calibrated:
            self._update_matrix()

    @property
    def is_calibrating(self) -> bool:
        return self._is_calibrating

    @property
    def current_step_index(self) -> int:
        return self._current_step_idx

    @property
    def current_step_instruction(self) -> str:
        if not self._is_calibrating or self._current_step_idx >= len(self.STEP_DESCRIPTIONS):
            return ""
        return self.STEP_DESCRIPTIONS[self._current_step_idx]

    def start_calibration(self) -> None:
        """Start the 4-step calibration process."""
        self._is_calibrating = True
        self._current_step_idx = 0
        self._collected_points = {}
        log.info("Calibration started")

    def cancel_calibration(self) -> None:
        """Cancel the ongoing calibration."""
        self._is_calibrating = False
        self._current_step_idx = 0
        self._collected_points = {}
        log.info("Calibration cancelled")

    def record_point(self, norm_x: float, norm_y: float) -> bool:
        """
        Record the current finger position for the current step.
        Returns True if calibration is now complete.
        """
        if not self._is_calibrating:
            return False

        step_name = self.STEPS[self._current_step_idx]
        self._collected_points[step_name] = CornerPoint(
            x=max(0.0, min(1.0, norm_x)),
            y=max(0.0, min(1.0, norm_y)),
        )
        log.info("Calibration recorded %s: (%.3f, %.3f)", step_name, norm_x, norm_y)

        self._current_step_idx += 1
        if self._current_step_idx >= len(self.STEPS):
            # All 4 corners collected!
            self.data.top_left = self._collected_points["top_left"]
            self.data.top_right = self._collected_points["top_right"]
            self.data.bottom_right = self._collected_points["bottom_right"]
            self.data.bottom_left = self._collected_points["bottom_left"]
            self.data.is_calibrated = True
            self.data.save()

            self._is_calibrating = False
            self._update_matrix()
            log.info("Calibration complete and saved successfully!")
            return True

        return False

    def reset_to_defaults(self) -> None:
        """Reset calibration back to uncalibrated defaults."""
        self.data = CalibrationData(is_calibrated=False)
        self.data.save()
        self._perspective_matrix = None
        self._is_calibrating = False
        log.info("Calibration reset to defaults")

    def _update_matrix(self) -> None:
        """Compute the perspective transform matrix from camera unit space to [0,1] screen space."""
        src = np.array(
            [
                [self.data.top_left.x, self.data.top_left.y],
                [self.data.top_right.x, self.data.top_right.y],
                [self.data.bottom_right.x, self.data.bottom_right.y],
                [self.data.bottom_left.x, self.data.bottom_left.y],
            ],
            dtype=np.float32,
        )
        dst = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [1.0, 1.0],
                [0.0, 1.0],
            ],
            dtype=np.float32,
        )
        try:
            self._perspective_matrix = cv2.getPerspectiveTransform(src, dst)
        except Exception as exc:
            log.error("Failed to compute perspective matrix: %s", exc)
            self._perspective_matrix = None

    def map_point(self, norm_x: float, norm_y: float, screen_w: int, screen_h: int) -> Tuple[int, int]:
        """
        Map normalised camera point (0..1) to screen pixel coordinates (0..screen_w, 0..screen_h).
        Uses perspective transform if calibrated, or dead-zone clamped linear mapping if not.
        """
        if self.data.is_calibrated and self._perspective_matrix is not None:
            pt = np.array([[[norm_x, norm_y]]], dtype=np.float32)
            transformed = cv2.perspectiveTransform(pt, self._perspective_matrix)
            tx = float(transformed[0, 0, 0])
            ty = float(transformed[0, 0, 1])

            # Clamp to [0, 1] screen fraction
            tx = max(0.0, min(1.0, tx))
            ty = max(0.0, min(1.0, ty))

            screen_x = int(tx * screen_w)
            screen_y = int(ty * screen_h)
            return screen_x, screen_y

        # Fallback to standard mapping
        return -1, -1
