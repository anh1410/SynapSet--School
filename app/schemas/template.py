from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.schemas.draft import Difficulty, Language, SectionMode
from app.schemas.question import QuestionType


class TemplateSection(BaseModel):
    question_format: QuestionType
    mode: SectionMode = "specific"
    difficulties: list[Difficulty] = Field(default_factory=list)  # mode == "specific": one per planned question
    difficulty: Difficulty = "medium"  # mode == "random"
    count: int = 3  # mode == "random"
    marks_per_question: int
    language: Language = "English"


class PaperTemplate(BaseModel):
    id: str
    teacher_id: str
    name: str
    duration_minutes: int | None = None
    sections: list[TemplateSection] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
