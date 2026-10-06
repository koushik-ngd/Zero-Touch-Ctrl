"""
Zero-Touch-Ctrl — Dynamic Island / Floating Minimalist Desktop HUD.

A sleek, semi-transparent, borderless, floating pill that docks at the top
of the user's screen (like macOS Dynamic Island / Raycast).
Features:
- Real-time micro wireframe hand skeleton preview (44x44 canvas)
- Dynamic gesture badge with emoji and state pill
- Always-on-top, draggable anywhere on the monitor
- Quick restore button to expand back to the full Control Panel
- Immediate visual feedback for Active, Paused, and Emergency Stop states
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional, Callable, List, Tuple
import numpy as np

# Palette (Zinc / Dark Modern)
HUD_BG = "#09090b"
PILL_SURFACE = "#18181b"
PILL_BORDER = "#27272a"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#71717a"
ACCENT_CYAN = "#38bdf8"
ACCENT_GREEN = "#22c55e"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"

# MediaPipe Hand Skeleton Bone Connections
HAND_CONNECTIONS: List[Tuple[int, int]] = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (0, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (0, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (0, 17), (17, 18), (18, 19), (19, 20),
    # Palm Base
    (5, 9), (9, 13), (13, 17),
]

GESTURE_EMOJIS = {
    "INDEX CURSOR": "☝️",
    "PINCH": "🤏",
    "DRAGGING": "🤏",
    "TWO FINGERS": "✌️",
    "OPEN PALM": "✋",
    "THUMBS UP": "👍",
    "GESTURE CONTROL PAUSED": "⏸️",
    "NONE": "💤",
}


class DynamicIslandHUD:
    """Floating borderless desktop widget showing live gesture status and mini skeleton."""

    def __init__(
        self,
        parent: tk.Tk,
        on_restore: Optional[Callable[[], None]] = None,
        on_toggle_control: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        self._parent = parent
        self._on_restore = on_restore
        self._on_toggle_control = on_toggle_control
        self._on_close = on_close

        self._window = tk.Toplevel(parent)
        self._window.title("Zero-Touch-Ctrl HUD")
        self._window.overrideredirect(True)  # Borderless window
        self._window.attributes("-topmost", True)  # Always on top
        self._window.configure(bg=HUD_BG)

        # Size & Positioning (Docked Top-Center by default)
        self._width = 390
        self._height = 54
        screen_w = self._window.winfo_screenwidth()
        start_x = (screen_w - self._width) // 2
        start_y = 18
        self._window.geometry(f"{self._width}x{self._height}+{start_x}+{start_y}")

        # Dragging support
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build_ui()
        self._bind_drag()

        # Start hidden until mini-mode is requested
        self._window.withdraw()

    def _build_ui(self) -> None:
        # Outer Pill Container with subtle border
        self._pill = tk.Frame(
            self._window,
            bg=PILL_SURFACE,
            highlightbackground=PILL_BORDER,
            highlightthickness=1,
            bd=0,
            cursor="fleur",  # Move cursor
        )
        self._pill.pack(fill="both", expand=True, padx=2, pady=2)

        # 1. Micro Hand Skeleton Canvas (Left)
        self._canvas_size = 46
        self._canvas = tk.Canvas(
            self._pill,
            width=self._canvas_size,
            height=self._canvas_size,
            bg="#0f0f11",
            highlightthickness=1,
            highlightbackground="#202024",
            bd=0,
        )
        self._canvas.pack(side="left", padx=(5, 8), pady=4)
        self._draw_empty_canvas()

        # 2. Gesture Info (Center)
        info_frame = tk.Frame(self._pill, bg=PILL_SURFACE)
        info_frame.pack(side="left", fill="y", pady=6)

        self._gesture_lbl = tk.Label(
            info_frame,
            text="☝️ CURSOR",
            bg=PILL_SURFACE,
            fg=TEXT_WHITE,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        self._gesture_lbl.pack(anchor="w")

        # Sub-status text (Confidence & State)
        self._sub_lbl = tk.Label(
            info_frame,
            text="● ACTIVE • 95%",
            bg=PILL_SURFACE,
            fg=ACCENT_GREEN,
            font=("Segoe UI", 8),
            anchor="w",
        )
        self._sub_lbl.pack(anchor="w")

        # 3. Action Buttons (Right)
        btn_frame = tk.Frame(self._pill, bg=PILL_SURFACE)
        btn_frame.pack(side="right", padx=(0, 8), pady=6)

        # Control Toggle Button (Pill button)
        self._ctrl_btn = tk.Button(
            btn_frame,
            text="ON",
            bg="#166534",
            fg=ACCENT_GREEN,
            activebackground="#14532d",
            activeforeground=TEXT_WHITE,
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=2,
            bd=0,
            command=self._handle_toggle_click,
        )
        self._ctrl_btn.pack(side="left", padx=(0, 6))

        # Restore Full Window Button (Square icon button)
        self._expand_btn = tk.Button(
            btn_frame,
            text="⛶",
            bg="#27272a",
            fg=TEXT_WHITE,
            activebackground="#3f3f46",
            activeforeground=TEXT_WHITE,
            font=("Segoe UI", 10),
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=0,
            bd=0,
            command=self._handle_restore_click,
        )
        self._expand_btn.pack(side="left")

        # Close Button
        self._close_btn = tk.Button(
            btn_frame,
            text="✕",
            bg="#27272a",
            fg=TEXT_MUTED,
            activebackground="#ef4444",
            activeforeground=TEXT_WHITE,
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=1,
            bd=0,
            command=self._handle_close_click,
        )
        self._close_btn.pack(side="left", padx=(4, 0))

    def _bind_drag(self) -> None:
        """Allow dragging the Island anywhere on screen by clicking background."""
        for widget in (self._pill, self._gesture_lbl, self._sub_lbl):
            widget.bind("<Button-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_dragging)

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_dragging(self, event: tk.Event) -> None:
        x = self._window.winfo_x() + (event.x - self._drag_start_x)
        y = self._window.winfo_y() + (event.y - self._drag_start_y)
        self._window.geometry(f"+{x}+{y}")

    def _handle_restore_click(self) -> None:
        if self._on_restore:
            self._on_restore()

    def _handle_toggle_click(self) -> None:
        if self._on_toggle_control:
            self._on_toggle_control()

    def _handle_close_click(self) -> None:
        if self._on_close:
            self._on_close()

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------
    def show(self) -> None:
        """Display the HUD window."""
        self._window.deiconify()
        self._window.lift()

    def hide(self) -> None:
        """Hide the HUD window."""
        self._window.withdraw()

    @property
    def is_visible(self) -> bool:
        return self._window.winfo_viewable() == 1

    # ------------------------------------------------------------------
    # Live Updates
    # ------------------------------------------------------------------
    def update_hud(
        self,
        gesture_name: str,
        state_name: str,
        confidence: float,
        control_enabled: bool,
        landmarks: Optional[np.ndarray] = None,
    ) -> None:
        """
        Update the floating HUD display with real-time tracking data.
        Must be called on the main UI thread.
        """
        # 1. Update Gesture Text & Emoji
        emoji = GESTURE_EMOJIS.get(gesture_name, "👋")
        display_name = gesture_name.replace("INDEX_CURSOR", "CURSOR").replace("TWO_FINGERS", "SCROLL")
        self._gesture_lbl.configure(text=f"{emoji} {display_name}")

        # 2. Update Status & Subtitle
        if not control_enabled:
            self._sub_lbl.configure(text="● DISABLED", fg=ACCENT_RED)
            self._ctrl_btn.configure(text="OFF", bg="#451a1a", fg=ACCENT_RED)
        elif state_name == "PAUSED":
            self._sub_lbl.configure(text="● PAUSED (PALM)", fg=ACCENT_AMBER)
            self._ctrl_btn.configure(text="PAUSE", bg="#45311a", fg=ACCENT_AMBER)
        else:
            conf_pct = int(confidence * 100)
            self._sub_lbl.configure(text=f"● {state_name} • {conf_pct}%", fg=ACCENT_GREEN)
            self._ctrl_btn.configure(text="ON", bg="#166534", fg=ACCENT_GREEN)

        # 3. Draw Micro Wireframe Skeleton
        self._draw_hand_skeleton(landmarks)

    def _draw_empty_canvas(self) -> None:
        self._canvas.delete("all")
        # Draw placeholder dot
        mid = self._canvas_size // 2
        self._canvas.create_oval(mid - 3, mid - 3, mid + 3, mid + 3, fill="#27272a", outline="")

    def _draw_hand_skeleton(self, landmarks: Optional[np.ndarray]) -> None:
        self._canvas.delete("all")
        if landmarks is None or len(landmarks) < 21:
            self._draw_empty_canvas()
            return

        # Auto-center and scale hand skeleton to fit canvas beautifully
        min_x = float(np.min(landmarks[:, 0]))
        max_x = float(np.max(landmarks[:, 0]))
        min_y = float(np.min(landmarks[:, 1]))
        max_y = float(np.max(landmarks[:, 1]))

        span_x = max_x - min_x
        span_y = max_y - min_y
        span = max(span_x, span_y, 0.08)

        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0

        margin = 6
        scale = self._canvas_size - (margin * 2)

        pts = []
        for i in range(21):
            norm_x = (landmarks[i, 0] - center_x) / span + 0.5
            norm_y = (landmarks[i, 1] - center_y) / span + 0.5
            px = margin + int(np.clip(norm_x, 0.0, 1.0) * scale)
            py = margin + int(np.clip(norm_y, 0.0, 1.0) * scale)
            pts.append((px, py))

        # Draw bones
        for a, b in HAND_CONNECTIONS:
            x1, y1 = pts[a]
            x2, y2 = pts[b]
            self._canvas.create_line(x1, y1, x2, y2, fill="#0284c7", width=1.5)

        # Draw joints
        for i, (px, py) in enumerate(pts):
            # Fingertips (4, 8, 12, 16, 20) highlighted in glowing cyan/green
            if i in (4, 8, 12, 16, 20):
                r = 2.5
                color = ACCENT_CYAN if i == 8 else ACCENT_GREEN
            else:
                r = 1.2
                color = "#94a3b8"
            self._canvas.create_oval(px - r, py - r, px + r, py + r, fill=color, outline="")
