"""Programmatically drawn microphone tray icons (no asset files needed).

The icon is tinted by pipeline state so the tray reflects what Larkyn is doing.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from larkyn.core.interfaces import PipelineState

STATE_COLORS: dict[str, str] = {
    PipelineState.IDLE.value: "#3B82F6",          # blue — ready
    PipelineState.RECORDING.value: "#EF4444",     # red — recording
    PipelineState.TRANSCRIBING.value: "#F59E0B",  # amber — working
    PipelineState.REWRITING.value: "#F59E0B",
    PipelineState.DELIVERING.value: "#10B981",    # green — delivering
    PipelineState.ERROR.value: "#9CA3AF",         # gray — error/idle-fallback
}

STATE_LABELS: dict[str, str] = {
    PipelineState.IDLE.value: "Ready",
    PipelineState.RECORDING.value: "Recording…",
    PipelineState.TRANSCRIBING.value: "Transcribing…",
    PipelineState.REWRITING.value: "Rewriting…",
    PipelineState.DELIVERING.value: "Pasting…",
    PipelineState.ERROR.value: "Error",
}


def _mic_pixmap(color: str, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)

    # Mic capsule
    body_w = size * 0.34
    body_h = size * 0.46
    bx = (size - body_w) / 2
    by = size * 0.12
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    p.drawRoundedRect(QRectF(bx, by, body_w, body_h), body_w / 2, body_w / 2)

    # Cradle arc + stand
    pen = QPen(c)
    pen.setWidthF(size * 0.075)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(size * 0.24, size * 0.30, size * 0.52, size * 0.50), 200 * 16, 140 * 16)
    p.drawLine(QPointF(size / 2, size * 0.80), QPointF(size / 2, size * 0.90))
    p.drawLine(QPointF(size * 0.38, size * 0.90), QPointF(size * 0.62, size * 0.90))
    p.end()
    return pm


def icon_for_state(state: str) -> QIcon:
    return QIcon(_mic_pixmap(STATE_COLORS.get(state, STATE_COLORS[PipelineState.IDLE.value])))


def asset_path(name: str) -> str | None:
    """Resolve a file in the assets dir (source tree or PyInstaller bundle)."""
    import os
    import sys

    bases = []
    if getattr(sys, "frozen", False):  # PyInstaller
        bases.append(os.path.join(os.path.dirname(sys.executable), "assets"))
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.append(os.path.join(meipass, "assets"))
    bases.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "assets"))
    for base in bases:
        path = os.path.join(base, name)
        if os.path.exists(path):
            return path
    return None


def app_icon() -> QIcon:
    """The branded application icon (assets/larkyn.ico), with fallback."""
    path = asset_path("larkyn.ico")
    if path:
        return QIcon(path)
    return icon_for_state(PipelineState.IDLE.value)


def label_for_state(state: str) -> str:
    return STATE_LABELS.get(state, "Ready")
