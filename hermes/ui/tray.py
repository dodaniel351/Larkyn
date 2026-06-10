"""System tray icon, menu, and notifications.

Single-click toggles dictation; double-click (or the menu) opens the main
window. The icon and tooltip reflect the live pipeline state. Menu state stays
in sync with the main window through the signal bus.
"""

from __future__ import annotations

import os

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from hermes.config import app_data_dir
from hermes.core.interfaces import OutputMode, PipelineState, Session
from hermes.prompt.profiles import all_profiles
from hermes.ui.context import UiContext
from hermes.ui.icons import icon_for_state, label_for_state
from hermes.ui.overlay import RecordingOverlay

_OUTPUT_MODE_LABELS = {
    OutputMode.PASTE.value: "Paste into active app",
    OutputMode.CLIPBOARD.value: "Copy to clipboard",
    OutputMode.DRAFT.value: "Draft (store only)",
}


class TrayController:
    def __init__(
        self,
        app: QApplication,
        ctx: UiContext,
        overlay: RecordingOverlay,
        on_open=None,
    ) -> None:
        self._app = app
        self._ctx = ctx
        self._config = ctx.config
        self._orch = ctx.orchestrator
        self._overlay = overlay
        self._on_open = on_open

        self._tray = QSystemTrayIcon(icon_for_state(PipelineState.IDLE.value))
        self._tray.setToolTip("Larkyn — Ready")

        self._build_menu()
        self._connect()
        self._tray.show()

    # --- menu construction --------------------------------------------------
    def _build_menu(self) -> None:
        menu = QMenu()

        open_action = menu.addAction("Open Larkyn")
        open_action.triggered.connect(self._open_window)
        menu.addSeparator()

        toggle = menu.addAction("Start / Stop dictation")
        toggle.triggered.connect(self._orch.toggle)
        self._hotkeyHint = menu.addAction(f"Hotkey: {self._config.hotkey.toggle}")
        self._hotkeyHint.setEnabled(False)
        menu.addSeparator()

        # Writing profile (exclusive)
        self._profile_menu = menu.addMenu("Writing profile")
        self._profile_group = QActionGroup(menu)
        self._profile_group.setExclusive(True)
        self._fill_profiles()
        self._profile_group.triggered.connect(self._on_profile)

        # Output mode (exclusive)
        output_menu = menu.addMenu("Output mode")
        self._output_group = QActionGroup(menu)
        self._output_group.setExclusive(True)
        for mode, label in _OUTPUT_MODE_LABELS.items():
            act = output_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(mode == self._config.output.mode)
            act.setData(mode)
            self._output_group.addAction(act)
        self._output_group.triggered.connect(self._on_output_mode)

        # Raw mode toggle
        self._raw_action = menu.addAction("Raw mode (skip rewrite)")
        self._raw_action.setCheckable(True)
        self._raw_action.setChecked(self._config.output.raw_mode)
        self._raw_action.toggled.connect(self._on_raw)

        menu.addSeparator()
        menu.addAction("Open history folder").triggered.connect(self._open_history_folder)
        menu.addAction("Quit Larkyn").triggered.connect(self._quit)

        self._menu = menu
        self._tray.setContextMenu(menu)

    def _fill_profiles(self) -> None:
        for act in list(self._profile_group.actions()):
            self._profile_group.removeAction(act)
        self._profile_menu.clear()
        for key, profile in all_profiles(self._config.custom_profiles).items():
            act = self._profile_menu.addAction(profile.name)
            act.setCheckable(True)
            act.setChecked(key == self._orch.profile_key)
            act.setData(key)
            self._profile_group.addAction(act)

    # --- signal wiring ------------------------------------------------------
    def _connect(self) -> None:
        self._orch.stateChanged.connect(self._on_state)
        self._orch.finished.connect(self._on_finished)
        self._orch.failed.connect(self._on_failed)
        self._tray.activated.connect(self._on_activated)

        bus = self._ctx.bus
        bus.profileChanged.connect(self._sync_profile)
        bus.profilesEdited.connect(self._fill_profiles)
        bus.outputModeChanged.connect(self._sync_output_mode)
        bus.rawModeChanged.connect(self._sync_raw)
        bus.hotkeyChanged.connect(
            lambda hk: self._hotkeyHint.setText(f"Hotkey: {hk}")
        )

    # --- bus sync (changes made in the main window) ---------------------------
    def _sync_profile(self, key: str) -> None:
        for act in self._profile_group.actions():
            act.setChecked(act.data() == key)

    def _sync_output_mode(self, mode: str) -> None:
        for act in self._output_group.actions():
            act.setChecked(act.data() == mode)

    def _sync_raw(self, enabled: bool) -> None:
        self._raw_action.blockSignals(True)
        self._raw_action.setChecked(enabled)
        self._raw_action.blockSignals(False)

    # --- handlers -----------------------------------------------------------
    def _open_window(self) -> None:
        if self._on_open is not None:
            self._on_open()

    def _on_profile(self, action: QAction) -> None:
        key = action.data()
        self._orch.set_profile(key)
        self._config.profile_default = key
        self._config.save()
        self._ctx.bus.profileChanged.emit(key)

    def _on_output_mode(self, action: QAction) -> None:
        mode = action.data()
        self._orch.set_output_mode(mode)
        self._config.save()
        self._ctx.bus.outputModeChanged.emit(mode)

    def _on_raw(self, checked: bool) -> None:
        self._orch.set_raw_mode(checked)
        self._config.save()
        self._ctx.bus.rawModeChanged.emit(checked)

    def _on_activated(self, reason) -> None:  # noqa: ANN001
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_window()
        elif reason == QSystemTrayIcon.Trigger:
            self._orch.toggle()

    def _on_state(self, state: str) -> None:
        self._tray.setIcon(icon_for_state(state))
        self._tray.setToolTip(f"Larkyn — {label_for_state(state)}")
        self._overlay.on_state(state)

    def _on_finished(self, session: Session) -> None:
        snippet = session.rewritten.strip().replace("\n", " ")
        if len(snippet) > 90:
            snippet = snippet[:90] + "…"
        self._tray.showMessage(
            "Larkyn", snippet or "(empty)",
            icon_for_state(PipelineState.IDLE.value), 4000,
        )

    def _on_failed(self, message: str) -> None:
        self._tray.showMessage("Larkyn", message, QSystemTrayIcon.Warning, 4000)

    def notify(self, message: str) -> None:
        """Public helper for the bootstrap layer to surface warnings."""
        self._tray.showMessage("Larkyn", message, QSystemTrayIcon.Warning, 5000)

    def _open_history_folder(self) -> None:
        try:
            os.startfile(str(app_data_dir()))  # type: ignore[attr-defined]
        except Exception:
            pass

    def _quit(self) -> None:
        self._tray.hide()
        self._app.quit()
