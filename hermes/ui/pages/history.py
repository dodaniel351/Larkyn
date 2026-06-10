"""History page — search and browse past dictations (SQLite + FTS5)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    ListWidget,
    PushButton,
    SearchLineEdit,
    SegmentedWidget,
    TextEdit,
    TitleLabel,
)

from hermes.core.interfaces import Session
from hermes.ui.context import UiContext


class HistoryPage(QWidget):
    def __init__(self, ctx: UiContext, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("historyPage")
        self._ctx = ctx
        self._sessions: list[Session] = []
        self._current: Session | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(12)
        root.addWidget(TitleLabel("History"))

        self._search = SearchLineEdit()
        self._search.setPlaceholderText("Search dictations…")
        self._search.textChanged.connect(self._reload)
        root.addWidget(self._search)

        body = QHBoxLayout()
        body.setSpacing(16)

        self._list = ListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        body.addWidget(self._list, 2)

        right = QVBoxLayout()
        right.setSpacing(8)
        self._meta = CaptionLabel("")
        right.addWidget(self._meta)

        self._pivot = SegmentedWidget()
        self._pivot.addItem("polished", "Polished")
        self._pivot.addItem("raw", "Raw transcript")
        self._pivot.setCurrentItem("polished")
        self._pivot.currentItemChanged.connect(lambda _k: self._show_text())
        right.addWidget(self._pivot)

        self._text = TextEdit()
        self._text.setReadOnly(True)
        right.addWidget(self._text, 1)

        btns = QHBoxLayout()
        self._copyBtn = PushButton(FluentIcon.COPY, "Copy")
        self._copyBtn.clicked.connect(self._copy)
        self._deleteBtn = PushButton(FluentIcon.DELETE, "Delete")
        self._deleteBtn.clicked.connect(self._delete)
        btns.addWidget(self._copyBtn)
        btns.addWidget(self._deleteBtn)
        btns.addStretch(1)
        right.addLayout(btns)

        body.addLayout(right, 3)
        root.addLayout(body, 1)

        ctx.orchestrator.finished.connect(lambda _s: self._reload())
        self._reload()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._reload()

    # ------------------------------------------------------------------
    def _reload(self) -> None:
        query = self._search.text().strip()
        try:
            self._sessions = (
                self._ctx.history.search(query, 200) if query
                else self._ctx.history.recent(200)
            )
        except Exception:
            self._sessions = []
        self._list.blockSignals(True)
        self._list.clear()
        for sess in self._sessions:
            snippet = sess.rewritten.replace("\n", " ")
            if len(snippet) > 60:
                snippet = snippet[:60] + "…"
            item = QListWidgetItem(f"{sess.timestamp[:16].replace('T', '  ')}\n{snippet}")
            self._list.addItem(item)
        self._list.blockSignals(False)
        if self._sessions:
            self._list.setCurrentRow(0)
        else:
            self._current = None
            self._meta.setText("No dictations found.")
            self._text.setPlainText("")

    def _on_select(self, row: int) -> None:
        if 0 <= row < len(self._sessions):
            self._current = self._sessions[row]
            sess = self._current
            self._meta.setText(
                f"{sess.timestamp.replace('T', ' ')}   ·   profile: {sess.profile}   ·   "
                f"model: {sess.model}   ·   {sess.duration_ms / 1000:.1f}s   ·   {sess.output_mode}"
            )
            self._show_text()

    def _show_text(self) -> None:
        if self._current is None:
            return
        raw_view = self._pivot.currentRouteKey() == "raw"
        self._text.setPlainText(
            self._current.raw_transcript if raw_view else self._current.rewritten
        )

    def _copy(self) -> None:
        if self._current is None:
            return
        import pyperclip

        pyperclip.copy(self._text.toPlainText())
        InfoBar.success(
            "Copied", "Text copied to clipboard.", duration=2000,
            position=InfoBarPosition.TOP, parent=self,
        )

    def _delete(self) -> None:
        if self._current is None or self._current.id is None:
            return
        self._ctx.history.delete(self._current.id)
        self._reload()
