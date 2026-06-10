import sys

from larkyn import autostart


def test_launch_command_quotes_executable():
    cmd = autostart.launch_command()
    assert cmd.startswith('"')
    assert "--minimized" in cmd
    assert sys.executable in cmd


def test_enable_disable_round_trip():
    """Real (per-user, harmless) registry round-trip on Windows."""
    if sys.platform != "win32":
        return
    original = autostart.is_enabled()
    try:
        autostart.enable()
        assert autostart.is_enabled()
        autostart.disable()
        assert not autostart.is_enabled()
    finally:
        autostart.set_enabled(original)  # leave the machine as we found it
