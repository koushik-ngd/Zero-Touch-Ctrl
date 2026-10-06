"""
HandCtrl — Hand tracker using MediaPipe HandLandmarker (v1.0+ Tasks API).

Initialises MediaPipe once and processes frames to extract hand landmarks,
handedness, and confidence values.  Designed for single-hand tracking with
the code structure ready for future two-hand support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.hand_landmarker import (
    HandLandmarker,
    HandLandmarkerOptions,
    HandLandmarkerResult,
    HandLandmarksConnections,
)
from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
    VisionTaskRunningMode,
)
from mediapipe.tasks.python.vision.drawing_utils import draw_landmarks, DrawingSpec
from mediapipe.tasks.python.components.containers.landmark import NormalizedLandmark

from handctrl.config import (
    MP_MAX_HANDS,
    MP_MIN_DETECTION_CONFIDENCE,
    MP_MIN_TRACKING_CONFIDENCE,
)
from handctrl.utils.logger import get_logger

log = get_logger()

# Model path — bundled in the project
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"

# Drawing styles
_LANDMARK_SPEC = DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3)
_CONNECTION_SPEC = DrawingSpec(color=(255, 255, 255), thickness=1, circle_radius=1)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------
@dataclass
class HandData:
    """Processed data for a single detected hand."""

    landmarks: List[NormalizedLandmark]  # 21 NormalizedLandmark objects
    landmark_array: np.ndarray  # (21, 3) float32 — x, y, z normalised
    handedness: str  # "Left" or "Right"
    detection_confidence: float
    tracking_confidence: float  # min_tracking_confidence used


@dataclass
class TrackingResult:
    """Result of processing a single frame."""

    hands: List[HandData] = field(default_factory=list)
    annotated_frame: Optional[np.ndarray] = None

    @property
    def has_hand(self) -> bool:
        return len(self.hands) > 0

    @property
    def primary_hand(self) -> Optional[HandData]:
        """Return the first (primary) detected hand."""
        return self.hands[0] if self.hands else None


# ---------------------------------------------------------------------------
# HandTracker
# ---------------------------------------------------------------------------
class HandTracker:
    """Wraps MediaPipe HandLandmarker for efficient per-frame processing."""

    def __init__(
        self,
        max_num_hands: int = MP_MAX_HANDS,
        min_detection_confidence: float = MP_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = MP_MIN_TRACKING_CONFIDENCE,
    ) -> None:
        self._max_hands = max_num_hands
        self._det_conf = min_detection_confidence
        self._track_conf = min_tracking_confidence
        self._landmarker: Optional[HandLandmarker] = None
        self._initialised = False
        self._timestamp_ms: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialise(self) -> bool:
        """Create the HandLandmarker instance. Returns True on success."""
        if not MODEL_PATH.exists():
            log.error("Hand landmarker model not found at %s", MODEL_PATH)
            return False

        try:
            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=VisionTaskRunningMode.VIDEO,
                num_hands=self._max_hands,
                min_hand_detection_confidence=self._det_conf,
                min_hand_presence_confidence=self._det_conf,
                min_tracking_confidence=self._track_conf,
            )
            self._landmarker = HandLandmarker.create_from_options(options)
            self._initialised = True
            self._timestamp_ms = 0
            log.info(
                "HandLandmarker initialised (max_hands=%d, det=%.2f, track=%.2f)",
                self._max_hands,
                self._det_conf,
                self._track_conf,
            )
            return True
        except Exception as exc:
            log.error("HandLandmarker initialisation failed: %s", exc)
            self._initialised = False
            return False

    def release(self) -> None:
        """Release MediaPipe resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
        self._initialised = False
        log.info("HandLandmarker released")

    @property
    def is_initialised(self) -> bool:
        return self._initialised

    # ------------------------------------------------------------------
    # Update confidence thresholds at runtime (from settings UI)
    # ------------------------------------------------------------------
    def update_confidence(
        self,
        detection: Optional[float] = None,
        tracking: Optional[float] = None,
    ) -> None:
        """Re-create the HandLandmarker instance with new confidence values."""
        if detection is not None:
            self._det_conf = detection
        if tracking is not None:
            self._track_conf = tracking
        if self._initialised:
            self.release()
            self.initialise()

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------
    def process(self, frame_bgr: np.ndarray, draw: bool = True) -> TrackingResult:
        """
        Process a BGR frame and return tracking results.

        Uses VIDEO running mode: frames must have increasing timestamps.

        Args:
            frame_bgr: Input image in BGR colour order.
            draw: If True, annotate the frame with landmarks.

        Returns:
            TrackingResult with hand data and optionally annotated frame.
        """
        result = TrackingResult()

        if not self._initialised or self._landmarker is None:
            result.annotated_frame = frame_bgr
            return result

        # Convert BGR → RGB and wrap in MediaPipe Image
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # Strictly increasing timestamps
        self._timestamp_ms += 33  # ~30 fps

        try:
            mp_result: HandLandmarkerResult = self._landmarker.detect_for_video(
                mp_image, self._timestamp_ms
            )
        except Exception as exc:
            log.warning("HandLandmarker detection error: %s", exc)
            result.annotated_frame = frame_bgr
            return result

        annotated = frame_bgr.copy() if draw else frame_bgr

        if mp_result.hand_landmarks and mp_result.handedness:
            for hand_lms, hand_cls in zip(
                mp_result.hand_landmarks,
                mp_result.handedness,
            ):
                # Extract classification
                handedness_label = hand_cls[0].category_name  # "Left" / "Right"
                det_conf = hand_cls[0].score

                # Build numpy array (21, 3)
                lm_array = np.array(
                    [(lm.x, lm.y, lm.z) for lm in hand_lms],
                    dtype=np.float32,
                )

                hand = HandData(
                    landmarks=hand_lms,
                    landmark_array=lm_array,
                    handedness=handedness_label,
                    detection_confidence=det_conf,
                    tracking_confidence=self._track_conf,
                )
                result.hands.append(hand)

                # Draw skeleton
                if draw:
                    draw_landmarks(
                        annotated,
                        hand_lms,
                        HandLandmarksConnections.HAND_CONNECTIONS,
                        landmark_drawing_spec=_LANDMARK_SPEC,
                        connection_drawing_spec=_CONNECTION_SPEC,
                    )

        result.annotated_frame = annotated
        return result
