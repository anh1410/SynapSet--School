from datetime import UTC, datetime
from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect
from app.schemas.subject import Subject


class SubjectStore:
    """SQLite-backed registry of school-wide subjects, plus which teachers
    are assigned to each (teacher_subjects). Admins manage both."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, subject: Subject) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO subjects (id, teacher_id, name, grade, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       teacher_id = excluded.teacher_id,
                       name = excluded.name,
                       grade = excluded.grade,
                       created_at = excluded.created_at""",
                (subject.id, subject.teacher_id, subject.name, subject.grade, subject.created_at.isoformat()),
            )

    def get(self, subject_id: str) -> Subject | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        return Subject.model_validate(dict(row)) if row else None

    def remove(self, subject_id: str) -> bool:
        with connect(self.persist_path) as conn:
            conn.execute("DELETE FROM teacher_subjects WHERE subject_id = ?", (subject_id,))
            cur = conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        return cur.rowcount > 0

    def list_all(self) -> list[Subject]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT * FROM subjects ORDER BY created_at").fetchall()
        return [Subject.model_validate(dict(r)) for r in rows]

    def list_for_teacher(self, teacher_id: str) -> list[Subject]:
        """Only the subjects an admin has assigned to this teacher."""
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                """SELECT s.* FROM subjects s
                   JOIN teacher_subjects ts ON ts.subject_id = s.id
                   WHERE ts.teacher_id = ? ORDER BY s.created_at""",
                (teacher_id,),
            ).fetchall()
        return [Subject.model_validate(dict(r)) for r in rows]

    def is_assigned(self, teacher_id: str, subject_id: str) -> bool:
        with connect(self.persist_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM teacher_subjects WHERE teacher_id = ? AND subject_id = ?", (teacher_id, subject_id)
            ).fetchone()
        return row is not None

    def assignments_by_teacher(self) -> dict[str, list[str]]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT teacher_id, subject_id FROM teacher_subjects ORDER BY assigned_at").fetchall()
        result: dict[str, list[str]] = {}
        for r in rows:
            result.setdefault(r["teacher_id"], []).append(r["subject_id"])
        return result

    def assign(self, teacher_id: str, subject_id: str) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO teacher_subjects (teacher_id, subject_id, assigned_at) VALUES (?, ?, ?)",
                (teacher_id, subject_id, datetime.now(UTC).isoformat()),
            )

    def set_teacher_subjects(self, teacher_id: str, subject_ids: list[str]) -> None:
        """Replaces the teacher's whole assignment list in one transaction."""
        wanted = list(dict.fromkeys(subject_ids))  # dedupe, keep order
        now = datetime.now(UTC).isoformat()
        with connect(self.persist_path) as conn:
            conn.execute("DELETE FROM teacher_subjects WHERE teacher_id = ?", (teacher_id,))
            conn.executemany(
                "INSERT INTO teacher_subjects (teacher_id, subject_id, assigned_at) VALUES (?, ?, ?)",
                [(teacher_id, sid, now) for sid in wanted],
            )


@lru_cache
def get_subject_store() -> SubjectStore:
    settings = get_settings()
    return SubjectStore(settings.database_path)
