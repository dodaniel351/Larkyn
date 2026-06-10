from larkyn.prompt.vocabulary import (
    enforce_vocabulary,
    normalize_terms,
    vocabulary_clause,
)


def test_empty_returns_blank():
    assert vocabulary_clause([]) == ""
    assert vocabulary_clause(["", "   "]) == ""


def test_dedup_case_insensitive_preserves_first_spelling():
    assert normalize_terms(["LibreNMS", "librenms", " LibreNMS "]) == ["LibreNMS"]


def test_clause_lists_all_terms():
    clause = vocabulary_clause(["eClinicalWorks", "Phreesia"])
    assert "eClinicalWorks" in clause
    assert "Phreesia" in clause
    assert "exactly as written" in clause


def test_clause_instructs_correction_of_mishearings():
    clause = vocabulary_clause(["LibreNMS"])
    assert "replace it with the exact term" in clause


def test_enforce_fixes_single_char_mishearing():
    assert enforce_vocabulary("errors in Greylog again", ["Graylog"]) == "errors in Graylog again"


def test_enforce_fixes_split_and_char_mishearing():
    out = enforce_vocabulary("the Libra NMS server is down", ["LibreNMS"])
    assert "LibreNMS" in out
    assert "Libra NMS" not in out


def test_enforce_fixes_casing():
    assert enforce_vocabulary("check librenms now", ["LibreNMS"]) == "check LibreNMS now"


def test_enforce_leaves_unrelated_words_alone():
    assert enforce_vocabulary("we deployed the library today", ["LibreNMS"]) == \
        "we deployed the library today"


def test_enforce_handles_empty():
    assert enforce_vocabulary("hello", []) == "hello"
    assert enforce_vocabulary("", ["LibreNMS"]) == ""
