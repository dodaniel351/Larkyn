"""Settings page — full configuration UI with live apply.

Changes are written to config.json and broadcast on the signal bus so the
running pipeline (LLM provider, Whisper engine, hotkey listener, theme) is
rebuilt immediately — no restart needed.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
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
    DoubleSpinBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SpinBox,
    StrongBodyLabel,
    SwitchButton,
    TitleLabel,
)

from larkyn.hotkey import parse_hotkey
from larkyn.ui.context import UiContext

_WHISPER_MODELS = [
    "large-v3-turbo", "distil-large-v3", "large-v3", "medium", "small", "base", "tiny",
]
_QT_MOD_MAP = [
    (Qt.ControlModifier, "<ctrl>"),
    (Qt.AltModifier, "<alt>"),
    (Qt.ShiftModifier, "<shift>"),
    (Qt.MetaModifier, "<cmd>"),
]
_QT_KEY_NAMES = {
    Qt.Key_Space: "<space>", Qt.Key_Return: "<enter>", Qt.Key_Enter: "<enter>",
    Qt.Key_Tab: "<tab>", Qt.Key_Escape: "<esc>",
}


_QT_MOD_KEYS = {
    Qt.Key_Control: "<ctrl>",
    Qt.Key_Alt: "<alt>",
    Qt.Key_Shift: "<shift>",
    Qt.Key_Meta: "<cmd>",  # Windows key
}


class HotkeyEdit(LineEdit):
    """Click, then press the desired combination — it is captured directly.

    Supports modifier-only combos (e.g. Ctrl+Win): hold the modifiers and
    release — the combo is committed on release. Pressing a regular key while
    modifiers are held commits modifiers+key immediately.
    """

    def __init__(self, spec: str, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._value = spec
        self._held: list[str] = []   # modifiers currently held, in press order
        self._committed = True       # current hold already produced a combo?
        self.setText(spec)
        self.setPlaceholderText("Click here, then press keys…")

    # --- capture -------------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.isAutoRepeat():
            return
        key = event.key()
        if key in _QT_MOD_KEYS:
            name = _QT_MOD_KEYS[key]
            if name not in self._held:
                self._held.append(name)
            self._committed = False
            self.setText("+".join(self._held) + " + …")  # live preview
            return
        if key == Qt.Key_unknown:
            return
        # A regular key commits modifiers+key.
        parts = [name for mod, name in _QT_MOD_MAP if event.modifiers() & mod]
        if key in _QT_KEY_NAMES:
            parts.append(_QT_KEY_NAMES[key])
        elif Qt.Key_F1 <= key <= Qt.Key_F24:
            parts.append(f"<f{key - Qt.Key_F1 + 1}>")
        else:
            text = QKeySequence(key).toString().lower()
            if not text or len(text) > 1:
                return
            parts.append(text)
        # Require a modifier unless it's a function key.
        if len(parts) >= 2 or parts[-1].startswith("<f"):
            self._commit("+".join(parts))

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.isAutoRepeat():
            return
        key = event.key()
        if key in _QT_MOD_KEYS:
            # Releasing a modifier with ≥2 held and nothing committed yet
            # -> commit the modifier-only combo (e.g. <ctrl>+<cmd>).
            if not self._committed and len(self._held) >= 2:
                self._commit("+".join(self._held))
            name = _QT_MOD_KEYS[key]
            if name in self._held:
                self._held.remove(name)
            if not self._held and not self._committed:
                self.setText(self._value)  # abandoned single-modifier press
                self._committed = True

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self._held = []
        if not self._committed:
            self.setText(self._value)
            self._committed = True

    def _commit(self, spec: str) -> None:
        self._value = spec
        self._committed = True
        self.setText(spec)


def _card(title: str, caption: str = "") -> tuple[CardWidget, QGridLayout]:
    card = CardWidget()
    outer = QVBoxLayout(card)
    outer.setContentsMargins(24, 18, 24, 18)
    outer.setSpacing(10)
    outer.addWidget(StrongBodyLabel(title))
    if caption:
        cap = CaptionLabel(caption)
        cap.setWordWrap(True)
        outer.addWidget(cap)
    grid = QGridLayout()
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(10)
    outer.addLayout(grid)
    return card, grid


class SettingsPage(ScrollArea):
    def __init__(self, ctx: UiContext, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._ctx = ctx
        cfg = ctx.config

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(16)
        root.addWidget(TitleLabel("Settings"))

        # --- AI model ------------------------------------------------------
        ai_card, ai = _card(
            "AI model",
            "The rewriting engine. The native Ollama provider supports disabling "
            "model 'thinking' for sub-second rewrites; any OpenAI-compatible "
            "server also works.",
        )
        ai.addWidget(BodyLabel("Provider"), 0, 0)
        self._provider = ComboBox()
        self._provider.addItem("Ollama (native, recommended)", userData="ollama")
        self._provider.addItem("OpenAI-compatible", userData="openai")
        self._provider.setCurrentIndex(0 if cfg.llm.provider == "ollama" else 1)
        ai.addWidget(self._provider, 0, 1)

        ai.addWidget(BodyLabel("Endpoint"), 1, 0)
        self._endpoint = LineEdit()
        self._endpoint.setText(cfg.llm.endpoint)
        ai.addWidget(self._endpoint, 1, 1)

        ai.addWidget(BodyLabel("Model"), 2, 0)
        self._model = LineEdit()
        self._model.setText(cfg.llm.model)
        ai.addWidget(self._model, 2, 1)

        ai.addWidget(BodyLabel("Temperature"), 3, 0)
        self._temp = DoubleSpinBox()
        self._temp.setRange(0.0, 2.0)
        self._temp.setSingleStep(0.1)
        self._temp.setValue(cfg.llm.temperature)
        ai.addWidget(self._temp, 3, 1)

        ai.addWidget(BodyLabel("Top-P"), 4, 0)
        self._topP = DoubleSpinBox()
        self._topP.setRange(0.0, 1.0)
        self._topP.setSingleStep(0.05)
        self._topP.setValue(cfg.llm.top_p)
        ai.addWidget(self._topP, 4, 1)

        ai.addWidget(BodyLabel("Max tokens"), 5, 0)
        self._maxTokens = SpinBox()
        self._maxTokens.setRange(64, 32768)
        self._maxTokens.setValue(cfg.llm.max_tokens)
        ai.addWidget(self._maxTokens, 5, 1)

        ai.addWidget(BodyLabel("Model thinking (slower, reasoning models only)"), 6, 0)
        self._think = SwitchButton()
        self._think.setChecked(cfg.llm.think)
        ai.addWidget(self._think, 6, 1)

        self._testBtn = PushButton(FluentIcon.SYNC, "Test connection")
        self._testBtn.clicked.connect(self._test_connection)
        ai.addWidget(self._testBtn, 7, 1)
        root.addWidget(ai_card)

        # --- Speech recognition ---------------------------------------------
        stt_card, stt = _card(
            "Speech recognition",
            "Local Whisper (faster-whisper). GPU is used automatically when available.",
        )
        stt.addWidget(BodyLabel("Whisper model"), 0, 0)
        self._whisperModel = ComboBox()
        for m in _WHISPER_MODELS:
            self._whisperModel.addItem(m)
        if cfg.stt.model in _WHISPER_MODELS:
            self._whisperModel.setCurrentIndex(_WHISPER_MODELS.index(cfg.stt.model))
        stt.addWidget(self._whisperModel, 0, 1)

        stt.addWidget(BodyLabel("Device"), 1, 0)
        self._device = ComboBox()
        for d in ("auto", "cuda", "cpu"):
            self._device.addItem(d)
        self._device.setCurrentText(cfg.stt.device)
        stt.addWidget(self._device, 1, 1)
        root.addWidget(stt_card)

        # --- Hotkey -----------------------------------------------------------
        hk_card, hk = _card(
            "Global hotkey",
            "Works from any application. Click the box, then press the combination "
            "you want — modifier-only combos work too (e.g. hold Ctrl + Windows "
            "and release).",
        )
        hk.addWidget(BodyLabel("Dictation hotkey"), 0, 0)
        self._hotkey = HotkeyEdit(cfg.hotkey.toggle)
        hk.addWidget(self._hotkey, 0, 1)

        hk.addWidget(BodyLabel("Behavior"), 1, 0)
        self._hotkeyMode = ComboBox()
        self._hotkeyMode.addItem("Hold to talk — record while held, process on release",
                                 userData="hold")
        self._hotkeyMode.addItem("Toggle — press to start, press again to stop",
                                 userData="toggle")
        self._hotkeyMode.setCurrentIndex(0 if cfg.hotkey.mode == "hold" else 1)
        hk.addWidget(self._hotkeyMode, 1, 1)
        root.addWidget(hk_card)

        # --- Output -----------------------------------------------------------
        out_card, out = _card("Output")
        out.addWidget(BodyLabel("Paste delay (ms)"), 0, 0)
        self._pasteDelay = SpinBox()
        self._pasteDelay.setRange(0, 2000)
        self._pasteDelay.setValue(cfg.output.paste_delay_ms)
        out.addWidget(self._pasteDelay, 0, 1)
        root.addWidget(out_card)

        # --- Startup -----------------------------------------------------------
        from larkyn import autostart

        st_card, st = _card(
            "Startup",
            "Larkyn starts minimized to the system tray, so dictation is always "
            "one hotkey away.",
        )
        st.addWidget(BodyLabel("Start Larkyn when I sign in to Windows"), 0, 0)
        self._autostart = SwitchButton()
        self._autostart.setChecked(autostart.is_enabled())
        st.addWidget(self._autostart, 0, 1)
        root.addWidget(st_card)

        # --- Appearance --------------------------------------------------------
        ap_card, ap = _card("Appearance")
        ap.addWidget(BodyLabel("Theme"), 0, 0)
        self._theme = ComboBox()
        self._theme.addItem("Dark", userData="dark")
        self._theme.addItem("Light", userData="light")
        self._theme.setCurrentIndex(0 if cfg.theme == "dark" else 1)
        ap.addWidget(self._theme, 0, 1)
        root.addWidget(ap_card)

        # --- Save ---------------------------------------------------------------
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self._saveBtn = PrimaryPushButton(FluentIcon.SAVE, "Save && apply")
        self._saveBtn.clicked.connect(self._save)
        save_row.addWidget(self._saveBtn)
        root.addLayout(save_row)
        root.addStretch(1)

        self.setWidget(container)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container.setStyleSheet("QWidget { background: transparent; }")

    # ------------------------------------------------------------------
    def _test_connection(self) -> None:
        import threading

        endpoint = self._endpoint.text().strip()
        model = self._model.text().strip()
        provider = self._provider.currentData()

        def work() -> None:
            try:
                import httpx

                from larkyn.llm.ollama_provider import native_base_url
                if provider == "ollama":
                    r = httpx.get(f"{native_base_url(endpoint)}/api/tags", timeout=5)
                    r.raise_for_status()
                    models = [m.get("name", "") for m in r.json().get("models", [])]
                    ok = model in models
                    msg = "Connected. Model found." if ok else \
                        f"Connected, but model {model!r} is not pulled."
                else:
                    r = httpx.get(f"{endpoint.rstrip('/')}/models", timeout=5)
                    r.raise_for_status()
                    ok, msg = True, "Connected."
            except Exception as exc:  # noqa: BLE001
                ok, msg = False, f"Connection failed: {exc}"
            self._testResult = (ok, msg)
            # Marshal back to the UI thread via a queued singleShot.
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self._show_test_result)

        threading.Thread(target=work, daemon=True).start()

    def _show_test_result(self) -> None:
        ok, msg = getattr(self, "_testResult", (False, "?"))
        bar = InfoBar.success if ok else InfoBar.error
        bar("Connection test", msg, duration=4000, position=InfoBarPosition.TOP, parent=self)

    def _save(self) -> None:
        cfg = self._ctx.config
        bus = self._ctx.bus

        hotkey_spec = self._hotkey.text().strip()
        if not parse_hotkey(hotkey_spec):
            InfoBar.error("Invalid hotkey", f"Could not parse {hotkey_spec!r}.",
                          duration=4000, position=InfoBarPosition.TOP, parent=self)
            return

        llm_changed = (
            cfg.llm.provider != self._provider.currentData()
            or cfg.llm.endpoint != self._endpoint.text().strip()
            or cfg.llm.model != self._model.text().strip()
            or cfg.llm.temperature != self._temp.value()
            or cfg.llm.top_p != self._topP.value()
            or cfg.llm.max_tokens != self._maxTokens.value()
            or cfg.llm.think != self._think.isChecked()
        )
        stt_changed = (
            cfg.stt.model != self._whisperModel.currentText()
            or cfg.stt.device != self._device.currentText()
        )
        hotkey_changed = (
            cfg.hotkey.toggle != hotkey_spec
            or cfg.hotkey.mode != self._hotkeyMode.currentData()
        )
        theme_changed = cfg.theme != self._theme.currentData()

        cfg.llm.provider = self._provider.currentData()
        cfg.llm.endpoint = self._endpoint.text().strip()
        cfg.llm.model = self._model.text().strip()
        cfg.llm.temperature = self._temp.value()
        cfg.llm.top_p = self._topP.value()
        cfg.llm.max_tokens = self._maxTokens.value()
        cfg.llm.think = self._think.isChecked()
        cfg.stt.model = self._whisperModel.currentText()
        cfg.stt.device = self._device.currentText()
        cfg.hotkey.toggle = hotkey_spec
        cfg.hotkey.mode = self._hotkeyMode.currentData()
        cfg.output.paste_delay_ms = self._pasteDelay.value()
        cfg.theme = self._theme.currentData()
        cfg.save()

        from larkyn import autostart

        try:
            if self._autostart.isChecked() != autostart.is_enabled():
                autostart.set_enabled(self._autostart.isChecked())
        except Exception:  # registry hiccup — don't block the rest of the save
            InfoBar.error("Startup", "Could not update the Windows startup entry.",
                          duration=4000, position=InfoBarPosition.TOP, parent=self)

        if llm_changed:
            bus.llmChanged.emit()
        if stt_changed:
            bus.sttChanged.emit()
        if hotkey_changed:
            bus.hotkeyChanged.emit(hotkey_spec)
        if theme_changed:
            bus.themeChanged.emit(cfg.theme)

        InfoBar.success("Saved", "Settings applied.", duration=2500,
                        position=InfoBarPosition.TOP, parent=self)
