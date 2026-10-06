# Zero-Touch-Ctrl (HandCtrl)

**AI Air Mouse & Hand Gesture Controller for Windows**

Control your computer with hand gestures using your built-in webcam. Zero-Touch-Ctrl uses MediaPipe hand tracking to detect gestures and translates them into smooth mouse navigation, drag-and-drop, scrolling, and keyboard media controls.

All processing happens locally on device — zero cloud APIs, zero telemetry, no internet required after setup.

---

## Features

| Gesture | Action |
|---|---|
| ☝️ Index finger | Move cursor |
| 🤏 Pinch (thumb + index) | Left click |
| 🤏 Pinch + move | Drag & drop |
| ✌️ Two fingers (index + middle) | Scroll |
| ✋ Open palm | Pause gesture control |
| 👍 Thumbs up | Media play/pause |
| 👋 Swipe left/right | Previous/next track |
| ✋ Hold open palm (1s) | Emergency stop |

**Emergency hotkey:** `Ctrl + Alt + H` — instantly toggles gesture control on/off.

### 🏝️ Floating Dynamic Island HUD (Mini-Mode)
- **Minimalist Floating Pill:** Raycast / macOS Dynamic Island inspired widget docked at the top of your screen.
- **Real-Time Hand Skeleton Wireframe:** Dynamic 46x46 micro canvas rendering 21 articulated hand joints and glowing fingertips with auto-centering and scaling.
- **Always-on-Top & Draggable:** Freely drag and reposition the pill anywhere across multiple monitors.
- **Live Status Badges:** Dynamic emojis (☝️, 🤏, ✌️, ✋, 👍, 🖊️), confidence percentage, and state indicators.
- **Seamless Window Switching:** Click `🏝️ MINI HUD` to minimize the main window into the floating island, and click `⛶` to expand back to the full control panel at any time.
- **Quick Controls:** Direct ON/OFF toggle and clean exit (`✕`) right from the floating pill.

### 🖊️ Air Pen Mode (Optical Stylus & Writing Grip)
- **Use Any Physical Pen:** Hold any physical pen, stylus, marker, or pencil to navigate your cursor like a laser pointer.
- **1-Click Color Sampling:** Simply click on your pen tip in the live video feed to lock onto that exact pen's color!
- **Color Presets:** Fast one-click presets for `🔵 Blue`, `🔴 Red`, `🟢 Green`, and `🟡 Yellow` pens and caps.
- **AI Hand Writing Grip (Tripod Grip):** Senses natural pen-holding finger posture via MediaPipe. Squeezing thumb and index finger tighter triggers an immediate click/drag!
- **Zero-Jitter Spacebar Click:** Tap `Spacebar` with your non-dominant hand while holding the pen to click or draw in MS Paint / OneNote without disturbing pen aim.
- **Mode Toggle Hotkey:** Press `Ctrl + Alt + P` or click `🖐️ HAND MODE` / `🖊️ PEN MODE` to toggle instantly.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/koushik-ngd/Zero-Touch-Ctrl.git
cd Zero-Touch-Ctrl

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

> **Note:** The MediaPipe hand landmark model (`hand_landmarker.task`) is included in `handctrl/models/`. No additional downloads needed.

---

## Usage

```bash
python main.py
```

1. Click **START CAMERA** to begin the webcam feed
2. Click **ENABLE CONTROL** to activate gesture control
3. Use hand gestures to control your computer
4. Press `Ctrl + Alt + H` or click **DISABLE CONTROL** to stop

---

## Calibration

Click **CALIBRATE** in the settings panel to tailor HandCtrl to your comfortable hand movement range:
1. Move your index finger to the **top-left corner** of your desired movement zone and click **Capture Corner**
2. Move to the **top-right corner** and capture
3. Move to the **bottom-right corner** and capture
4. Move to the **bottom-left corner** and capture

HandCtrl calculates a perspective transformation matrix mapping your hand quadrilateral directly to screen coordinates. Settings persist in `calibration.json`. Click **Reset** to return to default dead-zone mapping.

---

## Project Structure

```
hand-gesture-control/
├── main.py                          # Entry point
├── requirements.txt                 # Dependencies
├── README.md
│
└── handctrl/
    ├── config.py                    # Configuration & settings
    ├── models/
    │   └── hand_landmarker.task     # MediaPipe model
    │
    ├── camera/
    │   ├── camera_manager.py        # Webcam capture (threaded)
    │   ├── hand_tracker.py          # MediaPipe hand tracking
    │   ├── pen_tracker.py           # Optical pen tip & AI writing grip tracker
    │   └── calibration.py           # 4-corner screen calibration
    │
    ├── gestures/
    │   ├── gesture_detector.py      # Gesture classification & state machine
    │   ├── gesture_state.py         # State enums & data classes
    │   └── gesture_utils.py         # Finger detection math
    │
    ├── control/
    │   ├── action_manager.py        # Event dispatcher
    │   ├── mouse_controller.py      # Mouse actions (move, click, drag, scroll)
    │   └── keyboard_controller.py   # Media key actions
    │
    ├── ui/
    │   ├── app.py                   # Main Tkinter application
    │   ├── hud_island.py            # Dynamic Island floating HUD widget
    │   ├── camera_panel.py          # Camera preview widget
    │   └── settings_panel.py        # Settings sliders
    │
    └── utils/
        ├── logger.py                # Local file logger
        ├── smoothing.py             # EMA position smoothing
        └── cooldown.py              # Action cooldown timer
```

---

## Safety

- Gesture control starts **DISABLED** by default
- `Ctrl + Alt + H` instantly toggles control
- Open palm for 1 second triggers emergency stop
- No actions fire when detection confidence is low
- Cursor jump protection prevents tracking glitches
- All mouse buttons released on disable/shutdown
- Camera disconnection auto-disables control

---

## Troubleshooting

### Camera not detected
- Check that no other application is using the webcam
- Try a different camera index in Settings
- Ensure camera permissions are granted in Windows Settings → Privacy → Camera

### MediaPipe fails to initialise
- Verify `handctrl/models/hand_landmarker.task` exists
- Reinstall: `pip install --force-reinstall mediapipe`

### Cursor jittery
- Increase cursor smoothing in Settings
- Ensure good lighting on your hand
- Keep your hand within the camera frame

### High CPU usage
- Close other camera applications
- Reduce camera resolution in `config.py`

---

## Privacy

Camera processing happens entirely on your local device. Hand tracking frames are **never** uploaded, stored, or transmitted. No analytics, no telemetry, no cloud services.

---

## Requirements

- Python 3.11+
- Windows 10/11
- Webcam
- Dependencies: OpenCV, MediaPipe, PyAutoGUI, NumPy, pynput, Pillow
