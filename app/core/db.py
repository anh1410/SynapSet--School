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
    role TEXT NOT NULL DEFAULT 'teacher',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Subjects are school-wide and managed by admins; teacher_id records which
-- admin created it, it does NOT grant access (teacher_subjects does).
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL,
    name TEXT NOT NULL,
    grade TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher_subjects (
    teacher_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (teacher_id, subject_id)
);

-- Questions teachers propose for a subject. The question body is JSON; when
-- accepted it is copied into `questions` under the same id.
CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    teacher_id TEXT NOT NULL,
    status TEXT NOT NULL,
    question TEXT NOT NULL,
    duplicates TEXT NOT NULL,
    history TEXT NOT NULL,
    admin_comment TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions (status);
CREATE INDEX IF NOT EXISTS idx_submissions_subject ON submissions (subject_id);
CREATE INDEX IF NOT EXISTS idx_submissions_teacher ON submissions (teacher_id);

-- One credit per teacher-authored question per exported paper. The question text and
-- exam name are snapshots, so a credit still reads correctly if the bank question or
-- the paper is renamed or removed later.
CREATE TABLE IF NOT EXISTS credits (
    id TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    blueprint_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    exam_name TEXT NOT NULL,
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL,
    marks INTEGER NOT NULL,
    earned_at TEXT NOT NULL,
    UNIQUE (question_id, blueprint_id)
);
CREATE INDEX IF NOT EXISTS idx_credits_teacher ON credits (teacher_id);

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
    diagram TEXT,
    grid_layout TEXT,
    difficulty_score REAL,
    embedding_id TEXT,
    is_duplicate_of TEXT,
    source_document TEXT,
    author_id TEXT,
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


# Columns added after a table's original CREATE TABLE shipped. CREATE TABLE
# IF NOT EXISTS only helps brand-new databases; existing ones need each
# column added explicitly. Safe to re-run — duplicate-column errors are
# swallowed.
_MIGRATIONS = [
    "ALTER TABLE questions ADD COLUMN diagram TEXT",
    "ALTER TABLE questions ADD COLUMN grid_layout TEXT",
    "ALTER TABLE teachers ADD COLUMN role TEXT NOT NULL DEFAULT 'teacher'",
    "ALTER TABLE teachers ADD COLUMN active INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE subjects ADD COLUMN grade TEXT",
    "ALTER TABLE questions ADD COLUMN author_id TEXT",
]


def _connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    for migration in _MIGRATIONS:
        try:
            conn.execute(migration)
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                raise
    conn.commit()
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
