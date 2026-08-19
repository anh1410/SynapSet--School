from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect, dump, load
from app.schemas.template import PaperTemplate


def _row_to_template(row) -> PaperTemplate:
    d = dict(row)
    d["sections"] = load(d["sections"]) or []
    return PaperTemplate.model_validate(d)


class TemplateStore:
    """SQLite-backed store for reusable paper templates (section structure
    only — format/count/difficulty/marks — no topics, since those change
    per actual paper even when the pattern repeats)."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, template: PaperTemplate) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO paper_templates (id, teacher_id, name, duration_minutes, sections, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       teacher_id = excluded.teacher_id, name = excluded.name,
                       duration_minutes = excluded.duration_minutes, sections = excluded.sections,
                       created_at = excluded.created_at""",
                (
                    template.id,
                    template.teacher_id,
                    template.name,
                    template.duration_minutes,
                    dump([s.model_dump(mode="json") for s in template.sections]),
                    template.created_at.isoformat(),
                ),
            )

    def get(self, template_id: str) -> PaperTemplate | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM paper_templates WHERE id = ?", (template_id,)).fetchone()
        return _row_to_template(row) if row else None

    def remove(self, template_id: str) -> bool:
        with connect(self.persist_path) as conn:
            cur = conn.execute("DELETE FROM paper_templates WHERE id = ?", (template_id,))
        return cur.rowcount > 0

    def list_by_teacher(self, teacher_id: str) -> list[PaperTemplate]:
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                "SELECT * FROM paper_templates WHERE teacher_id = ? ORDER BY created_at DESC", (teacher_id,)
            ).fetchall()
        return [_row_to_template(r) for r in rows]


@lru_cache
def get_template_store() -> TemplateStore:
    settings = get_settings()
    return TemplateStore(settings.database_path)
