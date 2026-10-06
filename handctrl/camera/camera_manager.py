"""
HandCtrl — Webcam manager.

Handles camera lifecycle: open, read frames, release.
Runs capture in a background thread so the UI is never blocked.
"""

from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from handctrl.config import (
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FPS,
    DEFAULT_CAMERA_INDEX,
)
from handctrl.utils.logger import get_logger

log = get_logger()


class CameraManager:
    """Thread-safe webcam capture manager."""

    def __init__(self, camera_index: int = DEFAULT_CAMERA_INDEX) -> None:
        self._camera_index = camera_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._fps: float = 0.0

    # ------------------------------------------------------------------
    # Properties & Utilities
    # ------------------------------------------------------------------
    @property
    def camera_index(self) -> int:
        return self._camera_index

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def list_available_cameras(max_tested: int = 4) -> list[int]:
        """Probe system camera indices [0..max_tested-1] and return available ones."""
        available = []
        for i in range(max_tested):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    available.append(i)
                    cap.release()
            except Exception:
                pass
        if not available:
            available = [0]
        return available

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open(self, camera_index: Optional[int] = None) -> bool:
        """Open the camera. Returns True on success."""
        idx = camera_index if camera_index is not None else self._camera_index
        self._camera_index = idx

        try:
            self._cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            self._cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

            if not self._cap.isOpened():
                log.error("Failed to open camera %d", idx)
                self._connected = False
                return False

            self._connected = True
            log.info("Camera %d opened (%dx%d)", idx, CAMERA_WIDTH, CAMERA_HEIGHT)
            return True
        except Exception as exc:
            log.error("Camera open error: %s", exc)
            self._connected = False
            return False

    def start(self) -> None:
        """Start background frame capture thread."""
        if self._running:
            return
        if not self._connected:
            if not self.open():
                return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        log.info("Camera capture thread started")

    def stop(self) -> None:
        """Stop capture and release the camera."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        self._connected = False
        log.info("Camera released")

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------
    def get_frame(self) -> Optional[np.ndarray]:
        """Return the latest frame (BGR, or None if unavailable)."""
        with self._lock:
            if self._frame is not None:
                return self._frame.copy()
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _capture_loop(self) -> None:
        """Continuously grab frames in the background."""
        prev_time = time.perf_counter()

        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self._connected = False
                log.warning("Camera disconnected")
                time.sleep(0.5)
                # Try to reconnect
                if not self.open():
                    continue

            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._connected = False
                log.warning("Failed to read frame")
                time.sleep(0.1)
                continue

            self._connected = True

            # Flip horizontally for mirror-view
            frame = cv2.flip(frame, 1)

            with self._lock:
                self._frame = frame

            # FPS calculation
            now = time.perf_counter()
            dt = now - prev_time
            self._fps = 1.0 / dt if dt > 0 else 0.0
            prev_time = now

            # Small sleep to avoid maxing out the CPU
            time.sleep(0.001)
