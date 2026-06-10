"""Profiles page — view built-in writing profiles, manage custom ones.

All profiles use the same model; they differ only in prompt guidance. Built-ins
are read-only; custom profiles are stored in config and editable here.
"""

from __future__ import annotations

import re

from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    TextEdit,
    TitleLabel,
)

from larkyn.prompt.profiles import BUILTIN_PROFILES, all_profiles
from larkyn.ui.context import UiContext


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "custom"


class ProfilesPage(QWidget):
    def __init__(self, ctx: UiContext, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("profilesPage")
        self._ctx = ctx
        self._keys: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(12)
        root.addWidget(TitleLabel("Writing profiles"))
        root.addWidget(BodyLabel(
            "Profiles change how your speech is rewritten — same model, different instructions."
        ))

        body = QHBoxLayout()
        body.setSpacing(16)

        left = QVBoxLayout()
        self._list = ListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list, 1)

        lbtns = QHBoxLayout()
        self._addBtn = PushButton(FluentIcon.ADD, "New")
        self._addBtn.clicked.connect(self._add)
        self._delBtn = PushButton(FluentIcon.DELETE, "Delete")
        self._delBtn.clicked.connect(self._delete)
        lbtns.addWidget(self._addBtn)
        lbtns.addWidget(self._delBtn)
        left.addLayout(lbtns)
        body.addLayout(left, 2)

        right = QVBoxLayout()
        right.setSpacing(8)
        self._nameEdit = LineEdit()
        self._nameEdit.setPlaceholderText("Profile name")
        right.addWidget(self._nameEdit)
        self._badge = CaptionLabel("")
        right.addWidget(self._badge)
        self._guidance = TextEdit()
        self._guidance.setPlaceholderText(
            "Guidance appended to the base rewriting prompt, e.g.\n"
            "“Write as a friendly Slack message. Keep it casual and brief.”"
        )
        right.addWidget(self._guidance, 1)
        self._saveBtn = PrimaryPushButton(FluentIcon.SAVE, "Save profile")
        self._saveBtn.clicked.connect(self._save)
        right.addWidget(self._saveBtn)
        body.addLayout(right, 3)

        root.addLayout(body, 1)
        self._reload()

    # ------------------------------------------------------------------
    def _reload(self, select_key: str | None = None) -> None:
        profiles = all_profiles(self._ctx.config.custom_profiles)
        self._keys = list(profiles.keys())
        self._list.blockSignals(True)
        self._list.clear()
        for key in self._keys:
            suffix = "" if key in BUILTIN_PROFILES else "   (custom)"
            self._list.addItem(QListWidgetItem(profiles[key].name + suffix))
        self._list.blockSignals(False)
        row = self._keys.index(select_key) if select_key in self._keys else 0
        self._list.setCurrentRow(row)

    def _on_select(self, row: int) -> None:
        if not (0 <= row < len(self._keys)):
            return
        key = self._keys[row]
        profile = all_profiles(self._ctx.config.custom_profiles)[key]
        builtin = key in BUILTIN_PROFILES
        self._nameEdit.setText(profile.name)
        self._guidance.setPlainText(profile.guidance)
        self._nameEdit.setReadOnly(builtin)
        self._guidance.setReadOnly(builtin)
        self._saveBtn.setEnabled(not builtin)
        self._delBtn.setEnabled(not builtin)
        self._badge.setText(
            "Built-in profile (read-only)." if builtin
            else "Custom profile — edit freely."
        )

    def _add(self) -> None:
        base = "My profile"
        key = _slug(base)
        n = 2
        existing = set(BUILTIN_PROFILES) | set(self._ctx.config.custom_profiles)
        while key in existing:
            key = _slug(f"{base} {n}")
            n += 1
        self._ctx.config.custom_profiles[key] = ""
        self._ctx.config.save()
        self._ctx.bus.profilesEdited.emit()
        self._reload(select_key=key)
        self._nameEdit.setFocus()

    def _save(self) -> None:
        row = self._list.currentRow()
        if not (0 <= row < len(self._keys)):
            return
        old_key = self._keys[row]
        if old_key in BUILTIN_PROFILES:
            return
        new_key = _slug(self._nameEdit.text())
        guidance = self._guidance.toPlainText().strip()
        cp = self._ctx.config.custom_profiles
        if new_key != old_key:
            cp.pop(old_key, None)
            if self._ctx.config.profile_default == old_key:
                self._ctx.config.profile_default = new_key
            if self._ctx.orchestrator.profile_key == old_key:
                self._ctx.orchestrator.set_profile(new_key)
        cp[new_key] = guidance
        self._ctx.config.save()
        self._ctx.bus.profilesEdited.emit()
        self._reload(select_key=new_key)
        InfoBar.success("Saved", "Profile saved.", duration=2000,
                        position=InfoBarPosition.TOP, parent=self)

    def _delete(self) -> None:
        row = self._list.currentRow()
        if not (0 <= row < len(self._keys)):
            return
        key = self._keys[row]
        if key in BUILTIN_PROFILES:
            return
        self._ctx.config.custom_profiles.pop(key, None)
        if self._ctx.config.profile_default == key:
            self._ctx.config.profile_default = "general"
        if self._ctx.orchestrator.profile_key == key:
            self._ctx.orchestrator.set_profile("general")
            self._ctx.bus.profileChanged.emit("general")
        self._ctx.config.save()
        self._ctx.bus.profilesEdited.emit()
        self._reload()
