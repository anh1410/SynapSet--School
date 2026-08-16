import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.schemas.draft import BuilderDraft


class DraftStore:
    """JSON-file-backed store for in-progress Question Paper Builder drafts.
    One draft per (teacher_id, subject_id) — starting a new paper for the
    same subject overwrites the previous unsaved draft."""

    def __init__(self, persist_path: str):
        self.persist_path = Path(persist_path)
        self.drafts: dict[str, BuilderDraft] = self._load()

    def _key(self, teacher_id: str, subject_id: str) -> str:
        return f"{teacher_id}:{subject_id}"

    def _load(self) -> dict[str, BuilderDraft]:
        if self.persist_path.exists():
            data = json.loads(self.persist_path.read_text(encoding="utf-8"))
            return {row["id"]: BuilderDraft.model_validate(row) for row in data}
        return {}

    def save(self) -> None:
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = [d.model_dump(mode="json") for d in self.drafts.values()]
        self.persist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_for_subject(self, teacher_id: str, subject_id: str) -> BuilderDraft | None:
        key = self._key(teacher_id, subject_id)
        for draft in self.drafts.values():
            if self._key(draft.teacher_id, draft.subject_id) == key:
                return draft
        return None

    def upsert(self, draft: BuilderDraft) -> None:
        # Enforce one draft per (teacher, subject): drop any existing draft for
        # this pair under a different id before storing the new one.
        key = self._key(draft.teacher_id, draft.subject_id)
        stale = [
            d.id
            for d in self.drafts.values()
            if self._key(d.teacher_id, d.subject_id) == key and d.id != draft.id
        ]
        for stale_id in stale:
            del self.drafts[stale_id]
        self.drafts[draft.id] = draft
        self.save()

    def clear(self, teacher_id: str, subject_id: str) -> bool:
        key = self._key(teacher_id, subject_id)
        match = next((d for d in self.drafts.values() if self._key(d.teacher_id, d.subject_id) == key), None)
        if match is None:
            return False
        del self.drafts[match.id]
        self.save()
        return True


@lru_cache
def get_draft_store() -> DraftStore:
    settings = get_settings()
    return DraftStore(settings.draft_store_path)
