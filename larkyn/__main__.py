"""Larkyn application entry point.

Builds the pipeline, the Fluent main window, the tray, and the global hotkey,
and wires the signal bus so settings changes apply live (LLM provider, Whisper
engine, hotkey, theme) without a restart.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, Qt, QSharedMemory, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from larkyn.audio.capture import SoundDeviceCapture
from larkyn.config import AppConfig, history_db_path
from larkyn.core.orchestrator import Orchestrator
from larkyn.history.store import SqliteHistoryStore
from larkyn.llm.openai_provider import OpenAIProvider
from larkyn.logging_setup import setup_logging
from larkyn.output.sink import SystemOutputSink
from larkyn.stt.faster_whisper_engine import FasterWhisperEngine

log = logging.getLogger("larkyn.main")


class HotkeyBridge(QObject):
    """Marshals the global-hotkey callbacks (pynput thread) onto the Qt thread."""
    pressed = Signal()
    released = Signal()


def build_llm(config: AppConfig):
    if config.llm.provider == "ollama":
        from larkyn.llm.ollama_provider import OllamaNativeProvider

        return OllamaNativeProvider(
            endpoint=config.llm.endpoint,
            timeout_s=config.llm.timeout_s,
            think=config.llm.think,
        )
    return OpenAIProvider(
        endpoint=config.llm.endpoint,
        api_key=config.llm.api_key,
        timeout_s=config.llm.timeout_s,
    )


def build_transcriber(config: AppConfig) -> FasterWhisperEngine:
    return FasterWhisperEngine(
        model=config.stt.model,
        device=config.stt.device,
        compute_type=config.stt.compute_type,
        language=config.stt.language,
        beam_size=config.stt.beam_size,
        vad_filter=config.stt.vad_filter,
    )


def start_hotkey(bridge: HotkeyBridge, hotkey: str):
    from larkyn.hotkey import HotkeyListener

    listener = HotkeyListener(
        hotkey, bridge.pressed.emit, on_deactivate=bridge.released.emit
    )
    listener.start()
    return listener


def apply_theme(theme: str) -> None:
    try:
        from qfluentwidgets import Theme, setTheme

        setTheme(Theme.LIGHT if theme == "light" else Theme.DARK)
    except Exception:
        pass  # Fluent theming is optional; the app works without it.


def main() -> int:
    log_path = setup_logging()

    def _excepthook(exc_type, exc, tb):
        log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    log.info("=" * 60)
    log.info("Larkyn starting | python=%s", sys.executable)
    log.info("Log file: %s", log_path)

    app = QApplication(sys.argv)
    app.setApplicationName("Larkyn")
    app.setQuitOnLastWindowClosed(False)
    from larkyn.ui.icons import app_icon

    app.setWindowIcon(app_icon())

    # Single-instance guard so we don't register the hotkey twice.
    shm = QSharedMemory("Larkyn_singleton")
    if not shm.create(1):
        log.warning("Another instance is already running; exiting.")
        QMessageBox.information(None, "Larkyn", "Larkyn is already running.")
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.error("No system tray available.")
        QMessageBox.critical(None, "Larkyn", "No system tray is available on this system.")
        return 1

    config = AppConfig.load()
    log.info("Config loaded | provider=%s model=%s endpoint=%s whisper=%s hotkey=%s",
             config.llm.provider, config.llm.model, config.llm.endpoint,
             config.stt.model, config.hotkey.toggle)
    apply_theme(config.theme)

    # --- pipeline -----------------------------------------------------------
    capture = SoundDeviceCapture(sample_rate=16000)
    history = SqliteHistoryStore(history_db_path())
    orchestrator = Orchestrator(
        config, capture, build_transcriber(config), build_llm(config),
        SystemOutputSink(paste_delay_ms=config.output.paste_delay_ms), history,
    )

    # --- UI -------------------------------------------------------------------
    from larkyn.ui.context import SignalBus, UiContext
    from larkyn.ui.mainwindow import MainWindow
    from larkyn.ui.overlay import RecordingOverlay
    from larkyn.ui.tray import TrayController

    bus = SignalBus()
    ctx = UiContext(config=config, orchestrator=orchestrator, history=history, bus=bus)

    window = MainWindow(ctx)
    overlay = RecordingOverlay()
    tray = TrayController(app, ctx, overlay, on_open=window.show_window)
    log.info("Tray icon shown (look in the hidden-icons '^' area on the taskbar).")

    # Load Whisper in the background now so the first dictation is instant.
    orchestrator.warm_up()

    # --- global hotkey -----------------------------------------------------------
    bridge = HotkeyBridge()
    bridge.pressed.connect(orchestrator.on_hotkey_down, Qt.QueuedConnection)
    bridge.released.connect(orchestrator.on_hotkey_up, Qt.QueuedConnection)
    state = {"listener": None}
    try:
        state["listener"] = start_hotkey(bridge, config.hotkey.toggle)
        log.info("Global hotkey registered: %s", config.hotkey.toggle)
    except Exception as exc:  # noqa: BLE001
        log.exception("Hotkey registration FAILED for %s", config.hotkey.toggle)
        tray.notify(f"Hotkey '{config.hotkey.toggle}' could not be registered: {exc}")

    # --- live-apply handlers ---------------------------------------------------
    def on_hotkey_changed(spec: str) -> None:
        if state["listener"] is not None:
            try:
                state["listener"].stop()
            except Exception:
                pass
        try:
            state["listener"] = start_hotkey(bridge, spec)
            log.info("Hotkey re-registered: %s", spec)
        except Exception as exc:  # noqa: BLE001
            log.exception("Hotkey re-registration failed")
            tray.notify(f"Hotkey '{spec}' could not be registered: {exc}")

    def on_llm_changed() -> None:
        orchestrator.set_llm_provider(build_llm(config))
        log.info("LLM provider rebuilt | provider=%s model=%s",
                 config.llm.provider, config.llm.model)

    def on_stt_changed() -> None:
        orchestrator.set_transcriber(build_transcriber(config))
        log.info("Whisper engine rebuilt | model=%s device=%s",
                 config.stt.model, config.stt.device)
        orchestrator.warm_up()  # load the new model before the next dictation

    bus.hotkeyChanged.connect(on_hotkey_changed)
    bus.llmChanged.connect(on_llm_changed)
    bus.sttChanged.connect(on_stt_changed)
    bus.themeChanged.connect(apply_theme)

    # Keep strong references alive for the lifetime of the app.
    app._larkyn_refs = (orchestrator, overlay, tray, bridge, window, ctx, shm, state)  # type: ignore[attr-defined]

    banner = (
        "\n" + "=" * 64 +
        "\n  Larkyn is running.\n"
        f"  - Press {config.hotkey.toggle} to start/stop dictation.\n"
        "  - Double-click the tray icon to open the app window.\n"
        f"  - Logs: {log_path}\n" +
        "=" * 64 + "\n"
    )
    print(banner, flush=True)

    if "--minimized" not in sys.argv:
        window.show_window()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
