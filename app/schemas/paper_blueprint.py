from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.schemas.question import QuestionType

BlueprintStatus = Literal["draft", "exported"]


class BlueprintSection(BaseModel):
    id: str
    title: str
    question_format: QuestionType
    question_ids: list[str] = Field(default_factory=list)


class PaperBlueprint(BaseModel):
    id: str
    teacher_id: str
    subject_id: str
    name: str
    total_marks: int
    duration_minutes: int | None = None
    sections: list[BlueprintSection] = Field(default_factory=list)
    status: BlueprintStatus = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def question_ids(self) -> list[str]:
        """Flattened union of every section's question ids, in section order."""
        return [qid for section in self.sections for qid in section.question_ids]
