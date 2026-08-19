from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect
from app.schemas.teacher import Teacher


class TeacherStore:
    """SQLite-backed registry of teacher accounts."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, teacher: Teacher) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO teachers (id, email, name, password_hash, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       email = excluded.email,
                       name = excluded.name,
                       password_hash = excluded.password_hash,
                       created_at = excluded.created_at""",
                (teacher.id, teacher.email, teacher.name, teacher.password_hash, teacher.created_at.isoformat()),
            )

    def get(self, teacher_id: str) -> Teacher | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM teachers WHERE id = ?", (teacher_id,)).fetchone()
        return Teacher.model_validate(dict(row)) if row else None

    def get_by_email(self, email: str) -> Teacher | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM teachers WHERE lower(email) = lower(?)", (email,)).fetchone()
        return Teacher.model_validate(dict(row)) if row else None

    def list(self) -> list[Teacher]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT * FROM teachers ORDER BY created_at").fetchall()
        return [Teacher.model_validate(dict(r)) for r in rows]


@lru_cache
def get_teacher_store() -> TeacherStore:
    settings = get_settings()
    return TeacherStore(settings.database_path)
