"""Shared UI context: configuration + pipeline handles + a signal bus.

The bus decouples pages, the tray, and the bootstrap layer: any of them can
change a setting and everyone else reacts (live-apply, menu refresh, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from hermes.config import AppConfig
from hermes.core.orchestrator import Orchestrator
from hermes.history.store import SqliteHistoryStore


class SignalBus(QObject):
    profileChanged = Signal(str)    # profile key
    profilesEdited = Signal()       # custom profile set changed
    vocabularyEdited = Signal()
    outputModeChanged = Signal(str)
    rawModeChanged = Signal(bool)
    hotkeyChanged = Signal(str)     # new hotkey spec
    llmChanged = Signal()           # provider/endpoint/model/params changed
    sttChanged = Signal()           # whisper engine settings changed
    themeChanged = Signal(str)      # "dark" | "light"


@dataclass
class UiContext:
    config: AppConfig
    orchestrator: Orchestrator
    history: SqliteHistoryStore
    bus: SignalBus
