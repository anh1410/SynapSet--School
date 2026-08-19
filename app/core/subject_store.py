from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect
from app.schemas.subject import Subject


class SubjectStore:
    """SQLite-backed registry of subjects, each owned by a teacher."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, subject: Subject) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO subjects (id, teacher_id, name, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       teacher_id = excluded.teacher_id,
                       name = excluded.name,
                       created_at = excluded.created_at""",
                (subject.id, subject.teacher_id, subject.name, subject.created_at.isoformat()),
            )

    def get(self, subject_id: str) -> Subject | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        return Subject.model_validate(dict(row)) if row else None

    def remove(self, subject_id: str) -> bool:
        with connect(self.persist_path) as conn:
            cur = conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        return cur.rowcount > 0

    def list_by_teacher(self, teacher_id: str) -> list[Subject]:
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                "SELECT * FROM subjects WHERE teacher_id = ? ORDER BY created_at", (teacher_id,)
            ).fetchall()
        return [Subject.model_validate(dict(r)) for r in rows]


@lru_cache
def get_subject_store() -> SubjectStore:
    settings = get_settings()
    return SubjectStore(settings.database_path)
