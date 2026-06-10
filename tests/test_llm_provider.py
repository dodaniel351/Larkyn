from larkyn.llm.ollama_provider import native_base_url
from larkyn.llm.openai_provider import _clean


def test_native_base_url_strips_v1():
    assert native_base_url("http://localhost:11434/v1") == "http://localhost:11434"
    assert native_base_url("http://localhost:11434/v1/") == "http://localhost:11434"
    assert native_base_url("http://localhost:11434") == "http://localhost:11434"


def test_clean_strips_think_blocks():
    assert _clean("<think>reasoning here</think>Final text.") == "Final text."


def test_clean_strips_wrapping_quotes():
    assert _clean('"Hello there."') == "Hello there."
    assert _clean("Plain text.") == "Plain text."
