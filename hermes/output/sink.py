"""Deliver final text to the user.

- PASTE: copy to clipboard, then simulate Ctrl+V into the active window.
- CLIPBOARD: copy only.
- DRAFT: keep in memory (history persists it); the clipboard is left untouched.

The recording overlay must be a non-activating window so the user's target app
(Outlook, Teams, Word, Notepad, VS Code, browsers, ...) keeps focus and the
paste lands in the right place.
"""

from __future__ import annotations

import time

from hermes.core.interfaces import OutputMode, OutputSink


class SystemOutputSink(OutputSink):
    def __init__(self, paste_delay_ms: int = 120) -> None:
        self._delay = max(0.0, paste_delay_ms / 1000.0)
        self._last_draft: str | None = None
        self._keyboard = None  # lazily created pynput controller

    @property
    def last_draft(self) -> str | None:
        return self._last_draft

    def _copy(self, text: str) -> None:
        import pyperclip

        pyperclip.copy(text)

    def _paste(self) -> None:
        from pynput.keyboard import Controller, Key

        if self._keyboard is None:
            self._keyboard = Controller()
        kb = self._keyboard
        kb.press(Key.ctrl)
        kb.press("v")
        kb.release("v")
        kb.release(Key.ctrl)

    def deliver(self, text: str, mode: OutputMode) -> None:
        if text is None:
            text = ""
        if mode == OutputMode.DRAFT:
            self._last_draft = text
            return
        self._copy(text)
        if mode == OutputMode.PASTE:
            if self._delay:
                time.sleep(self._delay)
            self._paste()
