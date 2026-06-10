"""Vocabulary page — personal dictionary of terms that must never be altered."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    LineEdit,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    TitleLabel,
)

from hermes.prompt.vocabulary import normalize_terms
from hermes.ui.context import UiContext


class VocabularyPage(QWidget):
    def __init__(self, ctx: UiContext, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("vocabularyPage")
        self._ctx = ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(12)
        root.addWidget(TitleLabel("Personal vocabulary"))
        root.addWidget(BodyLabel(
            "Product names, jargon, and acronyms listed here are always preserved exactly — "
            "mis-hearings are corrected back to your spelling."
        ))

        row = QHBoxLayout()
        self._input = LineEdit()
        self._input.setPlaceholderText("Add a term, e.g. eClinicalWorks")
        self._input.returnPressed.connect(self._add)
        self._addBtn = PrimaryPushButton(FluentIcon.ADD, "Add")
        self._addBtn.clicked.connect(self._add)
        row.addWidget(self._input, 1)
        row.addWidget(self._addBtn)
        root.addLayout(row)

        self._list = ListWidget()
        root.addWidget(self._list, 1)

        self._removeBtn = PushButton(FluentIcon.DELETE, "Remove selected")
        self._removeBtn.clicked.connect(self._remove)
        root.addWidget(self._removeBtn)

        self._reload()

    def _reload(self) -> None:
        self._list.clear()
        for term in self._ctx.config.vocabulary:
            self._list.addItem(QListWidgetItem(term))

    def _persist(self, terms: list[str]) -> None:
        self._ctx.config.vocabulary = normalize_terms(terms)
        self._ctx.config.save()
        self._ctx.bus.vocabularyEdited.emit()
        self._reload()

    def _add(self) -> None:
        term = self._input.text().strip()
        if not term:
            return
        self._persist(self._ctx.config.vocabulary + [term])
        self._input.clear()
        self._input.setFocus()

    def _remove(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        terms = [t for t in self._ctx.config.vocabulary if t != item.text()]
        self._persist(terms)
