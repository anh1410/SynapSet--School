import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS teachers (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    category TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL,
    topics_extracted INTEGER NOT NULL,
    error_message TEXT,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    text TEXT NOT NULL,
    question_type TEXT NOT NULL,
    marks INTEGER NOT NULL,
    bloom_level INTEGER NOT NULL,
    topic_ids TEXT NOT NULL,
    co_ids TEXT NOT NULL,
    unit INTEGER,
    options TEXT,
    correct_answer TEXT,
    match_pairs TEXT,
    match_right_order TEXT,
    is_true INTEGER,
    difficulty_score REAL,
    embedding_id TEXT,
    is_duplicate_of TEXT,
    source_document TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_blueprints (
    id TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    name TEXT NOT NULL,
    total_marks INTEGER NOT NULL,
    duration_minutes INTEGER,
    sections TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS builder_drafts (
    id TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    paper_name TEXT NOT NULL,
    duration_minutes INTEGER,
    sections TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_templates (
    id TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL,
    name TEXT NOT NULL,
    duration_minutes INTEGER,
    sections TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


@contextmanager
def connect(path: str):
    """A fresh connection per call, scoped to a single `with` block. SQLite's
    own file locking handles concurrent access from FastAPI's threadpool;
    sharing one sqlite3.Connection object across threads is not safe, so we
    deliberately don't cache/reuse connections."""
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def dump(value: Any) -> str:
    return json.dumps(value)


def load(text: str | None) -> Any:
    return json.loads(text) if text is not None else None
