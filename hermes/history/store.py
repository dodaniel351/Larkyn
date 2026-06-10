"""SQLite-backed dictation history with full-text search.

All sessions are stored locally in %APPDATA%\\Larkyn\\history.db. An
FTS5 virtual table mirrors the transcript/output columns (kept in sync by
triggers) so history is searchable.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from hermes.core.interfaces import HistoryStore, Session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT    NOT NULL,
    profile        TEXT    NOT NULL,
    raw_transcript TEXT    NOT NULL,
    rewritten      TEXT    NOT NULL,
    duration_ms    INTEGER NOT NULL,
    model          TEXT    NOT NULL,
    output_mode    TEXT    NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts
USING fts5(raw_transcript, rewritten, content='sessions', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS sessions_ai AFTER INSERT ON sessions BEGIN
    INSERT INTO sessions_fts(rowid, raw_transcript, rewritten)
    VALUES (new.id, new.raw_transcript, new.rewritten);
END;

CREATE TRIGGER IF NOT EXISTS sessions_ad AFTER DELETE ON sessions BEGIN
    INSERT INTO sessions_fts(sessions_fts, rowid, raw_transcript, rewritten)
    VALUES ('delete', old.id, old.raw_transcript, old.rewritten);
END;

CREATE TRIGGER IF NOT EXISTS sessions_au AFTER UPDATE ON sessions BEGIN
    INSERT INTO sessions_fts(sessions_fts, rowid, raw_transcript, rewritten)
    VALUES ('delete', old.id, old.raw_transcript, old.rewritten);
    INSERT INTO sessions_fts(rowid, raw_transcript, rewritten)
    VALUES (new.id, new.raw_transcript, new.rewritten);
END;
"""

_COLUMNS = "id, timestamp, profile, raw_transcript, rewritten, duration_ms, model, output_mode"


def _fts_query(query: str) -> str:
    """Turn free text into a safe FTS5 MATCH string (quoted prefix terms)."""
    tokens = [t for t in (query or "").replace('"', " ").split() if t]
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens)


class SqliteHistoryStore(HistoryStore):
    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            timestamp=row["timestamp"],
            profile=row["profile"],
            raw_transcript=row["raw_transcript"],
            rewritten=row["rewritten"],
            duration_ms=row["duration_ms"],
            model=row["model"],
            output_mode=row["output_mode"],
        )

    def add(self, session: Session) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sessions "
                "(timestamp, profile, raw_transcript, rewritten, duration_ms, model, output_mode) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session.timestamp,
                    session.profile,
                    session.raw_transcript,
                    session.rewritten,
                    session.duration_ms,
                    session.model,
                    session.output_mode,
                ),
            )
            self._conn.commit()
            session.id = int(cur.lastrowid)
            return session.id

    def recent(self, limit: int = 50) -> list[Session]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_COLUMNS} FROM sessions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def search(self, query: str, limit: int = 50) -> list[Session]:
        match = _fts_query(query)
        if not match:
            return self.recent(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT s.{', s.'.join(_COLUMNS.split(', '))} "
                "FROM sessions s JOIN sessions_fts f ON s.id = f.rowid "
                "WHERE sessions_fts MATCH ? ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        return int(row["n"])

    def delete(self, session_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
