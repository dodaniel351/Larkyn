"""About page — what Larkyn is, the technology inside it, and who made it."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    HyperlinkButton,
    StrongBodyLabel,
    TitleLabel,
)

from larkyn import __version__
from larkyn.ui.icons import asset_path

_REPO_URL = "https://github.com/dodaniel351/Larkyn"

_DESCRIPTION = (
    "Larkyn is a privacy-first, system-wide voice-to-writing assistant. "
    "Hold a hotkey, speak naturally, release — your speech is transcribed and "
    "rewritten into polished written text, then pasted straight into whatever "
    "application you're using. It is not a transcription tool: it removes filler "
    "words, fixes grammar, and turns rambling speech into clean writing.\n\n"
    "Everything runs locally on your machine. No cloud, no telemetry, no data "
    "ever leaves your computer."
)

_TECH = [
    ("Speech recognition", "OpenAI Whisper (large-v3-turbo) via faster-whisper / "
                           "CTranslate2, GPU-accelerated with CUDA"),
    ("Writing engine", "Google Gemma 4 (e2b-it-qat) served locally by Ollama"),
    ("Interface", "Python · PySide6 (Qt) · Fluent Design widgets"),
    ("Storage", "SQLite with full-text search — history never leaves your PC"),
    ("Packaging", "PyInstaller · Inno Setup"),
]


class AboutPage(QWidget):
    def __init__(self, ctx=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(14)
        emblem_file = asset_path("emblem_white.png")
        if emblem_file:
            emblem = BodyLabel("")
            emblem.setPixmap(QPixmap(emblem_file).scaled(
                56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header.addWidget(emblem)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(TitleLabel("Larkyn"))
        title_col.addWidget(CaptionLabel(f"Version {__version__}"))
        header.addLayout(title_col)
        header.addStretch(1)
        root.addLayout(header)

        # --- What it is ---------------------------------------------------
        about_card = CardWidget(self)
        al = QVBoxLayout(about_card)
        al.setContentsMargins(24, 18, 24, 18)
        al.setSpacing(8)
        al.addWidget(StrongBodyLabel("Voice to polished writing. 100% local."))
        desc = BodyLabel(_DESCRIPTION)
        desc.setWordWrap(True)
        al.addWidget(desc)
        root.addWidget(about_card)

        # --- Technology ------------------------------------------------------
        tech_card = CardWidget(self)
        tl = QVBoxLayout(tech_card)
        tl.setContentsMargins(24, 18, 24, 18)
        tl.setSpacing(6)
        tl.addWidget(StrongBodyLabel("Technology"))
        for name, detail in _TECH:
            row = BodyLabel(f"•  {name} — {detail}")
            row.setWordWrap(True)
            tl.addWidget(row)
        root.addWidget(tech_card)

        # --- Credits -----------------------------------------------------------
        credit_card = CardWidget(self)
        cl = QVBoxLayout(credit_card)
        cl.setContentsMargins(24, 18, 24, 18)
        cl.setSpacing(8)
        cl.addWidget(StrongBodyLabel("Created by David O'Daniel"))
        links = QHBoxLayout()
        links.setSpacing(12)
        repo_btn = HyperlinkButton(_REPO_URL, "Larkyn on GitHub", self, FluentIcon.GITHUB)
        links.addWidget(repo_btn)
        links.addStretch(1)
        cl.addLayout(links)
        cl.addWidget(CaptionLabel("Open source under the MIT License."))
        root.addWidget(credit_card)

        root.addStretch(1)
