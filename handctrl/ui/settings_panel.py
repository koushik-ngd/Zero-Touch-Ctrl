"""
Zero-Touch-Ctrl — Modern Command Center & Settings Panel.

Clean, Linear/Raycast-inspired dark UI with segmented tabs:
- 🎮 Gestures: Live triggers, mapping, and active feedback
- 🎛️ Tuning: Precision sensitivity sliders & feature toggles
- 🎯 Calibration: 4-Corner screen boundary mapper
- 📷 Device: Webcam selector & privacy assurance
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, List, Dict

from handctrl.config import Settings
from handctrl.camera.calibration import CalibrationManager

# Theme Palette (Deep Obsidian / Modern Cyber)
BG_PANEL = "#111217"
TAB_BAR_BG = "#161822"
CARD_BG = "#171923"
BORDER_SUBTLE = "#232736"
BORDER_ACTIVE = "#38bdf8"
FG_PRIMARY = "#f4f4f5"
FG_SECONDARY = "#a1a1aa"
FG_MUTED = "#71717a"
ACCENT_CYAN = "#38bdf8"
ACCENT_GREEN = "#10b981"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"


class SettingsPanel:
    """Tabbed Command Center with Gestures, Sensitivity Tuning, Calibration, and Camera."""

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

        self._frame = tk.Frame(parent, bg=BG_PANEL, bd=0)
        self._frame.pack(fill="both", expand=True)

        self._tab_buttons: Dict[str, tk.Button] = {}
        self._tab_frames: Dict[str, tk.Frame] = {}
        self._active_tab = "gestures"

        self._build()

    def _build(self) -> None:
        # 1. Segmented Navigation Tab Bar at the top
        tab_bar = tk.Frame(self._frame, bg=TAB_BAR_BG, padx=6, pady=6)
        tab_bar.pack(fill="x")

        tabs = [
            ("gestures", "🎮 Gestures"),
            ("tuning", "🎛️ Tuning"),
            ("calibration", "🎯 Screen"),
            ("device", "📷 Device"),
        ]

        for tab_id, tab_label in tabs:
            btn = tk.Button(
                tab_bar,
                text=tab_label,
                bg="#1a1c26",
                fg=FG_MUTED,
                activebackground="#222634",
                activeforeground=FG_PRIMARY,
                font=("Segoe UI", 8, "bold"),
                relief="flat",
                cursor="hand2",
                padx=8,
                pady=4,
                bd=0,
                command=lambda tid=tab_id: self._switch_tab(tid),
            )
            btn.pack(side="left", padx=2, fill="x", expand=True)
            self._tab_buttons[tab_id] = btn

        # 2. Content Container for Pages
        self._content_container = tk.Frame(self._frame, bg=BG_PANEL, padx=10, pady=10)
        self._content_container.pack(fill="both", expand=True)

        # Build individual tab views
        self._build_gestures_tab()
        self._build_tuning_tab()
        self._build_calibration_tab()
        self._build_device_tab()

        # Show default tab
        self._switch_tab("gestures")

    def _switch_tab(self, tab_id: str) -> None:
        """Switch active tab with visual highlight."""
        self._active_tab = tab_id
        for tid, frame in self._tab_frames.items():
            if tid == tab_id:
                frame.pack(fill="both", expand=True)
                self._tab_buttons[tid].configure(
                    bg="#282d3f",
                    fg="#ffffff",
                    highlightbackground=ACCENT_CYAN,
                    highlightthickness=1,
                )
            else:
                frame.pack_forget()
                self._tab_buttons[tid].configure(
                    bg="#1a1c26",
                    fg=FG_MUTED,
                    highlightthickness=0,
                )

    # ------------------------------------------------------------------
    # TAB 1: GESTURES & ACTION MAP
    # ------------------------------------------------------------------
    def _build_gestures_tab(self) -> None:
        tab = tk.Frame(self._content_container, bg=BG_PANEL)
        self._tab_frames["gestures"] = tab

        # Header title
        lbl = tk.Label(
            tab,
            text="ACTIVE GESTURE CONTROLS",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        lbl.pack(anchor="w", pady=(0, 6))

        # Gesture cards list container
        list_container = tk.Frame(tab, bg=BG_PANEL)
        list_container.pack(fill="both", expand=True)

        gestures_data = [
            ("☝️ Index Finger", "Move Cursor", "Live Navigation"),
            ("🫵 3D Depth Tap", "Left Click", "Push forward in thin air"),
            ("🤏 Pinch & Hold", "Left Click / Drag", "Pinch thumb & index"),
            ("✌️ Two Fingers", "Smooth Scroll", "Index + middle up/down"),
            ("✋ Open Palm", "Pause Control", "Hold 1s for Emergency Stop"),
            ("👍 Thumbs Up", "Play / Pause", "Instant media control"),
            ("👋 Hand Swipe", "Skip Track", "Swipe left / right in air"),
            ("🖊️ Air Stylus", "Optical Pen", "Track any pen tip / laser"),
        ]

        for icon_title, action_title, desc in gestures_data:
            card = tk.Frame(
                list_container,
                bg=CARD_BG,
                highlightbackground=BORDER_SUBTLE,
                highlightthickness=1,
                padx=8,
                pady=4,
            )
            card.pack(fill="x", pady=2)

            left_side = tk.Frame(card, bg=CARD_BG)
            left_side.pack(side="left")

            title_lbl = tk.Label(
                left_side,
                text=icon_title,
                bg=CARD_BG,
                fg=FG_PRIMARY,
                font=("Segoe UI", 8, "bold"),
            )
            title_lbl.pack(anchor="w")

            desc_lbl = tk.Label(
                left_side,
                text=desc,
                bg=CARD_BG,
                fg=FG_MUTED,
                font=("Segoe UI", 7),
            )
            desc_lbl.pack(anchor="w")

            badge = tk.Label(
                card,
                text=action_title,
                bg="#1e2230",
                fg=ACCENT_CYAN if "Click" in action_title else FG_SECONDARY,
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=2,
                highlightbackground="#2c3246",
                highlightthickness=1,
            )
            badge.pack(side="right")

    # ------------------------------------------------------------------
    # TAB 2: SENSITIVITY & TUNING
    # ------------------------------------------------------------------
    def _build_tuning_tab(self) -> None:
        tab = tk.Frame(self._content_container, bg=BG_PANEL)
        self._tab_frames["tuning"] = tab
        s = self._settings

        # Sliders container
        self._add_slider(tab, "Cursor Smoothing", 0.0, 0.9, s.cursor_smoothing, 0.05, self._on_smoothing)
        self._add_slider(tab, "3D Air Tap Sensitivity", 0.02, 0.09, getattr(s, "depth_tap_threshold", 0.045), 0.005, self._on_depth_tap_sens)
        self._add_slider(tab, "Pinch Detection Distance", 0.02, 0.10, s.pinch_threshold, 0.005, self._on_pinch)
        self._add_slider(tab, "Scroll Sensitivity", 1.0, 20.0, s.scroll_sensitivity, 0.5, self._on_scroll)
        self._add_slider(tab, "Min Detection Confidence", 0.40, 0.95, s.detection_confidence, 0.05, self._on_det_conf)

        # Quick Toggles Section
        toggles_title = tk.Label(
            tab,
            text="FEATURE TOGGLES",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        toggles_title.pack(anchor="w", pady=(10, 4))

        toggles_box = tk.Frame(tab, bg=CARD_BG, highlightbackground=BORDER_SUBTLE, highlightthickness=1, padx=8, pady=4)
        toggles_box.pack(fill="x")

        # Two-column toggle layout
        col1 = tk.Frame(toggles_box, bg=CARD_BG)
        col1.pack(side="left", fill="both", expand=True)
        col2 = tk.Frame(toggles_box, bg=CARD_BG)
        col2.pack(side="left", fill="both", expand=True)

        self._add_mini_toggle(col1, "Cursor Move", s.enable_cursor, self._on_toggle_cursor)
        self._add_mini_toggle(col1, "3D Air Tap", getattr(s, "enable_depth_tap", True), self._on_toggle_depth_tap)
        self._add_mini_toggle(col1, "Pinch Click", s.enable_click, self._on_toggle_click)
        self._add_mini_toggle(col1, "Drag & Drop", s.enable_drag, self._on_toggle_drag)

        self._add_mini_toggle(col2, "Scroll Wheel", s.enable_scroll, self._on_toggle_scroll)
        self._add_mini_toggle(col2, "Thumbs Up Media", s.enable_thumbs_up, self._on_toggle_thumbs)
        self._add_mini_toggle(col2, "Swipe Tracks", s.enable_swipe, self._on_toggle_swipe)
        self._add_mini_toggle(col2, "Palm Pause", s.enable_palm_pause, self._on_toggle_pause)

    # ------------------------------------------------------------------
    # TAB 3: SCREEN CALIBRATION
    # ------------------------------------------------------------------
    def _build_calibration_tab(self) -> None:
        tab = tk.Frame(self._content_container, bg=BG_PANEL)
        self._tab_frames["calibration"] = tab

        card = tk.Frame(tab, bg=CARD_BG, highlightbackground=BORDER_SUBTLE, highlightthickness=1, padx=14, pady=14)
        card.pack(fill="both", expand=True)

        title = tk.Label(
            card,
            text="🎯 4-CORNER PERSPECTIVE CALIBRATION",
            bg=CARD_BG,
            fg=ACCENT_CYAN,
            font=("Segoe UI", 10, "bold"),
        )
        title.pack(anchor="w", pady=(0, 4))

        desc = tk.Label(
            card,
            text="Map your physical webcam field-of-view directly to your screen edges. Perfect for laptop webcams or sitting at an angle.",
            bg=CARD_BG,
            fg=FG_SECONDARY,
            font=("Segoe UI", 8),
            justify="left",
            wraplength=320,
        )
        desc.pack(anchor="w", pady=(0, 12))

        # Status badge
        is_cal = self._calibration.data.is_calibrated
        self._cal_status_lbl = tk.Label(
            card,
            text="● STATUS: CALIBRATED (CUSTOM MATRIX)" if is_cal else "● STATUS: DEFAULT DEAD-ZONE",
            bg="#101b14" if is_cal else "#18181b",
            fg=ACCENT_GREEN if is_cal else FG_SECONDARY,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
            highlightbackground="#1b4322" if is_cal else "#27272a",
            highlightthickness=1,
        )
        self._cal_status_lbl.pack(fill="x", pady=(0, 14))

        # Action Buttons
        self._cal_btn = tk.Button(
            card,
            text="▶ START 4-CORNER CALIBRATION",
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            pady=8,
            bd=0,
            command=self._on_calibrate_click,
        )
        self._cal_btn.pack(fill="x", pady=(0, 8))

        self._reset_cal_btn = tk.Button(
            card,
            text="↺ Reset to Default Dead-Zone",
            bg="#222634",
            fg=FG_MUTED,
            activebackground="#2c3246",
            activeforeground=FG_PRIMARY,
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            pady=6,
            bd=0,
            command=self._on_reset_cal_click,
        )
        self._reset_cal_btn.pack(fill="x")

    # ------------------------------------------------------------------
    # TAB 4: CAMERA DEVICE & PRIVACY
    # ------------------------------------------------------------------
    def _build_device_tab(self) -> None:
        tab = tk.Frame(self._content_container, bg=BG_PANEL)
        self._tab_frames["device"] = tab
        s = self._settings

        # Camera selection card
        cam_card = tk.Frame(tab, bg=CARD_BG, highlightbackground=BORDER_SUBTLE, highlightthickness=1, padx=12, pady=12)
        cam_card.pack(fill="x", pady=(0, 10))

        tk.Label(
            cam_card,
            text="WEBCAM INPUT SELECTOR",
            bg=CARD_BG,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        # Camera device buttons row
        cam_btn_row = tk.Frame(cam_card, bg=CARD_BG)
        cam_btn_row.pack(fill="x", pady=(0, 6))

        self._cam_buttons: Dict[int, tk.Button] = {}
        cams = self._available_cameras or [0]
        if s.camera_index not in cams:
            cams.append(s.camera_index)

        for c_idx in cams:
            is_active = (c_idx == s.camera_index)
            c_btn = tk.Button(
                cam_btn_row,
                text=f"📹 Camera {c_idx}",
                bg="#2563eb" if is_active else "#222634",
                fg="#ffffff" if is_active else FG_SECONDARY,
                activebackground="#1d4ed8",
                activeforeground="#ffffff",
                font=("Segoe UI", 8, "bold"),
                relief="flat",
                cursor="hand2",
                padx=10,
                pady=5,
                bd=0,
                command=lambda idx=c_idx: self._select_camera(idx),
            )
            c_btn.pack(side="left", padx=3)
            self._cam_buttons[c_idx] = c_btn

        # Device info
        tk.Label(
            cam_card,
            text="Resolution: 640x480 • Target FPS: 30–60 • Latency: ~12ms",
            bg=CARD_BG,
            fg=FG_MUTED,
            font=("Segoe UI", 7),
        ).pack(anchor="w")

        # Privacy Card
        priv_card = tk.Frame(tab, bg=CARD_BG, highlightbackground=BORDER_SUBTLE, highlightthickness=1, padx=12, pady=12)
        priv_card.pack(fill="x")

        tk.Label(
            priv_card,
            text="🔒 100% PRIVATE & ON-DEVICE",
            bg=CARD_BG,
            fg=ACCENT_GREEN,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            priv_card,
            text="Zero-Touch-Ctrl executes MediaPipe neural networks entirely in local memory. No frames, telemetry, or images ever leave your computer.",
            bg=CARD_BG,
            fg=FG_SECONDARY,
            font=("Segoe UI", 8),
            justify="left",
            wraplength=320,
        ).pack(anchor="w")

    # ------------------------------------------------------------------
    # Helper Components: Sliders & Mini Toggles
    # ------------------------------------------------------------------
    def _add_slider(
        self,
        parent: tk.Widget,
        label: str,
        min_val: float,
        max_val: float,
        initial: float,
        resolution: float,
        callback: Callable[[str], None],
    ) -> None:
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=2)

        top_line = tk.Frame(row, bg=BG_PANEL)
        top_line.pack(fill="x")

        lbl = tk.Label(top_line, text=label, bg=BG_PANEL, fg=FG_SECONDARY, font=("Segoe UI", 8))
        lbl.pack(side="left")

        val_lbl = tk.Label(
            top_line,
            text=f"{initial:.2f}",
            bg="#181a24",
            fg=ACCENT_CYAN,
            font=("Segoe UI", 7, "bold"),
            padx=4,
            pady=0,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
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
            bg=BG_PANEL,
            fg=FG_PRIMARY,
            troughcolor="#1c202d",
            activebackground=ACCENT_CYAN,
            highlightthickness=0,
            showvalue=False,
            sliderrelief="flat",
            bd=0,
            length=320,
        )
        scale.pack(fill="x", pady=(1, 4))

    def _add_mini_toggle(
        self,
        parent: tk.Widget,
        label: str,
        initial: bool,
        callback: Callable[[bool], None],
    ) -> None:
        var = tk.BooleanVar(value=initial)

        def _toggled():
            callback(var.get())

        cb = tk.Checkbutton(
            parent,
            text=label,
            variable=var,
            command=_toggled,
            bg=CARD_BG,
            fg=FG_PRIMARY,
            selectcolor="#242938",
            activebackground=CARD_BG,
            activeforeground=FG_PRIMARY,
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 7),
        )
        cb.pack(anchor="w", pady=1)

    # ------------------------------------------------------------------
    # Event Handlers & Callbacks
    # ------------------------------------------------------------------
    def _select_camera(self, cam_idx: int) -> None:
        self._settings.camera_index = cam_idx
        for idx, btn in self._cam_buttons.items():
            if idx == cam_idx:
                btn.configure(bg="#2563eb", fg="#ffffff")
            else:
                btn.configure(bg="#222634", fg=FG_SECONDARY)
        self._fire_change()
        if self._on_camera_select:
            self._on_camera_select(cam_idx)

    def _on_smoothing(self, val: str) -> None:
        self._settings.cursor_smoothing = float(val)
        self._fire_change()

    def _on_pinch(self, val: str) -> None:
        self._settings.pinch_threshold = float(val)
        self._fire_change()

    def _on_scroll(self, val: str) -> None:
        self._settings.scroll_sensitivity = float(val)
        self._fire_change()

    def _on_det_conf(self, val: str) -> None:
        self._settings.detection_confidence = float(val)
        self._fire_change()

    def _on_depth_tap_sens(self, val: str) -> None:
        self._settings.depth_tap_threshold = float(val)
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

    def _on_toggle_depth_tap(self, state: bool) -> None:
        self._settings.enable_depth_tap = state
        self._fire_change()

    def _on_calibrate_click(self) -> None:
        if self._on_start_calibration:
            self._on_start_calibration()

    def _on_reset_cal_click(self) -> None:
        if self._on_reset_calibration:
            self._on_reset_calibration()
        self.update_calibration_status()

    def update_calibration_status(self) -> None:
        """Refresh calibration status badge."""
        if hasattr(self, "_cal_status_lbl"):
            is_cal = self._calibration.data.is_calibrated
            if is_cal:
                self._cal_status_lbl.configure(
                    text="● STATUS: CALIBRATED (CUSTOM MATRIX)",
                    bg="#101b14",
                    fg=ACCENT_GREEN,
                    highlightbackground="#1b4322",
                )
            else:
                self._cal_status_lbl.configure(
                    text="● STATUS: DEFAULT DEAD-ZONE",
                    bg="#18181b",
                    fg=FG_SECONDARY,
                    highlightbackground="#27272a",
                )

    def _fire_change(self) -> None:
        self._settings.save()
        if self._on_change:
            self._on_change()
