import datetime

from hermes.core.interfaces import Session
from hermes.history.store import SqliteHistoryStore


def _session(raw: str, rewritten: str, profile: str = "general") -> Session:
    return Session(
        timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
        profile=profile,
        raw_transcript=raw,
        rewritten=rewritten,
        duration_ms=100,
        model="gemma4:e2b-it-qat",
        output_mode="paste",
    )


def test_add_and_recent(tmp_path):
    store = SqliteHistoryStore(tmp_path / "h.db")
    sid = store.add(_session("hello there", "Hello there."))
    assert sid >= 1
    recent = store.recent(10)
    assert len(recent) == 1
    assert recent[0].rewritten == "Hello there."
    assert recent[0].model == "gemma4:e2b-it-qat"


def test_fts_search(tmp_path):
    store = SqliteHistoryStore(tmp_path / "h.db")
    store.add(_session("the backup job failed", "The backup job failed again."))
    store.add(_session("lunch plans", "Let's grab lunch at noon."))

    hits = store.search("backup")
    assert len(hits) == 1
    assert "backup" in hits[0].rewritten.lower()

    # prefix match
    assert len(store.search("lun")) == 1
    # empty query falls back to recent (all rows)
    assert len(store.search("   ")) == 2
