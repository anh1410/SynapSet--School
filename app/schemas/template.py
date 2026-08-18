from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.schemas.draft import Difficulty
from app.schemas.question import QuestionType


class TemplateSection(BaseModel):
    question_format: QuestionType
    count: int
    difficulty: Difficulty = "medium"
    marks_per_question: int


class PaperTemplate(BaseModel):
    id: str
    teacher_id: str
    name: str
    duration_minutes: int | None = None
    sections: list[TemplateSection] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
