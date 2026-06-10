"""Personal vocabulary preservation.

User-defined terms must always be preserved exactly — never corrected, never
rewritten (spec). We inject them into the system prompt as a hard constraint.
"""

from __future__ import annotations

import re

_ALNUM_RUN = re.compile(r"[A-Za-z0-9]+|[^A-Za-z0-9]+")
_WORD = re.compile(r"[A-Za-z0-9]+")


def normalize_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        t = (term or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def vocabulary_clause(terms: list[str]) -> str:
    terms = normalize_terms(terms)
    if not terms:
        return ""
    listed = ", ".join(terms)
    return (
        "Custom vocabulary — these terms are spelled correctly and must appear in the "
        "output exactly as written, with identical spelling, capitalization, spacing, and "
        "punctuation. Speech-to-text often mishears them: if the text contains an obvious "
        "mis-transcription, phonetic variant, or spacing/hyphenation error of one of these "
        "terms (for example 'my sequel' for 'MySQL'), "
        "replace it with the exact term from this list. Never alter, translate, expand, or "
        f"split a term that already matches one of these. Terms: {listed}."
    )


# --- Deterministic enforcement ---------------------------------------------
# The prompt asks the model to honor vocabulary, but a small model can't
# guarantee it. This pass deterministically maps obvious mis-hearings back to
# the canonical term so preservation is reliable (spec: "must ALWAYS be
# preserved"). It is intentionally conservative to avoid false positives.

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _is_mishearing(candidate_key: str, term_key: str) -> bool:
    """True if candidate_key is the same as, or a close variant of, term_key."""
    if candidate_key == term_key:
        return True
    # Only fuzzy-match reasonably long, distinctive terms.
    if len(term_key) < 5 or abs(len(candidate_key) - len(term_key)) > 2:
        return False
    dist = _levenshtein(candidate_key, term_key)
    return dist <= (2 if len(term_key) >= 8 else 1)


def enforce_vocabulary(text: str, terms: list[str]) -> str:
    """Replace mis-transcribed spans with the exact canonical vocabulary term."""
    terms = normalize_terms(terms)
    if not text or not terms:
        return text
    # Longer (multi-word) terms first so they win over their components.
    for term in sorted(terms, key=lambda t: len(t.split()), reverse=True):
        text = _enforce_one(text, term)
    return text


def _enforce_one(text: str, term: str) -> str:
    term_key = _norm(term)
    if not term_key:
        return text
    max_words = max(1, len(term.split())) + 1  # allow split/merged variants

    tokens = _ALNUM_RUN.findall(text)
    word_positions = [i for i, t in enumerate(tokens) if _WORD.fullmatch(t)]
    n = len(word_positions)

    i = 0
    while i < n:
        matched = False
        for w in range(min(max_words, n - i), 0, -1):  # prefer longer windows
            span = word_positions[i:i + w]
            candidate_key = _norm("".join(tokens[p] for p in span))
            if len(candidate_key) < 3:
                continue
            if _is_mishearing(candidate_key, term_key):
                start, end = span[0], span[-1]
                for p in range(start, end + 1):
                    tokens[p] = ""
                tokens[start] = term
                i += w
                matched = True
                break
        if not matched:
            i += 1
    return "".join(tokens)
