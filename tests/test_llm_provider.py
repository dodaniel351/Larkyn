import httpx
import pytest

from larkyn.core.interfaces import ModelParams, Msg
from larkyn.llm.errors import LLMError
from larkyn.llm.ollama_provider import OllamaNativeProvider, native_base_url
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


# --- friendly error mapping (the messages users actually see) ---------------

_MSGS = [Msg("user", "hello")]
_PARAMS = ModelParams(model="gemma4:e2b-it-qat")


class _FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


def test_ollama_down_gives_actionable_message(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", boom)
    provider = OllamaNativeProvider("http://localhost:11434/v1")
    with pytest.raises(LLMError) as e:
        provider.rewrite(_MSGS, _PARAMS)
    msg = str(e.value)
    assert "Ollama doesn't appear to be running" in msg
    assert "Start Ollama" in msg


def test_ollama_missing_model_tells_user_to_pull(monkeypatch):
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: _FakeResponse(404, {"error": "model not found"}),
    )
    provider = OllamaNativeProvider("http://localhost:11434/v1")
    with pytest.raises(LLMError) as e:
        provider.rewrite(_MSGS, _PARAMS)
    msg = str(e.value)
    assert "isn't installed in Ollama" in msg
    assert "ollama pull gemma4:e2b-it-qat" in msg


def test_ollama_other_http_error_is_concise(monkeypatch):
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: _FakeResponse(500, {"error": "out of memory"}),
    )
    provider = OllamaNativeProvider("http://localhost:11434/v1")
    with pytest.raises(LLMError) as e:
        provider.rewrite(_MSGS, _PARAMS)
    assert "HTTP 500" in str(e.value)
    assert "out of memory" in str(e.value)


def test_ollama_timeout_message(monkeypatch):
    def slow(*a, **k):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx, "post", slow)
    provider = OllamaNativeProvider("http://localhost:11434/v1")
    with pytest.raises(LLMError) as e:
        provider.rewrite(_MSGS, _PARAMS)
    assert "took too long" in str(e.value)
