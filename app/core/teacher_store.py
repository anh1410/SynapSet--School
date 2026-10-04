from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect
from app.schemas.teacher import Teacher


class TeacherStore:
    """SQLite-backed registry of user accounts (admins and teachers)."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, teacher: Teacher) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO teachers (id, email, name, password_hash, role, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       email = excluded.email,
                       name = excluded.name,
                       password_hash = excluded.password_hash,
                       role = excluded.role,
                       active = excluded.active,
                       created_at = excluded.created_at""",
                (
                    teacher.id,
                    teacher.email,
                    teacher.name,
                    teacher.password_hash,
                    teacher.role,
                    int(teacher.active),
                    teacher.created_at.isoformat(),
                ),
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

    def count_active_admins(self) -> int:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM teachers WHERE role = 'admin' AND active = 1").fetchone()
        return row["n"]

    def remove(self, teacher_id: str) -> bool:
        """Deletes the account and its subject assignments. Subjects themselves
        are school-wide, so they are untouched."""
        with connect(self.persist_path) as conn:
            conn.execute("DELETE FROM teacher_subjects WHERE teacher_id = ?", (teacher_id,))
            cur = conn.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))
        return cur.rowcount > 0


@lru_cache
def get_teacher_store() -> TeacherStore:
    settings = get_settings()
    return TeacherStore(settings.database_path)
