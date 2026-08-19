from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect, dump, load
from app.schemas.draft import BuilderDraft


def _row_to_draft(row) -> BuilderDraft:
    d = dict(row)
    d["sections"] = load(d["sections"]) or []
    return BuilderDraft.model_validate(d)


class DraftStore:
    """SQLite-backed store for in-progress Question Paper Builder drafts.
    One draft per (teacher_id, subject_id) — starting a new paper for the
    same subject overwrites the previous unsaved draft."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def get_for_subject(self, teacher_id: str, subject_id: str) -> BuilderDraft | None:
        with connect(self.persist_path) as conn:
            row = conn.execute(
                "SELECT * FROM builder_drafts WHERE teacher_id = ? AND subject_id = ?",
                (teacher_id, subject_id),
            ).fetchone()
        return _row_to_draft(row) if row else None

    def upsert(self, draft: BuilderDraft) -> None:
        with connect(self.persist_path) as conn:
            # Enforce one draft per (teacher, subject): drop any existing draft
            # for this pair under a different id before storing the new one.
            conn.execute(
                "DELETE FROM builder_drafts WHERE teacher_id = ? AND subject_id = ? AND id != ?",
                (draft.teacher_id, draft.subject_id, draft.id),
            )
            conn.execute(
                """INSERT INTO builder_drafts (id, teacher_id, subject_id, paper_name, duration_minutes, sections, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       teacher_id = excluded.teacher_id, subject_id = excluded.subject_id,
                       paper_name = excluded.paper_name, duration_minutes = excluded.duration_minutes,
                       sections = excluded.sections, updated_at = excluded.updated_at""",
                (
                    draft.id,
                    draft.teacher_id,
                    draft.subject_id,
                    draft.paper_name,
                    draft.duration_minutes,
                    dump([s.model_dump(mode="json") for s in draft.sections]),
                    draft.updated_at.isoformat(),
                ),
            )

    def clear(self, teacher_id: str, subject_id: str) -> bool:
        with connect(self.persist_path) as conn:
            cur = conn.execute(
                "DELETE FROM builder_drafts WHERE teacher_id = ? AND subject_id = ?",
                (teacher_id, subject_id),
            )
        return cur.rowcount > 0


@lru_cache
def get_draft_store() -> DraftStore:
    settings = get_settings()
    return DraftStore(settings.database_path)
