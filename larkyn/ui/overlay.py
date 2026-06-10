"""A small floating status overlay (recording / processing indicator).

It is a frameless, always-on-top, **non-activating** window so the user's
target application keeps keyboard focus — critical for auto-paste to land in
the right place. It appears near the bottom-center of the primary screen while
the pipeline is active and hides when idle.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from larkyn.core.interfaces import PipelineState
from larkyn.ui.icons import STATE_COLORS, label_for_state

_VISIBLE_STATES = {
    PipelineState.RECORDING.value,
    PipelineState.TRANSCRIBING.value,
    PipelineState.REWRITING.value,
    PipelineState.DELIVERING.value,
}


class RecordingOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        try:
            self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
        except Exception:
            pass
        self.setFocusPolicy(Qt.NoFocus)

        card = QFrame(self)
        card.setObjectName("card")
        self._dot = QLabel(card)
        self._dot.setFixedSize(12, 12)
        self._text = QLabel("Ready", card)
        self._text.setObjectName("text")

        inner = QHBoxLayout(card)
        inner.setContentsMargins(16, 10, 18, 10)
        inner.setSpacing(10)
        inner.addWidget(self._dot)
        inner.addWidget(self._text)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        self.setStyleSheet(
            """
            #card { background-color: rgba(28, 28, 30, 235); border-radius: 16px; }
            #text { color: #F2F2F7; font-size: 13px; font-weight: 600;
                    font-family: 'Segoe UI', sans-serif; }
            """
        )
        self._set_dot_color(STATE_COLORS[PipelineState.IDLE.value])

    def _set_dot_color(self, color: str) -> None:
        self._dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.adjustSize()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + int(geo.height() * 0.86) - self.height()
        self.move(x, y)

    def on_state(self, state: str) -> None:
        if state in _VISIBLE_STATES:
            self._set_dot_color(STATE_COLORS.get(state, "#3B82F6"))
            self._text.setText(label_for_state(state))
            self._reposition()
            if not self.isVisible():
                self.show()
        else:
            self.hide()
