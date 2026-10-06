"""
HandCtrl — Settings panel for the desktop UI.

Clean, Linear-inspired dark settings controls including:
- Camera selection dropdown
- Precision sliders with numerical feedback
- Gesture feature enable/disable toggles
- Calibration controls
- Local privacy assurance
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List

from handctrl.config import Settings
from handctrl.camera.calibration import CalibrationManager


# ---------------------------------------------------------------------------
# Theme Palette (Zinc / Dark Modern)
# ---------------------------------------------------------------------------
BG_DARK = "#0f0f11"
SURFACE = "#18181b"
BORDER = "#27272a"
FG_PRIMARY = "#f4f4f5"
FG_SECONDARY = "#a1a1aa"
FG_MUTED = "#71717a"
ACCENT_BLUE = "#3b82f6"
EMERALD = "#10b981"
RED_ACCENT = "#ef4444"


class SettingsPanel:
    """Settings UI with camera picker, sliders, feature toggles, and calibration."""

    def __init__(
        self,
        parent: tk.Widget,
        settings: Settings,
        calibration: CalibrationManager,
        available_cameras: List[int],
        on_change: Optional[Callable[[], None]] = None,
        on_camera_select: Optional[Callable[[int], None]] = None,
        on_start_calibration: Optional[Callable[[], None]] = None,
        on_reset_calibration: Optional[Callable[[], None]] = None,
    ) -> None:
        self._settings = settings
        self._calibration = calibration
        self._available_cameras = available_cameras or [0]
        self._on_change = on_change
        self._on_camera_select = on_camera_select
        self._on_start_calibration = on_start_calibration
        self._on_reset_calibration = on_reset_calibration

        # Scrollable container or packed frame
        self._frame = tk.Frame(parent, bg=SURFACE, bd=0)
        self._frame.pack(fill="both", expand=True)

        self._build()

    def _build(self) -> None:
        s = self._settings

        # Canvas + Scrollbar for compact scrolling inside the settings card
        canvas = tk.Canvas(self._frame, bg=SURFACE, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(self._frame, orient="vertical", command=canvas.yview, bg=SURFACE)
        scrollable_frame = tk.Frame(canvas, bg=SURFACE, bd=0)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=360)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel support for scrolling settings
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True, padx=(4, 0))
        scrollbar.pack(side="right", fill="y")

        content = scrollable_frame

        # ===================================================================
        # SECTION: CAMERA SELECTION
        # ===================================================================
        self._add_heading(content, "CAMERA INPUT")

        cam_row = tk.Frame(content, bg=SURFACE)
        cam_row.pack(fill="x", padx=12, pady=(0, 10))

        cam_lbl = tk.Label(
            cam_row, text="Device", bg=SURFACE, fg=FG_SECONDARY, font=("Segoe UI", 9)
        )
        cam_lbl.pack(side="left")

        camera_options = [f"Camera {idx}" for idx in self._available_cameras]
        current_cam_text = f"Camera {s.camera_index}"
        if current_cam_text not in camera_options:
            camera_options.append(current_cam_text)

        self._cam_var = tk.StringVar(value=current_cam_text)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground="#27272a",
            background="#27272a",
            foreground="#f4f4f5",
            arrowcolor="#f4f4f5",
            bordercolor="#3f3f46",
            lightcolor="#27272a",
            darkcolor="#27272a",
        )

        self._cam_combo = ttk.Combobox(
            cam_row,
            textvariable=self._cam_var,
            values=camera_options,
            state="readonly",
            style="Dark.TCombobox",
            width=16,
            font=("Segoe UI", 9),
        )
        self._cam_combo.pack(side="right")
        self._cam_combo.bind("<<ComboboxSelected>>", self._on_camera_picked)

        # ===================================================================
        # SECTION: PRECISION TUNING SLIDERS
        # ===================================================================
        self._add_heading(content, "SENSITIVITY & TUNING")

        self._smoothing_var, self._smoothing_val_lbl = self._add_slider(
            content, "Cursor smoothing", 0.0, 0.9, s.cursor_smoothing, 0.05, self._on_smoothing
        )
        self._pinch_var, self._pinch_val_lbl = self._add_slider(
            content, "Pinch threshold", 0.02, 0.10, s.pinch_threshold, 0.005, self._on_pinch
        )
        self._scroll_var, self._scroll_val_lbl = self._add_slider(
            content, "Scroll sensitivity", 1.0, 20.0, s.scroll_sensitivity, 0.5, self._on_scroll
        )
        self._swipe_var, self._swipe_val_lbl = self._add_slider(
            content, "Swipe sensitivity", 0.05, 0.35, s.swipe_sensitivity, 0.02, self._on_swipe
        )
        self._det_conf_var, self._det_val_lbl = self._add_slider(
            content, "Min detection confidence", 0.40, 0.95, s.detection_confidence, 0.05, self._on_det_conf
        )

        # ===================================================================
        # SECTION: GESTURE TOGGLES
        # ===================================================================
        self._add_heading(content, "GESTURE TOGGLES")

        self._toggle_cursor_var = self._add_toggle(
            content, "Cursor movement (Index finger)", s.enable_cursor, self._on_toggle_cursor
        )
        self._toggle_click_var = self._add_toggle(
            content, "Left click (Pinch)", s.enable_click, self._on_toggle_click
        )
        self._toggle_drag_var = self._add_toggle(
            content, "Mouse drag (Pinch + move)", s.enable_drag, self._on_toggle_drag
        )
        self._toggle_scroll_var = self._add_toggle(
            content, "Scrolling (Two fingers)", s.enable_scroll, self._on_toggle_scroll
        )
        self._toggle_thumbs_var = self._add_toggle(
            content, "Play/Pause (Thumbs up)", s.enable_thumbs_up, self._on_toggle_thumbs
        )
        self._toggle_swipe_var = self._add_toggle(
            content, "Next/Prev track (Swipe)", s.enable_swipe, self._on_toggle_swipe
        )
        self._toggle_pause_var = self._add_toggle(
            content, "Open palm pause", s.enable_palm_pause, self._on_toggle_pause
        )

        # ===================================================================
        # SECTION: CALIBRATION
        # ===================================================================
        self._add_heading(content, "SCREEN CALIBRATION")

        cal_box = tk.Frame(content, bg="#202024", highlightbackground=BORDER, highlightthickness=1)
        cal_box.pack(fill="x", padx=12, pady=(0, 10))

        cal_status_text = "Status: Calibrated" if self._calibration.data.is_calibrated else "Status: Default dead-zone"
        self._cal_status_lbl = tk.Label(
            cal_box,
            text=cal_status_text,
            bg="#202024",
            fg=EMERALD if self._calibration.data.is_calibrated else FG_SECONDARY,
            font=("Segoe UI", 9, "bold"),
        )
        self._cal_status_lbl.pack(anchor="w", padx=10, pady=(8, 4))

        cal_desc = tk.Label(
            cal_box,
            text="Map your camera boundary to your screen corners.",
            bg="#202024",
            fg=FG_MUTED,
            font=("Segoe UI", 8),
            justify="left",
        )
        cal_desc.pack(anchor="w", padx=10, pady=(0, 6))

        btn_row = tk.Frame(cal_box, bg="#202024")
        btn_row.pack(fill="x", padx=10, pady=(0, 8))

        self._cal_btn = tk.Button(
            btn_row,
            text="🎯 CALIBRATE",
            bg="#27272a",
            fg=FG_PRIMARY,
            activebackground="#3f3f46",
            activeforeground=FG_PRIMARY,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
            command=self._on_calibrate_click,
        )
        self._cal_btn.pack(side="left", padx=(0, 6))

        self._reset_cal_btn = tk.Button(
            btn_row,
            text="Reset",
            bg="#27272a",
            fg=FG_MUTED,
            activebackground="#3f3f46",
            activeforeground=FG_PRIMARY,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            command=self._on_reset_cal_click,
        )
        self._reset_cal_btn.pack(side="left")

        # ===================================================================
        # SECTION: PRIVACY
        # ===================================================================
        self._add_heading(content, "LOCAL PRIVACY")

        priv_box = tk.Frame(content, bg=SURFACE)
        priv_box.pack(fill="x", padx=12, pady=(0, 16))

        priv_label = tk.Label(
            priv_box,
            text="🔒 Camera processing happens locally on this device.\nHand tracking frames are not uploaded or stored.",
            bg=SURFACE,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
            justify="left",
        )
        priv_label.pack(anchor="w")

    # ===================================================================
    # Helper builders
    # ===================================================================
    def _add_heading(self, parent: tk.Widget, title: str) -> None:
        lbl = tk.Label(
            parent,
            text=title,
            bg=SURFACE,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        lbl.pack(anchor="w", padx=12, pady=(12, 6))

    def _add_slider(
        self,
        parent: tk.Widget,
        label: str,
        min_val: float,
        max_val: float,
        initial: float,
        resolution: float,
        callback: Callable,
    ) -> tuple[tk.DoubleVar, tk.Label]:
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=12, pady=3)

        top_line = tk.Frame(row, bg=SURFACE)
        top_line.pack(fill="x")

        lbl = tk.Label(top_line, text=label, bg=SURFACE, fg=FG_PRIMARY, font=("Segoe UI", 9))
        lbl.pack(side="left")

        val_lbl = tk.Label(
            top_line, text=f"{initial:.2f}", bg=SURFACE, fg=FG_SECONDARY, font=("Segoe UI", 8)
        )
        val_lbl.pack(side="right")

        var = tk.DoubleVar(value=initial)

        def _slider_cb(val: str) -> None:
            v = float(val)
            val_lbl.configure(text=f"{v:.2f}")
            callback(val)

        scale = tk.Scale(
            row,
            from_=min_val,
            to=max_val,
            orient="horizontal",
            resolution=resolution,
            variable=var,
            command=_slider_cb,
            bg=SURFACE,
            fg=FG_PRIMARY,
            troughcolor="#27272a",
            activebackground=ACCENT_BLUE,
            highlightthickness=0,
            showvalue=False,
            sliderrelief="flat",
            bd=0,
            length=330,
        )
        scale.pack(fill="x", pady=(2, 0))

        return var, val_lbl

    def _add_toggle(
        self, parent: tk.Widget, label: str, initial: bool, callback: Callable[[bool], None]
    ) -> tk.BooleanVar:
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=12, pady=2)

        var = tk.BooleanVar(value=initial)

        def _toggled():
            callback(var.get())

        cb = tk.Checkbutton(
            row,
            text=label,
            variable=var,
            command=_toggled,
            bg=SURFACE,
            fg=FG_PRIMARY,
            selectcolor="#27272a",
            activebackground=SURFACE,
            activeforeground=FG_PRIMARY,
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 9),
        )
        cb.pack(side="left")
        return var

    # ===================================================================
    # Callbacks
    # ===================================================================
    def _on_camera_picked(self, _event=None) -> None:
        picked = self._cam_var.get()
        # Parse index from "Camera X"
        try:
            idx = int(picked.split()[-1])
            self._settings.camera_index = idx
            self._fire_change()
            if self._on_camera_select:
                self._on_camera_select(idx)
        except Exception:
            pass

    def _on_smoothing(self, val: str) -> None:
        self._settings.cursor_smoothing = float(val)
        self._fire_change()

    def _on_pinch(self, val: str) -> None:
        self._settings.pinch_threshold = float(val)
        self._fire_change()

    def _on_scroll(self, val: str) -> None:
        self._settings.scroll_sensitivity = float(val)
        self._fire_change()

    def _on_swipe(self, val: str) -> None:
        self._settings.swipe_sensitivity = float(val)
        self._fire_change()

    def _on_det_conf(self, val: str) -> None:
        self._settings.detection_confidence = float(val)
        self._fire_change()

    def _on_toggle_cursor(self, state: bool) -> None:
        self._settings.enable_cursor = state
        self._fire_change()

    def _on_toggle_click(self, state: bool) -> None:
        self._settings.enable_click = state
        self._fire_change()

    def _on_toggle_drag(self, state: bool) -> None:
        self._settings.enable_drag = state
        self._fire_change()

    def _on_toggle_scroll(self, state: bool) -> None:
        self._settings.enable_scroll = state
        self._fire_change()

    def _on_toggle_thumbs(self, state: bool) -> None:
        self._settings.enable_thumbs_up = state
        self._fire_change()

    def _on_toggle_swipe(self, state: bool) -> None:
        self._settings.enable_swipe = state
        self._fire_change()

    def _on_toggle_pause(self, state: bool) -> None:
        self._settings.enable_palm_pause = state
        self._fire_change()

    def _on_calibrate_click(self) -> None:
        if self._on_start_calibration:
            self._on_start_calibration()

    def _on_reset_cal_click(self) -> None:
        if self._on_reset_calibration:
            self._on_reset_calibration()
        self.update_calibration_status()

    def update_calibration_status(self) -> None:
        """Refresh calibration status label."""
        if self._calibration.data.is_calibrated:
            self._cal_status_lbl.configure(text="Status: Calibrated", fg=EMERALD)
        else:
            self._cal_status_lbl.configure(text="Status: Default dead-zone", fg=FG_SECONDARY)

    def _fire_change(self) -> None:
        self._settings.save()
        if self._on_change:
            self._on_change()
