from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.question import DiagramSpec, GridLayout, MatchPair, QuestionType

BloomLevelName = Literal["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"]


class GeneratedQuestionDraft(BaseModel):
    text: str
    question_type: QuestionType
    bloom_level: BloomLevelName
    marks: int
    options: list[str] | None = None
    correct_answer: str | None = None
    match_pairs: list[MatchPair] | None = None
    is_true: bool | None = None
    diagram: DiagramSpec | None = None  # stem_diagram only; image_id is always null here, backend-resolved
    grid_layout: GridLayout | None = None  # visual_worksheet only; item image_ids always null here
    topic_names: list[str] = Field(default_factory=list)
    co_codes: list[str] = Field(default_factory=list)


class QuestionDraftBatch(BaseModel):
    questions: list[GeneratedQuestionDraft] = Field(default_factory=list)
