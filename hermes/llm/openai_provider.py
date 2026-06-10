"""LLM rewrite via any OpenAI-compatible chat endpoint.

Default target is Ollama at http://localhost:11434/v1 serving gemma4:e2b-it-qat,
but the same code works against LM Studio, llama.cpp, vLLM, OpenAI, etc. — only
the endpoint/model/key change (spec: swappable, no code changes).
"""

from __future__ import annotations

import re

from hermes.core.interfaces import LLMProvider, ModelParams, Msg

# Safety net for models that inline chain-of-thought in the content field.
# (gemma4 returns reasoning in a separate field, so content is already clean.)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _clean(text: str) -> str:
    text = _THINK_RE.sub("", text or "").strip()
    # Some models wrap the whole answer in quotes despite instructions not to.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'", "“", "”"):
        inner = text[1:-1].strip()
        if inner:
            text = inner
    return text


class OpenAIProvider(LLMProvider):
    def __init__(self, endpoint: str, api_key: str = "ollama", timeout_s: int = 120) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=endpoint, api_key=api_key or "ollama", timeout=timeout_s)

    def rewrite(self, messages: list[Msg], params: ModelParams) -> str:
        resp = self._client.chat.completions.create(
            model=params.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=params.temperature,
            top_p=params.top_p,
            max_tokens=params.max_tokens,
            stream=False,
        )
        choice = resp.choices[0].message
        content = choice.content or ""
        if not content:
            # Fall back to a non-standard reasoning field if content came back empty.
            content = getattr(choice, "reasoning", "") or ""
        return _clean(content)
