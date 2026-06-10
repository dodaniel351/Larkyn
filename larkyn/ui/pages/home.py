"""Home page — live dictation dashboard.

Big start/stop control mirroring the global hotkey, quick pickers for profile
and output mode, session stats, and the most recent dictations.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    IndeterminateProgressRing,
    PrimaryPushButton,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
    TitleLabel,
)

from PySide6.QtGui import QPixmap

from larkyn.core.interfaces import OutputMode, PipelineState, Session
from larkyn.prompt.profiles import all_profiles
from larkyn.ui.context import UiContext
from larkyn.ui.icons import STATE_COLORS, asset_path, label_for_state

_MODE_LABELS = {
    OutputMode.PASTE.value: "Paste into active app",
    OutputMode.CLIPBOARD.value: "Copy to clipboard",
    OutputMode.DRAFT.value: "Draft (store only)",
}


class HomePage(QWidget):
    def __init__(self, ctx: UiContext, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("homePage")
        self._ctx = ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(14)
        emblem_file = asset_path("emblem_white.png") or asset_path("emblem.png")
        if emblem_file:
            emblem = BodyLabel("")
            emblem.setPixmap(QPixmap(emblem_file).scaled(
                48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header.addWidget(emblem)
        header.addWidget(TitleLabel("Larkyn"))
        header.addStretch(1)
        root.addLayout(header)
        sub = BodyLabel("Speak naturally. Get polished writing. 100% local.")
        root.addWidget(sub)

        # --- Dictation control card ------------------------------------
        control = CardWidget(self)
        cl = QVBoxLayout(control)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(12)

        status_row = QHBoxLayout()
        self._statusDot = BodyLabel("●")
        self._statusLabel = SubtitleLabel("Ready")
        self._spinner = IndeterminateProgressRing()
        self._spinner.setFixedSize(22, 22)
        self._spinner.hide()
        status_row.addWidget(self._statusDot)
        status_row.addWidget(self._statusLabel)
        status_row.addWidget(self._spinner)
        status_row.addStretch(1)
        cl.addLayout(status_row)

        self._toggleBtn = PrimaryPushButton(FluentIcon.MICROPHONE, "Start dictation")
        self._toggleBtn.setFixedHeight(44)
        self._toggleBtn.clicked.connect(ctx.orchestrator.toggle)
        cl.addWidget(self._toggleBtn)

        hint = CaptionLabel("")
        cl.addWidget(hint)
        self._hotkeyHint = hint
        self._update_hotkey_hint()
        root.addWidget(control)

        # --- Quick settings card ----------------------------------------
        quick = CardWidget(self)
        ql = QGridLayout(quick)
        ql.setContentsMargins(24, 18, 24, 18)
        ql.setHorizontalSpacing(28)
        ql.setVerticalSpacing(6)

        ql.addWidget(StrongBodyLabel("Writing profile"), 0, 0)
        self._profileBox = ComboBox()
        ql.addWidget(self._profileBox, 1, 0)

        ql.addWidget(StrongBodyLabel("Output"), 0, 1)
        self._modeBox = ComboBox()
        for mode, label in _MODE_LABELS.items():
            self._modeBox.addItem(label, userData=mode)
        ql.addWidget(self._modeBox, 1, 1)

        ql.addWidget(StrongBodyLabel("Raw mode"), 0, 2)
        self._rawSwitch = SwitchButton()
        self._rawSwitch.setChecked(ctx.config.output.raw_mode)
        ql.addWidget(self._rawSwitch, 1, 2)
        ql.setColumnStretch(0, 2)
        ql.setColumnStretch(1, 2)
        ql.setColumnStretch(2, 1)
        root.addWidget(quick)

        # --- Stats + recent ----------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(16)

        stats = CardWidget(self)
        sl = QVBoxLayout(stats)
        sl.setContentsMargins(24, 18, 24, 18)
        sl.addWidget(StrongBodyLabel("Statistics"))
        self._statTotal = BodyLabel("Dictations: –")
        self._statLast = BodyLabel("Last duration: –")
        self._statModel = CaptionLabel(f"Model: {ctx.config.llm.model}")
        sl.addWidget(self._statTotal)
        sl.addWidget(self._statLast)
        sl.addWidget(self._statModel)
        sl.addStretch(1)
        bottom.addWidget(stats, 1)

        recent = CardWidget(self)
        rl = QVBoxLayout(recent)
        rl.setContentsMargins(24, 18, 24, 18)
        rl.addWidget(StrongBodyLabel("Recent dictations"))
        self._recentLabels = [CaptionLabel("") for _ in range(4)]
        for lbl in self._recentLabels:
            lbl.setWordWrap(False)
            rl.addWidget(lbl)
        rl.addStretch(1)
        bottom.addWidget(recent, 2)

        root.addLayout(bottom)
        root.addStretch(1)

        # --- wiring -------------------------------------------------------
        self._reload_profiles()
        self._select_mode(ctx.config.output.mode)
        self._profileBox.currentIndexChanged.connect(self._on_profile)
        self._modeBox.currentIndexChanged.connect(self._on_mode)
        self._rawSwitch.checkedChanged.connect(self._on_raw)

        bus = ctx.bus
        bus.profileChanged.connect(self._sync_profile)
        bus.profilesEdited.connect(self._reload_profiles)
        bus.outputModeChanged.connect(self._select_mode)
        bus.rawModeChanged.connect(self._rawSwitch.setChecked)
        bus.hotkeyChanged.connect(lambda _hk: self._update_hotkey_hint())
        bus.llmChanged.connect(
            lambda: self._statModel.setText(f"Model: {self._ctx.config.llm.model}")
        )

        orch = ctx.orchestrator
        orch.stateChanged.connect(self.on_state)
        orch.finished.connect(self._on_finished)
        self.refresh()

    def _update_hotkey_hint(self) -> None:
        cfg = self._ctx.config.hotkey
        how = "hold to dictate, release to send" if cfg.mode == "hold" \
            else "press to start, press again to stop"
        self._hotkeyHint.setText(f"Global hotkey: {cfg.toggle}   •   {how}")

    # --- profile / mode helpers ---------------------------------------------
    def _reload_profiles(self) -> None:
        self._profileBox.blockSignals(True)
        self._profileBox.clear()
        for key, profile in all_profiles(self._ctx.config.custom_profiles).items():
            self._profileBox.addItem(profile.name, userData=key)
        self._sync_profile(self._ctx.orchestrator.profile_key)
        self._profileBox.blockSignals(False)

    def _sync_profile(self, key: str) -> None:
        for i in range(self._profileBox.count()):
            if self._profileBox.itemData(i) == key:
                self._profileBox.blockSignals(True)
                self._profileBox.setCurrentIndex(i)
                self._profileBox.blockSignals(False)
                return

    def _select_mode(self, mode: str) -> None:
        for i in range(self._modeBox.count()):
            if self._modeBox.itemData(i) == mode:
                self._modeBox.blockSignals(True)
                self._modeBox.setCurrentIndex(i)
                self._modeBox.blockSignals(False)
                return

    def _on_profile(self, index: int) -> None:
        key = self._profileBox.itemData(index)
        if not key:
            return
        self._ctx.orchestrator.set_profile(key)
        self._ctx.config.profile_default = key
        self._ctx.config.save()
        self._ctx.bus.profileChanged.emit(key)

    def _on_mode(self, index: int) -> None:
        mode = self._modeBox.itemData(index)
        if not mode:
            return
        self._ctx.orchestrator.set_output_mode(mode)
        self._ctx.config.save()
        self._ctx.bus.outputModeChanged.emit(mode)

    def _on_raw(self, checked: bool) -> None:
        self._ctx.orchestrator.set_raw_mode(checked)
        self._ctx.config.save()
        self._ctx.bus.rawModeChanged.emit(checked)

    # --- pipeline state -------------------------------------------------------
    def on_state(self, state: str) -> None:
        color = STATE_COLORS.get(state, "#3B82F6")
        self._statusDot.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._statusLabel.setText(label_for_state(state))
        busy = state in (
            PipelineState.TRANSCRIBING.value,
            PipelineState.REWRITING.value,
            PipelineState.DELIVERING.value,
        )
        self._spinner.setVisible(busy)
        if state == PipelineState.RECORDING.value:
            self._toggleBtn.setText("Stop && process")
            self._toggleBtn.setIcon(FluentIcon.PAUSE)
            self._toggleBtn.setEnabled(True)
        elif busy:
            self._toggleBtn.setText("Processing…")
            self._toggleBtn.setEnabled(False)
        else:
            self._toggleBtn.setText("Start dictation")
            self._toggleBtn.setIcon(FluentIcon.MICROPHONE)
            self._toggleBtn.setEnabled(True)

    def _on_finished(self, session: Session) -> None:
        self.refresh()

    def refresh(self) -> None:
        try:
            total = self._ctx.history.count()
            recent = self._ctx.history.recent(4)
        except Exception:
            return
        self._statTotal.setText(f"Dictations: {total}")
        if recent:
            self._statLast.setText(f"Last duration: {recent[0].duration_ms / 1000:.1f}s")
        for lbl, sess in zip(self._recentLabels, recent + [None] * 4):
            if sess is None:
                lbl.setText("")
            else:
                snippet = sess.rewritten.replace("\n", " ")
                if len(snippet) > 95:
                    snippet = snippet[:95] + "…"
                lbl.setText(f"{sess.timestamp[11:16]}  ·  {snippet}")
