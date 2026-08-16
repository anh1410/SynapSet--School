from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.question import QuestionType

Difficulty = Literal["easy", "medium", "hard"]


class DraftSection(BaseModel):
    id: str
    question_format: QuestionType
    count: int
    topic_ids: list[str] = Field(default_factory=list)
    difficulty: Difficulty = "medium"
    marks_per_question: int
    generated_question_ids: list[str] = Field(default_factory=list)


class BuilderDraft(BaseModel):
    id: str
    teacher_id: str
    subject_id: str
    paper_name: str
    duration_minutes: int | None = None
    sections: list[DraftSection] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
