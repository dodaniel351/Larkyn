"""The main Fluent window: navigation between Home, History, Profiles,
Vocabulary, and Settings. Closing hides to the tray; the app keeps running."""

from __future__ import annotations

from PySide6.QtCore import QSize
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition

from hermes.ui.context import UiContext
from hermes.ui.icons import app_icon
from hermes.ui.pages.history import HistoryPage
from hermes.ui.pages.home import HomePage
from hermes.ui.pages.profiles import ProfilesPage
from hermes.ui.pages.settings import SettingsPage
from hermes.ui.pages.vocabulary import VocabularyPage


class MainWindow(FluentWindow):
    def __init__(self, ctx: UiContext) -> None:
        super().__init__()
        self._ctx = ctx

        self.setWindowTitle("Larkyn")
        self.setWindowIcon(app_icon())
        self.resize(QSize(1000, 720))

        self.homePage = HomePage(ctx, self)
        self.historyPage = HistoryPage(ctx, self)
        self.profilesPage = ProfilesPage(ctx, self)
        self.vocabularyPage = VocabularyPage(ctx, self)
        self.settingsPage = SettingsPage(ctx, self)

        self.addSubInterface(self.homePage, FluentIcon.HOME, "Home")
        self.addSubInterface(self.historyPage, FluentIcon.HISTORY, "History")
        self.addSubInterface(self.profilesPage, FluentIcon.EDIT, "Profiles")
        self.addSubInterface(self.vocabularyPage, FluentIcon.DICTIONARY, "Vocabulary")
        self.addSubInterface(
            self.settingsPage, FluentIcon.SETTING, "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        """Hide to tray instead of quitting."""
        event.ignore()
        self.hide()

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
