import logging
import uuid
from datetime import datetime
from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect
from app.schemas.audit import AuditEntry
from app.schemas.teacher import Teacher

logger = logging.getLogger(__name__)

_MAX_SUMMARY = 300


class AuditStore:
    """Append-only record of who changed what, for admins to look back on."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, entry: AuditEntry) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO audit_log (id, at, actor_id, actor_name, action, target_type, target_id, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.id,
                    entry.at.isoformat(),
                    entry.actor_id,
                    entry.actor_name,
                    entry.action,
                    entry.target_type,
                    entry.target_id,
                    entry.summary,
                ),
            )

    def find(
        self,
        *,
        actor_id: str | None = None,
        area: str | None = None,
        action: str | None = None,
        q: str | None = None,
        before: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditEntry], bool]:
        """Newest first. `before` is the `at` of the last row of the previous page.
        Returns (rows, has_more)."""
        clauses, params = [], []
        if actor_id:
            clauses.append("actor_id = ?")
            params.append(actor_id)
        if action:
            clauses.append("action = ?")
            params.append(action)
        elif area:
            clauses.append("action LIKE ?")
            params.append(f"{area}.%")
        if q:
            clauses.append("(summary LIKE ? OR actor_name LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        if before:
            # the API hands out `at` as ISO with a "Z"; rows are stored with "+00:00", and the
            # two don't sort the same as text, so compare in the stored format
            clauses.append("at < ?")
            params.append(datetime.fromisoformat(before).isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY at DESC LIMIT ?", [*params, limit + 1]
            ).fetchall()
        entries = [AuditEntry.model_validate(dict(r)) for r in rows[:limit]]
        return entries, len(rows) > limit


@lru_cache
def get_audit_store() -> AuditStore:
    settings = get_settings()
    return AuditStore(settings.database_path)


def record(actor: Teacher, action: str, summary: str, target_type: str = "", target_id: str = "") -> None:
    """Writes one line to the activity log. Best-effort: a failure here must never
    undo or block the change it describes."""
    try:
        get_audit_store().add(
            AuditEntry(
                id=str(uuid.uuid4()),
                actor_id=actor.id,
                actor_name=actor.name,
                action=action,
                target_type=target_type,
                target_id=target_id,
                summary=" ".join(summary.split())[:_MAX_SUMMARY],
            )
        )
    except Exception:  # noqa: BLE001 - see docstring
        logger.exception("Couldn't write the activity log entry %s", action)


def snippet(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
