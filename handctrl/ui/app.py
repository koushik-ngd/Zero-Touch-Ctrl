"""
HandCtrl — Main desktop application UI.

Modern dark desktop interface inspired by Linear, Raycast, Vercel, and Arc.
Features:
- Dual-panel layout (camera preview + control & settings)
- Live camera feed with hand landmark skeleton overlay
- Dynamic gesture status & confidence indicators
- Interactive 4-step screen calibration wizard
- Fine-grained gesture toggles and precision sliders
- Global emergency hotkey (Ctrl + Alt + H) & open palm hold safety
"""

from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional, List

import cv2
import numpy as np
from pynput import keyboard as kb

from handctrl.camera.camera_manager import CameraManager
from handctrl.camera.hand_tracker import HandTracker
from handctrl.camera.calibration import CalibrationManager
from handctrl.config import Settings, EMERGENCY_HOTKEY
from handctrl.control.action_manager import ActionManager
from handctrl.gestures.gesture_detector import GestureDetector
from handctrl.gestures.gesture_state import GestureState, GestureName
from handctrl.gestures.gesture_utils import index_tip_position
from handctrl.ui.camera_panel import CameraPanel
from handctrl.ui.settings_panel import SettingsPanel
from handctrl.ui.hud_island import DynamicIslandHUD
from handctrl.camera.pen_tracker import PenTracker
from handctrl.utils.logger import get_logger

log = get_logger()

# ---------------------------------------------------------------------------
# Design System (Zinc / Obsidian / Modern Cyber Theme)
# ---------------------------------------------------------------------------
BG_MAIN = "#09090b"  # Deep black/zinc
SURFACE_CARD = "#121215"  # Card background
SURFACE_ELEVATED = "#18181b"  # Elevated background
BORDER_SUBTLE = "#27272a"  # Subtle borders
BORDER_ACTIVE = "#38bdf8"
BORDER_FOCUS = "#3f3f46"

FG_TITLE = "#ffffff"
FG_PRIMARY = "#f4f4f5"
FG_SECONDARY = "#a1a1aa"
FG_MUTED = "#71717a"

COLOR_GREEN = "#10b981"
COLOR_GREEN_BG = "#064e3b"
COLOR_RED = "#ef4444"
COLOR_RED_BG = "#7f1d1d"
COLOR_AMBER = "#f59e0b"
COLOR_AMBER_BG = "#78350f"
COLOR_BLUE = "#3b82f6"
COLOR_CYAN = "#38bdf8"

PREVIEW_WIDTH = 540
PREVIEW_HEIGHT = 405


def _bind_hover(
    widget: tk.Widget,
    normal_bg: str,
    hover_bg: str,
    normal_fg: Optional[str] = None,
    hover_fg: Optional[str] = None,
) -> None:
    """Helper to attach sleek hover transitions to buttons."""
    def on_enter(_):
        try:
            if widget.cget("state") != "disabled":
                widget.configure(bg=hover_bg)
                if hover_fg:
                    widget.configure(fg=hover_fg)
        except Exception:
            pass

    def on_leave(_):
        try:
            if widget.cget("state") != "disabled":
                widget.configure(bg=normal_bg)
                if normal_fg:
                    widget.configure(fg=normal_fg)
        except Exception:
            pass

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")


class HandCtrlApp:
    """The main HandCtrl desktop application."""

    def __init__(self) -> None:
        self._settings = Settings.load()
        self._calibration = CalibrationManager()

        # Enumerate cameras
        self._available_cameras = CameraManager.list_available_cameras()

        # Core subsystems
        self._camera = CameraManager(camera_index=self._settings.camera_index)
        self._tracker = HandTracker(
            min_detection_confidence=self._settings.detection_confidence,
            min_tracking_confidence=self._settings.tracking_confidence,
        )
        self._gesture_detector = GestureDetector(self._settings)
        self._action_manager = ActionManager(self._settings, calibration=self._calibration)

        # Application state
        self._control_enabled: bool = False
        self._running: bool = False
        self._process_thread: Optional[threading.Thread] = None
        self._hotkey_listener: Optional[kb.GlobalHotKeys] = None

        # Calibration state
        self._is_calibrating: bool = False
        self._last_index_pos: Optional[tuple[float, float]] = None

        # Root Window
        self._root = tk.Tk()
        self._root.title("Zero-Touch-Ctrl — AI Gesture Control")
        self._root.configure(bg=BG_MAIN)
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Apply Windows 11 dark mode title bar & caption color
        self._apply_dark_title_bar()

        # Dynamic Island HUD overlay
        self._hud = DynamicIslandHUD(
            self._root,
            on_restore=self._restore_from_hud,
            on_toggle_control=self._toggle_control,
            on_close=self._on_close,
        )

        # Pen Tracking state
        self._pen_tracker = PenTracker()
        self._tracking_mode: str = "HAND"  # "HAND" or "PEN"
        self._pen_clicking: bool = False

        # Build UI layout
        self._build_ui()
        self._register_hotkey()

        # Spacebar click in Pen Mode
        self._root.bind("<space>", self._on_spacebar_click)

    def _apply_dark_title_bar(self) -> None:
        """Apply Windows 10/11 immersive dark mode and caption color to the native window frame."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import c_int, byref
            self._root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            if not hwnd:
                hwnd = self._root.winfo_id()
            # DWMWA_USE_IMMERSIVE_DARK_MODE (20 on Win11 / Win10 20H1+, 19 on older Win10)
            val = c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(val), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, byref(val), 4)
            # DWMWA_CAPTION_COLOR = 35 (BGR: 0x000B0909 for #09090b)
            caption_color = c_int(0x000B0909)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), 4)
        except Exception as exc:
            log.debug("Could not set Windows dark title bar: %s", exc)

    # ==================================================================
    # UI Layout Construction
    # ==================================================================
    def _build_ui(self) -> None:
        root = self._root

        # Main wrapper container
        app_container = tk.Frame(root, bg=BG_MAIN, padx=16, pady=12)
        app_container.pack(fill="both", expand=True)

        # --------------------------------------------------------------
        # 1. Top Header Bar
        # --------------------------------------------------------------
        header = tk.Frame(app_container, bg=BG_MAIN)
        header.pack(fill="x", pady=(0, 12))

        # Brand title & badge
        brand_frame = tk.Frame(header, bg=BG_MAIN)
        brand_frame.pack(side="left")

        logo_lbl = tk.Label(
            brand_frame,
            text="✦",
            bg=BG_MAIN,
            fg="#38bdf8",
            font=("Segoe UI", 16, "bold"),
        )
        logo_lbl.pack(side="left", padx=(0, 6))

        title_lbl = tk.Label(
            brand_frame,
            text="ZERO-TOUCH-CTRL",
            bg=BG_MAIN,
            fg=FG_TITLE,
            font=("Segoe UI", 14, "bold"),
        )
        title_lbl.pack(side="left")

        tag_lbl = tk.Label(
            brand_frame,
            text="AI AIR MOUSE",
            bg="#18181b",
            fg="#38bdf8",
            font=("Segoe UI", 7, "bold"),
            padx=7,
            pady=2,
            highlightbackground="#27272a",
            highlightthickness=1,
        )
        tag_lbl.pack(side="left", padx=(10, 0))

        # Status pills & Quick Controls on top right
        status_bar = tk.Frame(header, bg=BG_MAIN)
        status_bar.pack(side="right")

        # Mode toggle button (Hand vs Pen)
        self._mode_btn = tk.Button(
            status_bar,
            text="🖐️ HAND MODE",
            bg="#18181b",
            fg="#a1a1aa",
            activebackground="#27272a",
            activeforeground=FG_TITLE,
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=3,
            highlightbackground="#27272a",
            highlightthickness=1,
            command=self._toggle_tracking_mode,
        )
        self._mode_btn.pack(side="left", padx=(0, 8))
        _bind_hover(self._mode_btn, "#18181b", "#27272a", "#a1a1aa", FG_TITLE)

        # Mini HUD toggle button
        self._mini_hud_btn = tk.Button(
            status_bar,
            text="🏝️ MINI HUD",
            bg="#18181b",
            fg="#38bdf8",
            activebackground="#27272a",
            activeforeground=FG_TITLE,
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=3,
            highlightbackground="#27272a",
            highlightthickness=1,
            command=self._enter_mini_mode,
        )
        self._mini_hud_btn.pack(side="left", padx=(0, 8))
        _bind_hover(self._mini_hud_btn, "#18181b", "#27272a", "#38bdf8", FG_TITLE)

        self._cam_pill = tk.Label(
            status_bar,
            text="● CAMERA OFF",
            bg="#1f1414",
            fg=COLOR_RED,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            relief="flat",
            highlightbackground="#3b1d1d",
            highlightthickness=1,
        )
        self._cam_pill.pack(side="left", padx=(0, 8))

        self._ctrl_pill = tk.Label(
            status_bar,
            text="● CONTROL OFF",
            bg="#1f1414",
            fg=COLOR_RED,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            relief="flat",
            highlightbackground="#3b1d1d",
            highlightthickness=1,
        )
        self._ctrl_pill.pack(side="left")

        # --------------------------------------------------------------
        # 2. Main Body Split: Left (Camera) + Right (Control & Settings)
        # --------------------------------------------------------------
        body_split = tk.Frame(app_container, bg=BG_MAIN)
        body_split.pack(fill="both", expand=True)

        # === LEFT COLUMN: CAMERA FEED & LIVE HUD ===
        left_col = tk.Frame(body_split, bg=BG_MAIN)
        left_col.pack(side="left", fill="both", padx=(0, 14))

        # Pen control toolbar (appears when in PEN mode)
        self._pen_toolbar = tk.Frame(
            left_col,
            bg="#121215",
            highlightbackground="#27272a",
            highlightthickness=1,
            padx=8,
            pady=5,
        )

        tk.Label(
            self._pen_toolbar,
            text="🖊️ AIR PEN:",
            bg="#121215",
            fg="#38bdf8",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 6))

        tk.Label(
            self._pen_toolbar,
            text="Click tip in preview or select:",
            bg="#121215",
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left", padx=(0, 4))

        for col_name, col_emoji, hex_bg in [
            ("BLUE", "🔵 Blue", "#1e3a8a"),
            ("RED", "🔴 Red", "#881337"),
            ("GREEN", "🟢 Green", "#14532d"),
            ("YELLOW", "🟡 Yellow", "#713f12"),
        ]:
            tk.Button(
                self._pen_toolbar,
                text=col_emoji,
                bg=hex_bg,
                fg="#ffffff",
                font=("Segoe UI", 7, "bold"),
                relief="flat",
                cursor="hand2",
                padx=6,
                pady=2,
                command=lambda c=col_name: self._set_pen_color(c),
            ).pack(side="left", padx=2)

        self._pen_status_lbl = tk.Label(
            self._pen_toolbar,
            text="Locked: BLUE",
            bg="#18181b",
            fg=COLOR_GREEN,
            font=("Segoe UI", 8, "bold"),
            padx=6,
            pady=2,
            highlightbackground="#27272a",
            highlightthickness=1,
        )
        self._pen_status_lbl.pack(side="right")

        # Camera Preview
        self._camera_panel = CameraPanel(left_col, width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT)
        self._camera_panel.bind_click(self._on_camera_panel_click)

        # Calibration banner overlay (appears only when calibrating)
        self._cal_hud_frame = tk.Frame(
            left_col,
            bg="#1a1c23",
            highlightbackground=COLOR_BLUE,
            highlightthickness=1,
            padx=10,
            pady=8,
        )

        self._cal_hud_instruction = tk.Label(
            self._cal_hud_frame,
            text="1. Move your index finger to TOP-LEFT corner",
            bg="#1a1c23",
            fg="#67e8f9",
            font=("Segoe UI", 10, "bold"),
        )
        self._cal_hud_instruction.pack(side="left")

        self._cal_record_btn = tk.Button(
            self._cal_hud_frame,
            text="Capture Corner",
            bg=COLOR_BLUE,
            fg=FG_TITLE,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=3,
            command=self._on_record_calibration_corner,
        )
        self._cal_record_btn.pack(side="right", padx=(6, 0))

        self._cal_cancel_btn = tk.Button(
            self._cal_hud_frame,
            text="Cancel",
            bg="#27272a",
            fg=FG_SECONDARY,
            font=("Segoe UI", 9),
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=3,
            command=self._cancel_calibration_mode,
        )
        self._cal_cancel_btn.pack(side="right")

        # Cyber Telemetry Card below camera
        telemetry_card = tk.Frame(
            left_col,
            bg=SURFACE_CARD,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        telemetry_card.pack(fill="x", pady=(10, 0))

        # Row 1: Active Gesture & State Badge & FPS
        tel_row1 = tk.Frame(telemetry_card, bg=SURFACE_CARD)
        tel_row1.pack(fill="x")

        self._gesture_val_lbl = tk.Label(
            tel_row1,
            text="⚡ GESTURE: IDLE",
            bg=SURFACE_CARD,
            fg=FG_TITLE,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        self._gesture_val_lbl.pack(side="left")

        right_pills = tk.Frame(tel_row1, bg=SURFACE_CARD)
        right_pills.pack(side="right")

        self._state_badge = tk.Label(
            right_pills,
            text="STANDBY",
            bg="#1e2029",
            fg=FG_SECONDARY,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
            highlightbackground="#2b2f3d",
            highlightthickness=1,
        )
        self._state_badge.pack(side="left", padx=(0, 6))

        self._fps_val_lbl = tk.Label(
            right_pills,
            text="0 FPS",
            bg="#18181b",
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
            padx=7,
            pady=2,
            highlightbackground="#27272a",
            highlightthickness=1,
        )
        self._fps_val_lbl.pack(side="left")

        # Row 2: Live Confidence Meter with dynamic visual progress bar
        tel_row2 = tk.Frame(telemetry_card, bg=SURFACE_CARD)
        tel_row2.pack(fill="x", pady=(8, 0))

        self._conf_val_lbl = tk.Label(
            tel_row2,
            text="Confidence: 0%",
            bg=SURFACE_CARD,
            fg=FG_SECONDARY,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._conf_val_lbl.pack(side="left")

        self._conf_bar_width = 160
        self._conf_bar_height = 8
        self._conf_canvas = tk.Canvas(
            tel_row2,
            width=self._conf_bar_width,
            height=self._conf_bar_height,
            bg="#1c1d24",
            highlightthickness=1,
            highlightbackground="#2b2f3d",
            bd=0,
        )
        self._conf_canvas.pack(side="right", pady=4)
        self._conf_bar_fill = self._conf_canvas.create_rectangle(
            0, 0, 0, self._conf_bar_height, fill=COLOR_GREEN, width=0
        )

        # Camera toggle button row
        cam_btn_row = tk.Frame(left_col, bg=BG_MAIN)
        cam_btn_row.pack(fill="x", pady=(10, 0))

        self._start_cam_btn = tk.Button(
            cam_btn_row,
            text="▶ START CAMERA",
            bg="#1e2029",
            fg=FG_PRIMARY,
            activebackground="#2b2f3d",
            activeforeground=FG_TITLE,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=8,
            highlightbackground="#2b2f3d",
            highlightthickness=1,
            command=self._toggle_camera,
        )
        self._start_cam_btn.pack(side="left", fill="x", expand=True)
        _bind_hover(self._start_cam_btn, "#1e2029", "#2b2f3d", FG_PRIMARY, FG_TITLE)

        # === RIGHT COLUMN: CONTROL & SETTINGS ===
        right_col = tk.Frame(body_split, bg=BG_MAIN, width=380)
        right_col.pack(side="right", fill="both", expand=True)

        # --------------------------------------------------------------
        # COMMAND CENTER Card (Hero control button & quick telemetry)
        # --------------------------------------------------------------
        ctrl_card = tk.Frame(
            right_col,
            bg=SURFACE_CARD,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        ctrl_card.pack(fill="x", pady=(0, 10))

        ctrl_header = tk.Frame(ctrl_card, bg=SURFACE_CARD)
        ctrl_header.pack(fill="x", pady=(0, 8))

        ctrl_title = tk.Label(
            ctrl_header,
            text="COMMAND CENTER",
            bg=SURFACE_CARD,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        ctrl_title.pack(side="left")

        self._cursor_status_lbl = tk.Label(
            ctrl_header,
            text="○ Standby",
            bg=SURFACE_CARD,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        self._cursor_status_lbl.pack(side="right")

        # Main Hero Enable/Disable Control Button
        self._control_btn = tk.Button(
            ctrl_card,
            text="⚡ ACTIVATE GESTURE CONTROL",
            bg=COLOR_GREEN_BG,
            fg=COLOR_GREEN,
            activebackground="#166534",
            activeforeground=FG_TITLE,
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            cursor="hand2",
            pady=10,
            state="disabled",
            highlightbackground="#1b4322",
            highlightthickness=1,
            command=self._toggle_control,
        )
        self._control_btn.pack(fill="x")
        _bind_hover(self._control_btn, COLOR_GREEN_BG, "#166534", COLOR_GREEN, FG_TITLE)

        shortcut_hint = tk.Label(
            ctrl_card,
            text="Global Toggle Shortcut: Ctrl + Alt + H",
            bg=SURFACE_CARD,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        )
        shortcut_hint.pack(pady=(6, 0))

        # --------------------------------------------------------------
        # SETTINGS Card (Segmented Tabbed Command Center)
        # --------------------------------------------------------------
        settings_card = tk.Frame(
            right_col,
            bg=SURFACE_CARD,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
        )
        settings_card.pack(fill="both", expand=True)

        self._settings_panel = SettingsPanel(
            settings_card,
            self._settings,
            calibration=self._calibration,
            available_cameras=self._available_cameras,
            on_change=self._on_settings_change,
            on_camera_select=self._on_camera_switch,
            on_start_calibration=self._start_calibration_mode,
            on_reset_calibration=self._reset_calibration,
        )

        # --------------------------------------------------------------
        # Footer Bar
        # --------------------------------------------------------------
        footer = tk.Frame(app_container, bg=BG_MAIN)
        footer.pack(fill="x", pady=(12, 0))

        hotkey_notice = tk.Label(
            footer,
            text="⌨ Hotkeys: Ctrl+Alt+H (Toggle)  •  Ctrl+Alt+P (Mode)  •  Space (Pen Click)",
            bg=BG_MAIN,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        )
        hotkey_notice.pack(side="left")

        privacy_notice = tk.Label(
            footer,
            text="🔒 100% On-Device AI  •  Zero Cloud Latency",
            bg=BG_MAIN,
            fg="#52525b",
            font=("Segoe UI", 8),
        )
        privacy_notice.pack(side="right")

    def _add_mapping_row(self, parent: tk.Widget, label: str, value: str) -> tk.Label:
        row = tk.Frame(parent, bg=SURFACE_CARD)
        row.pack(fill="x", pady=2)

        lbl = tk.Label(
            row, text=label, bg=SURFACE_CARD, fg=FG_SECONDARY, font=("Segoe UI", 9)
        )
        lbl.pack(side="left")

        val = tk.Label(
            row,
            text=value,
            bg=SURFACE_CARD,
            fg=COLOR_GREEN if "Active" in value else FG_PRIMARY,
            font=("Segoe UI", 9, "bold" if "Active" in value else "normal"),
        )
        val.pack(side="right")
        return val

    # ==================================================================
    # Camera Lifecycle & Switching
    # ==================================================================
    def _toggle_camera(self) -> None:
        if self._camera.is_running:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self) -> None:
        if not self._camera.open(self._settings.camera_index):
            self._cam_pill.configure(
                text="● CAMERA FAILED", bg="#2a1414", fg=COLOR_RED, highlightbackground="#3b1d1d"
            )
            messagebox.showerror(
                "Camera Error",
                f"Could not open camera {self._settings.camera_index}.\n"
                "Please verify that another application is not using the camera.",
            )
            return

        self._camera.start()

        if not self._tracker.initialise():
            self._cam_pill.configure(
                text="● TRACKER ERROR", bg="#2a1414", fg=COLOR_RED, highlightbackground="#3b1d1d"
            )
            self._camera.stop()
            messagebox.showerror("Error", "MediaPipe Hand Tracker failed to initialize.")
            return

        self._cam_pill.configure(
            text="● CAMERA LIVE", bg="#142618", fg=COLOR_GREEN, highlightbackground="#1b4322"
        )
        self._start_cam_btn.configure(
            text="■ STOP CAMERA", bg="#3f1d1d", fg=COLOR_RED, highlightbackground="#7f1d1d"
        )
        _bind_hover(self._start_cam_btn, "#3f1d1d", "#582020", COLOR_RED, "#ffffff")
        self._control_btn.configure(state="normal")
        self._start_processing()
        log.info("Webcam started successfully")

    def _stop_camera(self) -> None:
        if self._is_calibrating:
            self._cancel_calibration_mode()

        if self._control_enabled:
            self._toggle_control()

        self._stop_processing()
        self._tracker.release()
        self._camera.stop()

        self._camera_panel.reset_placeholder()
        self._cam_pill.configure(
            text="● CAMERA OFF", bg="#1f1414", fg=COLOR_RED, highlightbackground="#3b1d1d"
        )
        self._start_cam_btn.configure(
            text="▶ START CAMERA", bg="#1e2029", fg=FG_PRIMARY, highlightbackground="#2b2f3d"
        )
        _bind_hover(self._start_cam_btn, "#1e2029", "#2b2f3d", FG_PRIMARY, FG_TITLE)
        self._control_btn.configure(state="disabled")
        self._fps_val_lbl.configure(text="0 FPS")
        self._conf_val_lbl.configure(text="Confidence: 0%")
        self._gesture_val_lbl.configure(text="⚡ GESTURE: IDLE")
        self._state_badge.configure(text="STANDBY", bg="#1e2029", fg=FG_SECONDARY, highlightbackground="#2b2f3d")
        try:
            self._conf_canvas.coords(self._conf_bar_fill, 0, 0, 0, self._conf_bar_height)
        except Exception:
            pass
        log.info("Webcam stopped")

    def _on_camera_switch(self, new_index: int) -> None:
        """Switch camera device dynamically."""
        was_running = self._camera.is_running
        was_controlling = self._control_enabled

        if was_running:
            self._stop_camera()

        self._settings.camera_index = new_index
        self._settings.save()

        if was_running:
            self._start_camera()
            if was_controlling:
                self._toggle_control()

    # ==================================================================
    # Mini Mode (Dynamic Island HUD)
    # ==================================================================
    def _enter_mini_mode(self) -> None:
        """Switch from full desktop control panel to floating Dynamic Island HUD."""
        self._root.withdraw()
        self._hud.show()
        # Automatically start camera if not already running
        if not self._camera.is_running:
            self._start_camera()
        log.info("Entered Dynamic Island HUD mini-mode")

    def _restore_from_hud(self) -> None:
        """Expand Dynamic Island HUD back to full desktop control panel."""
        self._hud.hide()
        self._root.deiconify()
        self._root.lift()
        log.info("Restored full Control Panel from HUD mini-mode")

    # ==================================================================
    # Pen Mode & Color Sampling
    # ==================================================================
    def _toggle_tracking_mode(self) -> None:
        """Toggle between Hand Gestures and Air Pen tracking."""
        if self._tracking_mode == "HAND":
            self._tracking_mode = "PEN"
            self._mode_btn.configure(
                text="🖊️ PEN MODE", bg="#0c4a6e", fg="#38bdf8", highlightbackground="#0284c7"
            )
            self._pen_toolbar.pack(fill="x", pady=(0, 6), before=self._camera_panel._frame_container)
            log.info("Switched to PEN MODE")
        else:
            if self._pen_clicking and self._control_enabled:
                self._action_manager.mouse.drag_end()
                self._pen_clicking = False
            self._tracking_mode = "HAND"
            self._mode_btn.configure(
                text="🖐️ HAND MODE", bg="#18181b", fg="#a1a1aa", highlightbackground="#27272a"
            )
            self._pen_toolbar.pack_forget()
            log.info("Switched to HAND MODE")

    def _set_pen_color(self, preset_name: str) -> None:
        """Switch active pen color preset."""
        self._pen_tracker.set_preset(preset_name)
        self._pen_status_lbl.configure(text=f"Locked: {preset_name}", fg=COLOR_GREEN)

    def _on_camera_panel_click(self, frame_x: int, frame_y: int) -> None:
        """Sample pen tip color when user clicks the preview in Pen Mode."""
        if self._tracking_mode != "PEN":
            return
        frame = self._camera.get_frame()
        if frame is not None:
            self._pen_tracker.sample_color_at_pixel(frame, frame_x, frame_y)
            self._pen_status_lbl.configure(text="Locked: Custom Pen", fg="#38bdf8")
            log.info("Sampled pen color at pixel (%d, %d)", frame_x, frame_y)

    def _on_spacebar_click(self, event: tk.Event) -> None:
        """Trigger mouse click via Spacebar when in Pen Mode."""
        if self._control_enabled and self._tracking_mode == "PEN":
            self._action_manager.mouse.click()
            log.info("Spacebar pen click executed")

    def _on_mode_hotkey(self) -> None:
        log.info("Mode toggle hotkey pressed")
        self._root.after(0, self._toggle_tracking_mode)

    # ==================================================================
    # Control Toggle & Safety
    # ==================================================================
    def _toggle_control(self) -> None:
        if self._control_enabled:
            self._control_enabled = False
            self._gesture_detector.disable()
            self._action_manager.disable()
            self._control_btn.configure(
                text="⚡ ACTIVATE GESTURE CONTROL",
                bg=COLOR_GREEN_BG,
                fg=COLOR_GREEN,
                activebackground="#166534",
                highlightbackground="#1b4322",
            )
            _bind_hover(self._control_btn, COLOR_GREEN_BG, "#166534", COLOR_GREEN, FG_TITLE)
            self._ctrl_pill.configure(
                text="● CONTROL OFF", bg="#1f1414", fg=COLOR_RED, highlightbackground="#3b1d1d"
            )
            self._cursor_status_lbl.configure(text="○ Standby", fg=FG_MUTED)
            log.info("Gesture control toggled OFF")
        else:
            if not self._camera.is_running:
                return
            if self._is_calibrating:
                self._cancel_calibration_mode()

            self._control_enabled = True
            self._gesture_detector.enable()
            self._action_manager.enable()
            self._control_btn.configure(
                text="⏹ DEACTIVATE GESTURE CONTROL",
                bg=COLOR_RED_BG,
                fg="#fca5a5",
                activebackground="#991b1b",
                highlightbackground="#7f1d1d",
            )
            _bind_hover(self._control_btn, COLOR_RED_BG, "#991b1b", "#fca5a5", FG_TITLE)
            self._ctrl_pill.configure(
                text="● CONTROL LIVE", bg="#142618", fg=COLOR_GREEN, highlightbackground="#1b4322"
            )
            self._cursor_status_lbl.configure(text="● Active", fg=COLOR_GREEN)
            log.info("Gesture control toggled ON")

        # Synchronize HUD island buttons and state
        self._hud.update_hud(
            self._gesture_detector.current_gesture_name,
            self._gesture_detector.gesture_state.name,
            self._gesture_detector.state.confidence,
            self._control_enabled,
            None,
        )

    # ==================================================================
    # Processing Loop (Thread-safe background worker)
    # ==================================================================
    def _start_processing(self) -> None:
        self._running = True
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()

    def _stop_processing(self) -> None:
        self._running = False
        if self._process_thread is not None:
            self._process_thread.join(timeout=2.0)
            self._process_thread = None

    def _process_loop(self) -> None:
        """Background worker thread: reads frames, tracks landmarks, detects gestures."""
        while self._running:
            frame = self._camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            # Process hand landmarks
            result = self._tracker.process(frame, draw=True)
            display = result.annotated_frame if result.annotated_frame is not None else frame
            hand = result.primary_hand

            # Keep index position updated for calibration
            if hand is not None:
                ix, iy = index_tip_position(hand.landmark_array)
                self._last_index_pos = (ix, iy)

            # If calibrating, skip control actions
            if self._is_calibrating:
                cal_step = self._calibration.STEPS[self._calibration.current_step_index]
                cal_instruction = self._calibration.current_step_instruction
                self._root.after(0, self._camera_panel.update_frame, display, cal_step, cal_instruction)
                self._root.after(0, self._update_hud_labels, "CALIBRATING", "CALIBRATING", 1.0, self._camera.fps)
                time.sleep(0.005)
                continue

            # Check tracking mode: PEN vs HAND
            if self._tracking_mode == "PEN":
                pen_res, display = self._pen_tracker.process(display, hand=hand, draw=True)

                if pen_res.detected and pen_res.tip_norm is not None:
                    tip_x, tip_y = pen_res.tip_norm
                    if self._control_enabled:
                        self._action_manager.mouse.move_cursor(tip_x, tip_y)

                        if pen_res.is_clicking:
                            if not self._pen_clicking:
                                self._action_manager.mouse.drag_start()
                                self._pen_clicking = True
                        else:
                            if self._pen_clicking:
                                self._action_manager.mouse.drag_end()
                                self._pen_clicking = False

                    gesture_name = f"PEN ({self._pen_tracker.active_color_name})"
                    state_name = "PEN_CLICK" if self._pen_clicking else "PEN_ACTIVE"
                    conf = pen_res.confidence

                    self._root.after(0, self._camera_panel.update_frame, display, None, None)
                    self._root.after(0, self._update_hud_labels, gesture_name, state_name, conf, self._camera.fps)
                    self._root.after(
                        0,
                        self._hud.update_hud,
                        gesture_name,
                        state_name,
                        conf,
                        self._control_enabled,
                        None,
                        pen_res.tip_norm,
                    )
                else:
                    if self._pen_clicking and self._control_enabled:
                        self._action_manager.mouse.drag_end()
                        self._pen_clicking = False

                    gesture_name = "SEARCHING PEN..."
                    state_name = "IDLE"
                    self._root.after(0, self._camera_panel.update_frame, display, None, None)
                    self._root.after(0, self._update_hud_labels, gesture_name, state_name, 0.0, self._camera.fps)
                    self._root.after(
                        0,
                        self._hud.update_hud,
                        gesture_name,
                        state_name,
                        0.0,
                        self._control_enabled,
                        None,
                        None,
                    )

                time.sleep(0.005)
                continue

            # Gesture detection
            events = self._gesture_detector.update(hand)

            # Check swipe if hand is active
            if hand is not None and self._gesture_detector.gesture_state != GestureState.DISABLED:
                swipe = self._gesture_detector.check_swipe(hand.landmark_array)
                if swipe:
                    events.append(swipe)

            # Dispatch actions to mouse/keyboard
            if self._control_enabled:
                self._action_manager.dispatch(events)

            # Emergency stop detection
            for ev in events:
                if ev.action == "emergency_stop":
                    self._root.after(0, self._handle_emergency_stop)

            # Update HUD and camera panel on main UI thread
            gesture_name = self._gesture_detector.current_gesture_name
            state_name = self._gesture_detector.gesture_state.name
            conf = self._gesture_detector.state.confidence

            # Handle paused state display
            if self._gesture_detector.gesture_state == GestureState.PAUSED:
                gesture_name = "GESTURE CONTROL PAUSED"

            lm_array = hand.landmark_array if hand is not None else None
            # Draw holographic ripple visual effects
            self._gesture_detector.draw_effects(display)

            self._root.after(0, self._camera_panel.update_frame, display, None, None)
            self._root.after(0, self._update_hud_labels, gesture_name, state_name, conf, self._camera.fps)
            self._root.after(
                0,
                self._hud.update_hud,
                gesture_name,
                state_name,
                conf,
                self._control_enabled,
                lm_array,
            )

            time.sleep(0.005)

    def _update_hud_labels(self, gesture: str, state: str, conf: float, fps: float) -> None:
        """Update live status labels on main UI."""
        icon = "⚡"
        if "TAP" in gesture or "CLICK" in gesture:
            icon = "👆"
        elif "PINCH" in gesture or "DRAG" in gesture:
            icon = "👌"
        elif "SCROLL" in gesture:
            icon = "↕️"
        elif "PAUSED" in gesture:
            icon = "✋"
        elif "PEN" in gesture:
            icon = "🖊️"
        elif "THUMBS" in gesture or "MEDIA" in gesture:
            icon = "👍"
        elif "SWIPE" in gesture:
            icon = "💨"
        elif "CALIBRAT" in gesture:
            icon = "🎯"

        self._gesture_val_lbl.configure(text=f"{icon} {gesture}")

        # State badge formatting
        self._state_badge.configure(text=state)
        if state in ("CURSOR", "DRAGGING", "SCROLLING", "PEN_ACTIVE", "PEN_CLICK", "TAP_DETECTED"):
            self._state_badge.configure(bg=COLOR_GREEN_BG, fg=COLOR_GREEN, highlightbackground="#1b4322")
        elif state == "PAUSED":
            self._state_badge.configure(bg=COLOR_AMBER_BG, fg=COLOR_AMBER, highlightbackground="#78350f")
        elif state == "DISABLED":
            self._state_badge.configure(bg="#27272a", fg=FG_MUTED, highlightbackground="#3f3f46")
        else:
            self._state_badge.configure(bg="#1e2029", fg=FG_SECONDARY, highlightbackground="#2b2f3d")

        self._conf_val_lbl.configure(text=f"Confidence: {conf:.0%}")
        self._fps_val_lbl.configure(text=f"{fps:.0f} FPS")

        # Dynamically update the visual confidence progress bar
        try:
            bar_w = int(self._conf_bar_width * max(0.0, min(1.0, conf)))
            bar_color = COLOR_GREEN if conf >= 0.7 else (COLOR_AMBER if conf >= 0.4 else COLOR_RED)
            self._conf_canvas.coords(self._conf_bar_fill, 0, 0, bar_w, self._conf_bar_height)
            self._conf_canvas.itemconfig(self._conf_bar_fill, fill=bar_color)
        except Exception:
            pass

    # ==================================================================
    # Screen Calibration Workflow
    # ==================================================================
    def _start_calibration_mode(self) -> None:
        """Start the 4-corner screen calibration process."""
        if not self._camera.is_running:
            self._start_camera()

        if self._control_enabled:
            self._toggle_control()

        self._is_calibrating = True
        self._calibration.start_calibration()
        self._cal_hud_frame.pack(fill="x", pady=(8, 0))
        self._update_calibration_banner()
        log.info("Calibration wizard active")

    def _cancel_calibration_mode(self) -> None:
        self._is_calibrating = False
        self._calibration.cancel_calibration()
        self._cal_hud_frame.pack_forget()
        self._settings_panel.update_calibration_status()
        log.info("Calibration wizard cancelled")

    def _on_record_calibration_corner(self) -> None:
        """Record the current index finger position for the active calibration step."""
        if not self._last_index_pos:
            messagebox.showwarning(
                "Hand not detected",
                "Please place your index finger in the camera view before capturing.",
            )
            return

        ix, iy = self._last_index_pos
        finished = self._calibration.record_point(ix, iy)

        if finished:
            self._is_calibrating = False
            self._cal_hud_frame.pack_forget()
            self._action_manager.set_calibration(self._calibration)
            self._settings_panel.update_calibration_status()
            messagebox.showinfo(
                "Calibration Complete",
                "Screen corners mapped successfully!\nTracking will now use your calibrated boundaries.",
            )
        else:
            self._update_calibration_banner()

    def _update_calibration_banner(self) -> None:
        instruction = self._calibration.current_step_instruction
        self._cal_hud_instruction.configure(text=instruction)

    def _reset_calibration(self) -> None:
        self._calibration.reset_to_defaults()
        self._action_manager.set_calibration(self._calibration)
        self._settings_panel.update_calibration_status()
        messagebox.showinfo("Reset", "Calibration reset to default screen dead-zone.")

    # ==================================================================
    # Hotkeys & Emergency Stop
    # ==================================================================
    def _register_hotkey(self) -> None:
        """Register the global Ctrl+Alt+H emergency toggle hotkey."""
        try:
            self._hotkey_listener = kb.GlobalHotKeys({
                EMERGENCY_HOTKEY: self._on_emergency_hotkey,
                "<ctrl>+<alt>+p": self._on_mode_hotkey,
            })
            self._hotkey_listener.start()
            log.info("Emergency global hotkey registered: %s, mode hotkey: Ctrl+Alt+P", EMERGENCY_HOTKEY)
        except Exception as exc:
            log.error("Failed to register emergency hotkey: %s", exc)

    def _on_emergency_hotkey(self) -> None:
        log.info("Emergency hotkey pressed")
        self._root.after(0, self._toggle_control)

    def _handle_emergency_stop(self) -> None:
        """Handle emergency stop triggered by holding open palm for 1 second."""
        log.warning("Emergency stop triggered by open palm hold")
        if self._control_enabled:
            self._toggle_control()
            self._ctrl_pill.configure(
                text="● EMERGENCY STOP", bg=COLOR_RED_BG, fg="#ffffff", highlightbackground=COLOR_RED
            )

    # ==================================================================
    # Settings change callback
    # ==================================================================
    def _on_settings_change(self) -> None:
        self._tracker.update_confidence(
            detection=self._settings.detection_confidence,
            tracking=self._settings.tracking_confidence,
        )
        log.debug("Settings updated and applied")

    # ==================================================================
    # Application Lifecycle
    # ==================================================================
    def run(self) -> None:
        """Start HandCtrl main loop."""
        log.info("HandCtrl application running")
        self._root.mainloop()

    def _on_close(self) -> None:
        """Clean shutdown releasing all resources."""
        log.info("Closing application...")
        self._running = False

        if self._control_enabled:
            self._control_enabled = False
            if self._pen_clicking:
                self._action_manager.mouse.drag_end()
                self._pen_clicking = False
            self._gesture_detector.disable()
            self._action_manager.disable()

        self._stop_processing()
        self._tracker.release()
        self._camera.stop()

        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()

        if self._hud is not None:
            self._hud.hide()

        self._root.destroy()
        log.info("HandCtrl closed cleanly")
