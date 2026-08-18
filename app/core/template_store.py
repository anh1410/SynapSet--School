import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.schemas.template import PaperTemplate


class TemplateStore:
    """JSON-file-backed store for reusable paper templates (section structure
    only — format/count/difficulty/marks — no topics, since those change
    per actual paper even when the pattern repeats)."""

    def __init__(self, persist_path: str):
        self.persist_path = Path(persist_path)
        self.templates: dict[str, PaperTemplate] = self._load()

    def _load(self) -> dict[str, PaperTemplate]:
        if self.persist_path.exists():
            data = json.loads(self.persist_path.read_text(encoding="utf-8"))
            return {row["id"]: PaperTemplate.model_validate(row) for row in data}
        return {}

    def save(self) -> None:
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = [t.model_dump(mode="json") for t in self.templates.values()]
        self.persist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, template: PaperTemplate) -> None:
        self.templates[template.id] = template
        self.save()

    def get(self, template_id: str) -> PaperTemplate | None:
        return self.templates.get(template_id)

    def remove(self, template_id: str) -> bool:
        if template_id in self.templates:
            del self.templates[template_id]
            self.save()
            return True
        return False

    def list_by_teacher(self, teacher_id: str) -> list[PaperTemplate]:
        return sorted(
            (t for t in self.templates.values() if t.teacher_id == teacher_id),
            key=lambda t: t.created_at,
            reverse=True,
        )


@lru_cache
def get_template_store() -> TemplateStore:
    settings = get_settings()
    return TemplateStore(settings.template_store_path)
