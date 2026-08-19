from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect
from app.schemas.document import UploadedDocument


class DocumentStore:
    """SQLite-backed registry of uploaded documents and their ingestion status."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, document: UploadedDocument) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO documents (
                    id, subject_id, filename, category, size_bytes, status,
                    topics_extracted, error_message, uploaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    subject_id = excluded.subject_id, filename = excluded.filename,
                    category = excluded.category, size_bytes = excluded.size_bytes,
                    status = excluded.status, topics_extracted = excluded.topics_extracted,
                    error_message = excluded.error_message, uploaded_at = excluded.uploaded_at""",
                (
                    document.id,
                    document.subject_id,
                    document.filename,
                    document.category,
                    document.size_bytes,
                    document.status,
                    document.topics_extracted,
                    document.error_message,
                    document.uploaded_at.isoformat(),
                ),
            )

    def remove(self, document_id: str) -> bool:
        with connect(self.persist_path) as conn:
            cur = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        return cur.rowcount > 0

    def list_all(self) -> list[UploadedDocument]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
        return [UploadedDocument.model_validate(dict(r)) for r in rows]

    def list_by_subject(self, subject_id: str) -> list[UploadedDocument]:
        with connect(self.persist_path) as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE subject_id = ? ORDER BY uploaded_at DESC", (subject_id,)
            ).fetchall()
        return [UploadedDocument.model_validate(dict(r)) for r in rows]


@lru_cache
def get_document_store() -> DocumentStore:
    settings = get_settings()
    return DocumentStore(settings.database_path)
