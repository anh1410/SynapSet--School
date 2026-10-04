from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect, dump, load
from app.schemas.submission import Submission, SubmissionSummary

OPEN_STATUSES = ("submitted", "changes_requested")


def _row_to_submission(row) -> Submission:
    d = dict(row)
    d["question"] = load(d["question"])
    d["duplicates"] = load(d["duplicates"]) or []
    d["history"] = load(d["history"]) or []
    return Submission.model_validate(d)


class SubmissionStore:
    """SQLite-backed store for questions teachers have proposed."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, sub: Submission) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO submissions (
                       id, subject_id, teacher_id, status, question, duplicates, history,
                       admin_comment, reviewed_by, reviewed_at, revision, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       subject_id = excluded.subject_id, teacher_id = excluded.teacher_id,
                       status = excluded.status, question = excluded.question,
                       duplicates = excluded.duplicates, history = excluded.history,
                       admin_comment = excluded.admin_comment, reviewed_by = excluded.reviewed_by,
                       reviewed_at = excluded.reviewed_at, revision = excluded.revision,
                       created_at = excluded.created_at, updated_at = excluded.updated_at""",
                (
                    sub.id,
                    sub.subject_id,
                    sub.teacher_id,
                    sub.status,
                    dump(sub.question.model_dump(mode="json")),
                    dump([d.model_dump(mode="json") for d in sub.duplicates]),
                    dump([e.model_dump(mode="json") for e in sub.history]),
                    sub.admin_comment,
                    sub.reviewed_by,
                    sub.reviewed_at.isoformat() if sub.reviewed_at else None,
                    sub.revision,
                    sub.created_at.isoformat(),
                    sub.updated_at.isoformat(),
                ),
            )

    def set_duplicates(self, submission_id: str, duplicates: list) -> None:
        """Writes only the duplicate list, so a slow background check can't overwrite a
        status/comment an admin or teacher changed while it was running."""
        with connect(self.persist_path) as conn:
            conn.execute(
                "UPDATE submissions SET duplicates = ? WHERE id = ?",
                (dump([d.model_dump(mode="json") for d in duplicates]), submission_id),
            )

    def get(self, submission_id: str) -> Submission | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        return _row_to_submission(row) if row else None

    def delete(self, submission_id: str) -> bool:
        with connect(self.persist_path) as conn:
            cur = conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
        return cur.rowcount > 0

    def find(
        self,
        *,
        subject_id: str | None = None,
        teacher_id: str | None = None,
        status: str | None = None,
    ) -> list[Submission]:
        clauses, params = [], []
        for column, value in (("subject_id", subject_id), ("teacher_id", teacher_id), ("status", status)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect(self.persist_path) as conn:
            rows = conn.execute(f"SELECT * FROM submissions {where} ORDER BY updated_at DESC", params).fetchall()
        return [_row_to_submission(r) for r in rows]

    def list_open_for_subject(self, subject_id: str) -> list[Submission]:
        """Not-yet-decided submissions for a subject: the pool a new submission is
        checked against for near-duplicates, besides the question bank."""
        return [s for s in self.find(subject_id=subject_id) if s.status in OPEN_STATUSES]

    def count_for_teacher(self, teacher_id: str) -> int:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM submissions WHERE teacher_id = ?", (teacher_id,)).fetchone()
        return row["n"]

    def summary(self, teacher_id: str | None = None) -> SubmissionSummary:
        where, params = ("WHERE teacher_id = ?", [teacher_id]) if teacher_id else ("", [])
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                f"SELECT status, COUNT(*) AS n FROM submissions {where} GROUP BY status", params
            ).fetchall()
        return SubmissionSummary(**{r["status"]: r["n"] for r in rows})


@lru_cache
def get_submission_store() -> SubmissionStore:
    settings = get_settings()
    return SubmissionStore(settings.database_path)
