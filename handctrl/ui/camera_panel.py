"""
HandCtrl — Camera preview panel for the Tkinter UI.

Displays the live webcam feed with hand landmarks, gesture info,
and calibration targets inside a Tkinter Label widget.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional, Tuple, Callable

import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw


class CameraPanel:
    """Tkinter widget that displays the live camera feed with modern dark borders."""

    def __init__(self, parent: tk.Widget, width: int = 560, height: int = 420) -> None:
        self._width = width
        self._height = height

        self._frame_container = tk.Frame(
            parent,
            bg="#18181b",
            highlightbackground="#27272a",
            highlightthickness=1,
            bd=0,
        )
        self._frame_container.pack(fill="both", expand=True)

        self._label = tk.Label(
            self._frame_container,
            bg="#09090b",
            width=width,
            height=height,
            bd=0,
        )
        self._label.pack(fill="both", expand=True, padx=2, pady=2)

        self._photo: Optional[ImageTk.PhotoImage] = None
        self._placeholder: Optional[ImageTk.PhotoImage] = None
        self._on_click_callback = None
        self._last_frame_shape = None
        self._label.bind("<Button-1>", self._on_label_click)
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        """Display an elegant cyber studio viewfinder placeholder when camera is stopped."""
        w, h = self._width, self._height
        img = Image.new("RGB", (w, h), color=(10, 11, 15))
        draw = ImageDraw.Draw(img)

        # Subtle background dot grid
        for gx in range(40, w, 55):
            for gy in range(40, h, 55):
                draw.point((gx, gy), fill=(22, 25, 35))

        # Viewfinder corner reticles
        c_len = 22
        pad = 18
        c_color = (39, 45, 60)
        # Top-left
        draw.line([(pad, pad), (pad + c_len, pad)], fill=c_color, width=2)
        draw.line([(pad, pad), (pad, pad + c_len)], fill=c_color, width=2)
        # Top-right
        draw.line([(w - pad, pad), (w - pad - c_len, pad)], fill=c_color, width=2)
        draw.line([(w - pad, pad), (w - pad, pad + c_len)], fill=c_color, width=2)
        # Bottom-left
        draw.line([(pad, h - pad), (pad + c_len, h - pad)], fill=c_color, width=2)
        draw.line([(pad, h - pad), (pad, h - pad - c_len)], fill=c_color, width=2)
        # Bottom-right
        draw.line([(w - pad, h - pad), (w - pad - c_len, h - pad)], fill=c_color, width=2)
        draw.line([(w - pad, h - pad), (w - pad, pad + c_len if False else h - pad - c_len)], fill=c_color, width=2)

        # Center target aperture rings
        cx, cy = w // 2, h // 2
        draw.ellipse([cx - 38, cy - 38, cx + 38, cy + 38], outline=(25, 30, 42), width=1)
        draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], outline=(56, 189, 248), width=2)
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(56, 189, 248))

        # Crosshair lines
        draw.line([(cx - 50, cy), (cx - 28, cy)], fill=(56, 189, 248), width=1)
        draw.line([(cx + 28, cy), (cx + 50, cy)], fill=(56, 189, 248), width=1)
        draw.line([(cx, cy - 50), (cx, cy - 28)], fill=(56, 189, 248), width=1)
        draw.line([(cx, cy + 28), (cx, cy + 50)], fill=(56, 189, 248), width=1)

        # Text labels
        draw.text((cx, cy + 54), "VISION STUDIO STANDBY", fill=(244, 244, 245), anchor="mm")
        draw.text((cx, cy + 74), "Click  '▶ START WEBCAM'  below to activate tracking", fill=(113, 113, 122), anchor="mm")

        # Technical metadata badges
        draw.text((pad + 4, h - pad - 6), "FEED: OFFLINE", fill=(63, 75, 96), anchor="ls")
        draw.text((w - pad - 4, h - pad - 6), "640x480 • 30 FPS", fill=(63, 75, 96), anchor="rs")

        self._placeholder = ImageTk.PhotoImage(image=img)
        self._label.configure(image=self._placeholder)

    def bind_click(self, callback: Optional[Callable[[int, int], None]]) -> None:
        """Bind a callback invoked with (frame_x, frame_y) when clicking the preview."""
        self._on_click_callback = callback

    def _on_label_click(self, event: tk.Event) -> None:
        if self._on_click_callback and self._last_frame_shape:
            fh, fw = self._last_frame_shape[:2]
            scale_x = fw / self._width
            scale_y = fh / self._height
            fx = int(event.x * scale_x)
            fy = int(event.y * scale_y)
            self._on_click_callback(fx, fy)

    def reset_placeholder(self) -> None:
        self._show_placeholder()

    def update_frame(
        self,
        frame_bgr: Optional[np.ndarray],
        calibration_step: Optional[str] = None,
        calibration_instruction: Optional[str] = None,
    ) -> None:
        """
        Update the displayed frame.

        Args:
            frame_bgr: The captured BGR image.
            calibration_step: Name of active corner ("top_left", etc.) if calibrating.
            calibration_instruction: Text instruction to display on overlay.
        """
        if frame_bgr is None:
            return

        self._last_frame_shape = frame_bgr.shape
        frame = frame_bgr.copy()

        # If calibrating, draw calibration HUD on frame
        if calibration_step and calibration_instruction:
            self._draw_calibration_hud(frame, calibration_step, calibration_instruction)

        # Resize to panel dimensions
        h, w = frame.shape[:2]
        if w != self._width or h != self._height:
            frame = cv2.resize(frame, (self._width, self._height), interpolation=cv2.INTER_LINEAR)

        # Convert BGR -> RGB -> PIL -> Tk PhotoImage
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        self._photo = ImageTk.PhotoImage(image=img)
        self._label.configure(image=self._photo)

    def _draw_calibration_hud(
        self, frame: np.ndarray, step_name: str, instruction: str
    ) -> None:
        """Draw interactive crosshairs and target box for calibration."""
        h, w = frame.shape[:2]

        # Draw semi-transparent header banner
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 64), (18, 18, 22), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Instruction text
        cv2.putText(
            frame,
            "CALIBRATION IN PROGRESS",
            (16, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 215, 255),
            2,
        )
        cv2.putText(
            frame,
            instruction,
            (16, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
        )

        # Draw target corner box
        box_size = 60
        corner_coords = {
            "top_left": (30, 80),
            "top_right": (w - 30 - box_size, 80),
            "bottom_right": (w - 30 - box_size, h - 30 - box_size),
            "bottom_left": (30, h - 30 - box_size),
        }

        if step_name in corner_coords:
            cx, cy = corner_coords[step_name]
            cv2.rectangle(
                frame,
                (cx, cy),
                (cx + box_size, cy + box_size),
                (0, 255, 128),
                2,
            )
            # Crosshair inside target box
            center_x = cx + box_size // 2
            center_y = cy + box_size // 2
            cv2.drawMarker(
                frame,
                (center_x, center_y),
                (0, 255, 128),
                cv2.MARKER_CROSS,
                20,
                2,
            )
