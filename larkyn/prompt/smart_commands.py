"""Spoken editing commands.

Two layers (spec: "Recognize spoken editing commands ... Convert into
formatting instructions"):

1. ``SMART_COMMANDS_GUIDANCE`` — appended to the rewrite system prompt so the
   LLM applies spoken commands as real formatting.
2. ``apply_smart_commands`` — a deterministic processor used in Raw Mode
   (no LLM pass) so commands still work there.
"""

from __future__ import annotations

import re

SMART_COMMANDS_GUIDANCE = """Spoken editing commands:
The speaker may dictate formatting commands. When one of these phrases appears
as a command (not as part of a sentence's meaning), apply it as formatting and
remove the phrase itself from the text:
- "new paragraph" -> start a new paragraph (blank line)
- "new line" -> start a new line
- "bullet point" -> start a bulleted list item ("- ")
- "numbered list" -> start a numbered list (1. 2. 3. ...)
- "heading <words>" / "heading: <words>" -> render <words> as a heading line
- "undo last sentence" / "scratch that" -> delete the sentence dictated just before the command"""

_PUNCT_AFTER = r"[\s,.;:!?]*"

# Ordered: more specific phrases first.
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(rf"{_PUNCT_AFTER}\bnew paragraph\b{_PUNCT_AFTER}", re.IGNORECASE), "\n\n"),
    (re.compile(rf"{_PUNCT_AFTER}\bnew line\b{_PUNCT_AFTER}", re.IGNORECASE), "\n"),
    (re.compile(rf"{_PUNCT_AFTER}\bbullet point\b{_PUNCT_AFTER}", re.IGNORECASE), "\n- "),
]

_UNDO_RE = re.compile(r"\b(?:undo last sentence|scratch that)\b[\s,.;:!?]*", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _apply_undo(text: str) -> str:
    """Remove the sentence immediately preceding each undo command."""
    while True:
        m = _UNDO_RE.search(text)
        if not m:
            return text
        before = text[: m.start()]
        after = text[m.end():]
        sentences = _SENTENCE_SPLIT.split(before.strip())
        if sentences:
            sentences = sentences[:-1]
        prefix = " ".join(s for s in sentences if s).strip()
        if prefix and after.strip():
            text = prefix + " " + after.lstrip()
        else:
            text = (prefix + after).strip()


def apply_smart_commands(text: str) -> str:
    """Deterministically apply spoken formatting commands (Raw Mode path)."""
    if not text:
        return text
    text = _apply_undo(text)
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    # Tidy: strip trailing spaces per line, collapse 3+ newlines.
    lines = [ln.rstrip() for ln in text.split("\n")]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    # Capitalize line starts after paragraph/line breaks.
    out = re.sub(r"(^|\n+|\n- )([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out
