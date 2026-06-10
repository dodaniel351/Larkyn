"""Logging configuration.

Writes to both the console (when present) and a rotating log file at
``%APPDATA%\\Larkyn\\larkyn.log``. The file handler is essential because
the app normally runs as a windowless tray process (pythonw), where there is no
console to print to.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from larkyn.config import app_data_dir

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> Path:
    global _CONFIGURED
    log_path = app_data_dir() / "larkyn.log"
    if _CONFIGURED:
        return log_path

    root = logging.getLogger("larkyn")
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    _CONFIGURED = True
    return log_path
