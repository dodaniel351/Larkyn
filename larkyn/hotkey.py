"""Robust global hotkey detection.

pynput's ``GlobalHotKeys`` proved unreliable for modifier combos like
Ctrl+Alt+Space on Windows. Instead we run a raw keyboard ``Listener`` (which
does receive the events) and track a normalized set of pressed keys, firing on
the rising edge when the target combo becomes fully held. Left/right modifier
variants are normalized, and letter/digit keys are normalized by virtual-key
code so combos work even while Ctrl is held (which otherwise mangles ``char``).
"""

from __future__ import annotations

import logging

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

log = logging.getLogger("larkyn.hotkey")

_MOD_ALIASES = {
    "ctrl": Key.ctrl, "control": Key.ctrl,
    "alt": Key.alt, "alt_gr": Key.alt, "option": Key.alt,
    "shift": Key.shift,
    "cmd": Key.cmd, "win": Key.cmd, "super": Key.cmd, "meta": Key.cmd,
    "space": Key.space, "enter": Key.enter, "return": Key.enter,
    "tab": Key.tab, "esc": Key.esc, "escape": Key.esc,
}


def _normalize(key):
    if key in (Key.ctrl_l, Key.ctrl_r):
        return Key.ctrl
    if key in (Key.alt_l, Key.alt_r, Key.alt_gr):
        return Key.alt
    if key in (Key.shift_l, Key.shift_r):
        return Key.shift
    if key in (Key.cmd_l, Key.cmd_r):
        return Key.cmd
    if isinstance(key, KeyCode):
        vk = key.vk
        if vk is not None:
            if 0x41 <= vk <= 0x5A:           # A-Z
                return KeyCode.from_char(chr(vk).lower())
            if 0x30 <= vk <= 0x39:           # 0-9
                return KeyCode.from_char(chr(vk))
        if key.char:
            return KeyCode.from_char(key.char.lower())
    return key


def parse_hotkey(spec: str) -> set:
    """Parse '<ctrl>+<alt>+<space>' (or 'ctrl+alt+h', '<f9>', ...) into keys."""
    keys: set = set()
    for raw in spec.split("+"):
        tok = raw.strip().lower().strip("<>")
        if not tok:
            continue
        if tok in _MOD_ALIASES:
            keys.add(_MOD_ALIASES[tok])
        elif len(tok) == 1:
            keys.add(KeyCode.from_char(tok))
        elif hasattr(Key, tok):              # f1..f24, home, end, etc.
            keys.add(getattr(Key, tok))
        else:
            log.warning("Unrecognized hotkey token: %r", raw)
    return keys


class HotkeyListener:
    """Fires ``on_activate`` when the combo becomes fully held, and
    ``on_deactivate`` (if given) when any combo key is then released —
    enabling push-to-talk (hold to record, release to process)."""

    def __init__(self, spec: str, on_activate, on_deactivate=None) -> None:
        self.spec = spec
        self._target = parse_hotkey(spec)
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate
        self._pressed: set = set()
        self._active = False
        self._listener = None

    def start(self) -> None:
        if not self._target:
            raise ValueError(f"Could not parse hotkey: {self.spec!r}")
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key) -> None:
        self._pressed.add(_normalize(key))
        if self._target <= self._pressed and not self._active:
            self._active = True
            try:
                self._on_activate()
            except Exception:
                log.exception("Hotkey callback raised")

    def _on_release(self, key) -> None:
        norm = _normalize(key)
        self._pressed.discard(norm)
        if norm in self._target and self._active:
            self._active = False  # re-arm once any combo key is released
            if self._on_deactivate is not None:
                try:
                    self._on_deactivate()
                except Exception:
                    log.exception("Hotkey release callback raised")
