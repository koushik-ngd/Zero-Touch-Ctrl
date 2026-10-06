"""
HandCtrl — Gesture utility functions.

Pure-math helpers for determining finger states, distances, and angles
from the 21-landmark hand array. No side effects, no state.
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# MediaPipe Hand Landmark indices
# ---------------------------------------------------------------------------
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20


def distance_2d(lm: np.ndarray, a: int, b: int) -> float:
    """Euclidean distance between two landmarks (x, y only)."""
    return float(np.linalg.norm(lm[a, :2] - lm[b, :2]))


def distance_3d(lm: np.ndarray, a: int, b: int) -> float:
    """Euclidean distance between two landmarks (x, y, z)."""
    return float(np.linalg.norm(lm[a] - lm[b]))


# ---------------------------------------------------------------------------
# Finger extension detection
# ---------------------------------------------------------------------------
def is_finger_extended(lm: np.ndarray, tip: int, dip: int, pip_: int, mcp: int) -> bool:
    """
    Check if a finger is extended.

    A finger is extended when its tip is farther from the wrist
    than its PIP joint, and the tip-to-MCP distance exceeds
    the PIP-to-MCP distance.
    """
    tip_to_mcp = distance_2d(lm, tip, mcp)
    pip_to_mcp = distance_2d(lm, pip_, mcp)
    tip_to_wrist = distance_2d(lm, tip, WRIST)
    pip_to_wrist = distance_2d(lm, pip_, WRIST)
    return tip_to_mcp > pip_to_mcp and tip_to_wrist > pip_to_wrist


def is_thumb_extended(lm: np.ndarray) -> bool:
    """
    Check if the thumb is extended.

    Uses the distance of thumb tip from index MCP versus
    thumb IP from index MCP — if tip is farther, thumb is out.
    """
    tip_dist = distance_2d(lm, THUMB_TIP, INDEX_MCP)
    ip_dist = distance_2d(lm, THUMB_IP, INDEX_MCP)
    return tip_dist > ip_dist


def get_finger_states(lm: np.ndarray) -> dict[str, bool]:
    """
    Return the extended/folded state of all five fingers.

    Returns:
        dict with keys: thumb, index, middle, ring, pinky
    """
    return {
        "thumb": is_thumb_extended(lm),
        "index": is_finger_extended(lm, INDEX_TIP, INDEX_DIP, INDEX_PIP, INDEX_MCP),
        "middle": is_finger_extended(lm, MIDDLE_TIP, MIDDLE_DIP, MIDDLE_PIP, MIDDLE_MCP),
        "ring": is_finger_extended(lm, RING_TIP, RING_DIP, RING_PIP, RING_MCP),
        "pinky": is_finger_extended(lm, PINKY_TIP, PINKY_DIP, PINKY_PIP, PINKY_MCP),
    }


# ---------------------------------------------------------------------------
# Gesture-specific helpers
# ---------------------------------------------------------------------------
def pinch_distance(lm: np.ndarray) -> float:
    """Distance between thumb tip and index tip (normalised coords)."""
    return distance_2d(lm, THUMB_TIP, INDEX_TIP)


def is_thumbs_up(lm: np.ndarray) -> bool:
    """
    Detect thumbs-up: thumb extended upward, other fingers folded.

    The thumb tip must be above (lower y) the thumb MCP,
    and the thumb must be the only extended digit.
    """
    states = get_finger_states(lm)
    thumb_up = states["thumb"] and lm[THUMB_TIP, 1] < lm[THUMB_MCP, 1]
    others_folded = not any(states[f] for f in ("index", "middle", "ring", "pinky"))
    return thumb_up and others_folded


def is_open_palm(lm: np.ndarray) -> bool:
    """All five fingers extended (or 4 main fingers extended with thumb spread)."""
    states = get_finger_states(lm)
    four_fingers = (
        states["index"]
        and states["middle"]
        and states["ring"]
        and states["pinky"]
    )
    if not four_fingers:
        return False
    return states["thumb"] or (pinch_distance(lm) > 0.08)


def is_index_only(lm: np.ndarray) -> bool:
    """Only the index finger is extended."""
    states = get_finger_states(lm)
    return (
        states["index"]
        and not states["middle"]
        and not states["ring"]
        and not states["pinky"]
    )


def is_two_fingers(lm: np.ndarray) -> bool:
    """Index and middle fingers extended, others folded."""
    states = get_finger_states(lm)
    return (
        states["index"]
        and states["middle"]
        and not states["ring"]
        and not states["pinky"]
    )


def index_tip_position(lm: np.ndarray) -> tuple[float, float]:
    """Return (x, y) of index fingertip in normalised coordinates."""
    return float(lm[INDEX_TIP, 0]), float(lm[INDEX_TIP, 1])


def hand_center(lm: np.ndarray) -> tuple[float, float]:
    """Return the average (x, y) of all landmarks — rough hand centre."""
    return float(lm[:, 0].mean()), float(lm[:, 1].mean())
