"""
HandCtrl — Lightweight local logger.

Logs application events to a local file. Never logs images or webcam data.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOGGER_NAME = "handctrl"
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Return the singleton HandCtrl logger, creating it on first call."""
    global _logger
    if _logger is not None:
        return _logger

    from handctrl.config import LOG_FILE

    _logger = logging.getLogger(_LOGGER_NAME)
    _logger.setLevel(logging.DEBUG)

    # File handler — append mode, UTF-8
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # Console handler — INFO and above
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:
            pass

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    _logger.addHandler(fh)
    _logger.addHandler(ch)
    return _logger
