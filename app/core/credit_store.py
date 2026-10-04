import uuid
from datetime import UTC, datetime
from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect
from app.schemas.credit import Credit
from app.schemas.question import Question


def _row_to_credit(row) -> Credit:
    return Credit.model_validate(dict(row))


class CreditStore:
    """SQLite-backed store of the credits teachers earn when their questions land in an exported paper."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def sync_paper(self, blueprint_id: str, subject_id: str, exam_name: str, questions: list[Question]) -> None:
        """Makes this paper's credits match `questions` exactly: new authored questions
        earn a credit, ones removed since an earlier export lose it, and a renamed exam
        updates its name. Safe to call on every export."""
        authored = {q.id: q for q in questions if q.author_id}
        now = datetime.now(UTC).isoformat()
        with connect(self.persist_path) as conn:
            existing = {
                r["question_id"]
                for r in conn.execute("SELECT question_id FROM credits WHERE blueprint_id = ?", (blueprint_id,))
            }
            for stale in existing - authored.keys():
                conn.execute("DELETE FROM credits WHERE blueprint_id = ? AND question_id = ?", (blueprint_id, stale))
            conn.execute("UPDATE credits SET exam_name = ? WHERE blueprint_id = ?", (exam_name, blueprint_id))
            for q in authored.values():
                if q.id in existing:
                    continue
                conn.execute(
                    """INSERT INTO credits (
                           id, teacher_id, question_id, blueprint_id, subject_id, exam_name,
                           question_text, question_type, marks, earned_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        q.author_id,
                        q.id,
                        blueprint_id,
                        subject_id,
                        exam_name,
                        q.text,
                        q.question_type.value,
                        q.marks,
                        now,
                    ),
                )

    def list_for_teacher(self, teacher_id: str) -> list[Credit]:
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                "SELECT * FROM credits WHERE teacher_id = ? ORDER BY earned_at DESC", (teacher_id,)
            ).fetchall()
        return [_row_to_credit(r) for r in rows]

    def counts_by_teacher(self) -> dict[str, int]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT teacher_id, COUNT(*) AS n FROM credits GROUP BY teacher_id").fetchall()
        return {r["teacher_id"]: r["n"] for r in rows}


@lru_cache
def get_credit_store() -> CreditStore:
    settings = get_settings()
    return CreditStore(settings.database_path)
