from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.core.academic import academic_year_for, check_academic_year, check_term

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
    academic_year: str | None = None  # defaults to the year it was created in
    term: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    _check_term = field_validator("term")(check_term)
    _check_year = field_validator("academic_year")(check_academic_year)

    @model_validator(mode="after")
    def _default_year(self) -> "PaperBlueprint":
        if self.academic_year is None:
            self.academic_year = academic_year_for(self.created_at)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def question_ids(self) -> list[str]:
        """Flattened union of every section's question ids, in section order."""
        return [qid for section in self.sections for qid in section.question_ids]
