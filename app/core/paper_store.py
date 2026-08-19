from datetime import UTC, datetime
from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect, dump, load
from app.schemas.paper_blueprint import PaperBlueprint


def _row_to_blueprint(row) -> PaperBlueprint:
    d = dict(row)
    d["sections"] = load(d["sections"]) or []
    return PaperBlueprint.model_validate(d)


class PaperStore:
    """SQLite-backed store for saved exam paper blueprints (draft/exported)."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, blueprint: PaperBlueprint) -> None:
        blueprint.updated_at = datetime.now(UTC)
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO paper_blueprints (
                    id, teacher_id, subject_id, name, total_marks, duration_minutes,
                    sections, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    teacher_id = excluded.teacher_id, subject_id = excluded.subject_id,
                    name = excluded.name, total_marks = excluded.total_marks,
                    duration_minutes = excluded.duration_minutes, sections = excluded.sections,
                    status = excluded.status, created_at = excluded.created_at,
                    updated_at = excluded.updated_at""",
                (
                    blueprint.id,
                    blueprint.teacher_id,
                    blueprint.subject_id,
                    blueprint.name,
                    blueprint.total_marks,
                    blueprint.duration_minutes,
                    dump([s.model_dump(mode="json") for s in blueprint.sections]),
                    blueprint.status,
                    blueprint.created_at.isoformat(),
                    blueprint.updated_at.isoformat(),
                ),
            )

    def remove(self, blueprint_id: str) -> bool:
        with connect(self.persist_path) as conn:
            cur = conn.execute("DELETE FROM paper_blueprints WHERE id = ?", (blueprint_id,))
        return cur.rowcount > 0

    def list_all(self) -> list[PaperBlueprint]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT * FROM paper_blueprints ORDER BY updated_at DESC").fetchall()
        return [_row_to_blueprint(r) for r in rows]

    def list_by_teacher(self, teacher_id: str) -> list[PaperBlueprint]:
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                "SELECT * FROM paper_blueprints WHERE teacher_id = ? ORDER BY updated_at DESC", (teacher_id,)
            ).fetchall()
        return [_row_to_blueprint(r) for r in rows]

    def get(self, blueprint_id: str) -> PaperBlueprint | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM paper_blueprints WHERE id = ?", (blueprint_id,)).fetchone()
        return _row_to_blueprint(row) if row else None


@lru_cache
def get_paper_store() -> PaperStore:
    settings = get_settings()
    return PaperStore(settings.database_path)
