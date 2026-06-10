from pynput.keyboard import Key, KeyCode

from hermes.hotkey import HotkeyListener, parse_hotkey


def test_parse_default_hotkey():
    keys = parse_hotkey("<ctrl>+<alt>+<space>")
    assert keys == {Key.ctrl, Key.alt, Key.space}


def test_parse_letter_hotkey():
    keys = parse_hotkey("ctrl+alt+h")
    assert Key.ctrl in keys and Key.alt in keys
    assert KeyCode.from_char("h") in keys


def test_parse_modifier_only_combo():
    # Ctrl + Windows key
    assert parse_hotkey("<ctrl>+<cmd>") == {Key.ctrl, Key.cmd}
    assert parse_hotkey("<ctrl>+<win>") == {Key.ctrl, Key.cmd}


def test_modifier_only_combo_fires_and_rearms():
    calls = []
    h = HotkeyListener("<ctrl>+<cmd>", lambda: calls.append(1))

    h._on_press(Key.ctrl_l)
    assert calls == []
    h._on_press(Key.cmd_l)          # win key completes the combo
    assert calls == [1]
    h._on_release(Key.cmd_l)        # re-arm
    h._on_press(Key.cmd_r)          # right win key also works
    assert calls == [1, 1]


def test_release_callback_fires_for_push_to_talk():
    downs, ups = [], []
    h = HotkeyListener("<ctrl>+<cmd>", lambda: downs.append(1),
                       on_deactivate=lambda: ups.append(1))

    h._on_press(Key.ctrl_l)
    h._on_press(Key.cmd_l)
    assert downs == [1] and ups == []      # held -> recording
    h._on_release(Key.cmd_l)
    assert ups == [1]                      # released -> process
    h._on_release(Key.ctrl_l)
    assert ups == [1]                      # only fires once per activation

    h._on_press(Key.ctrl_l)                # ctrl alone never triggers either
    h._on_release(Key.ctrl_l)
    assert downs == [1] and ups == [1]


def test_fires_once_and_rearms_with_modifier_normalization():
    calls = []
    h = HotkeyListener("<ctrl>+<alt>+<space>", lambda: calls.append(1))

    # left-variant modifiers must normalize to the generic modifier
    h._on_press(Key.ctrl_l)
    h._on_press(Key.alt_l)
    assert calls == []          # combo not complete yet
    h._on_press(Key.space)
    assert calls == [1]         # rising edge fires once
    h._on_press(Key.space)      # still held -> no refire
    assert calls == [1]

    h._on_release(Key.space)    # re-arm
    h._on_press(Key.space)
    assert calls == [1, 1]
