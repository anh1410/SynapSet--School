from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.question import QuestionType

Difficulty = Literal["easy", "medium", "hard"]
SectionMode = Literal["specific", "random"]
Language = Literal["English", "Hindi", "Kannada"]


class DraftQuestionSpec(BaseModel):
    id: str
    topic_id: str
    difficulty: Difficulty = "medium"


class DraftSection(BaseModel):
    id: str
    question_format: QuestionType
    mode: SectionMode = "specific"
    questions: list[DraftQuestionSpec] = Field(default_factory=list)  # mode == "specific"
    topic_ids: list[str] = Field(default_factory=list)  # mode == "random"
    difficulty: Difficulty = "medium"  # mode == "random"
    count: int = 3  # mode == "random"
    marks_per_question: int
    language: Language = "English"
    generated_question_ids: list[str] = Field(default_factory=list)


class BuilderDraft(BaseModel):
    id: str
    teacher_id: str
    subject_id: str
    paper_name: str
    duration_minutes: int | None = None
    sections: list[DraftSection] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
