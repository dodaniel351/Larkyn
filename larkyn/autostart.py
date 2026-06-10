"""Start Larkyn automatically at Windows sign-in.

Uses the per-user Run registry key (no admin rights needed):
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

The installer can also create a Startup-folder shortcut (an install-time
option); enabling/disabling here removes that shortcut so the two mechanisms
never double-launch the app.
"""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("larkyn.autostart")

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "Larkyn"


def launch_command() -> str:
    """The command the OS should run at sign-in (starts minimized to tray)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    # Dev fallback: run the package with the current interpreter.
    return f'"{sys.executable}" -m larkyn --minimized'


def _startup_shortcut_path() -> str:
    return os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup", "Larkyn.lnk",
    )


def _remove_startup_shortcut() -> None:
    path = _startup_shortcut_path()
    try:
        if os.path.exists(path):
            os.remove(path)
            log.info("Removed legacy Startup-folder shortcut.")
    except OSError:
        log.exception("Could not remove Startup shortcut %s", path)


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except OSError:
        pass
    return os.path.exists(_startup_shortcut_path())


def enable() -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, launch_command())
    _remove_startup_shortcut()  # avoid double-launch with the installer option
    log.info("Autostart enabled: %s", launch_command())


def disable() -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except OSError:
        pass  # value didn't exist
    _remove_startup_shortcut()
    log.info("Autostart disabled.")


def set_enabled(enabled: bool) -> None:
    enable() if enabled else disable()
