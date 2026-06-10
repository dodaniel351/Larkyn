from hermes.prompt.smart_commands import apply_smart_commands


def test_new_paragraph():
    out = apply_smart_commands("first point new paragraph second point")
    assert out == "First point\n\nSecond point"


def test_new_line():
    out = apply_smart_commands("item one new line item two")
    assert out == "Item one\nItem two"


def test_bullet_points():
    out = apply_smart_commands("todo list bullet point fix server bullet point email bob")
    assert out == "Todo list\n- Fix server\n- Email bob"


def test_undo_last_sentence():
    out = apply_smart_commands("The server is fine. The backup failed. scratch that The backup succeeded.")
    assert "failed" not in out
    assert "The backup succeeded." in out
    assert "The server is fine." in out


def test_plain_text_untouched():
    text = "Nothing special here."
    assert apply_smart_commands(text) == text


def test_empty():
    assert apply_smart_commands("") == ""
