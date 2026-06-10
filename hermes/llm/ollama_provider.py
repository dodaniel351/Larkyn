"""LLM rewrite via Ollama's native /api/chat.

gemma4:e2b-it-qat is a reasoning model; over the OpenAI-compatible /v1 endpoint
its chain-of-thought cannot be disabled and adds 3-8s per rewrite. The native
Ollama API honors ``think: false``, cutting a short rewrite to well under one
second with no quality loss — so this provider is the default when the backend
is Ollama. Any other OpenAI-compatible server still uses OpenAIProvider.
"""

from __future__ import annotations

import httpx

from hermes.core.interfaces import LLMProvider, ModelParams, Msg
from hermes.llm.openai_provider import _clean


def native_base_url(endpoint: str) -> str:
    """Map an OpenAI-style endpoint (.../v1) to the Ollama server root."""
    base = endpoint.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


class OllamaNativeProvider(LLMProvider):
    def __init__(self, endpoint: str, timeout_s: int = 120, think: bool = False) -> None:
        self._base = native_base_url(endpoint)
        self._timeout = timeout_s
        self._think = think

    def rewrite(self, messages: list[Msg], params: ModelParams) -> str:
        payload = {
            "model": params.model,
            "stream": False,
            "think": self._think,
            "options": {
                "temperature": params.temperature,
                "top_p": params.top_p,
                "num_predict": params.max_tokens,
            },
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        resp = httpx.post(f"{self._base}/api/chat", json=payload, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        return _clean(data.get("message", {}).get("content", ""))
