from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.bloom import BloomLevel


class QuestionType(str, Enum):
    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    NUMERICAL = "numerical"
    FILL_IN_BLANK = "fill_in_blank"
    MATCH_FOLLOWING = "match_following"
    TRUE_FALSE = "true_false"


class MatchPair(BaseModel):
    left: str
    right: str


class Question(BaseModel):
    id: str
    subject_id: str
    text: str
    question_type: QuestionType
    marks: int
    bloom_level: BloomLevel
    topic_ids: list[str] = Field(default_factory=list)
    co_ids: list[str] = Field(default_factory=list)
    unit: int | None = None

    options: list[str] | None = None  # MCQ choices
    correct_answer: str | None = None  # MCQ/short/long/numerical/fill_in_blank answer
    match_pairs: list[MatchPair] | None = None  # match_following only; index i's left matches index i's right
    match_right_order: list[int] | None = None  # match_following only; display permutation for Column B
    is_true: bool | None = None  # true_false only

    difficulty_score: float | None = None  # 1-10, set by difficulty scorer (Phase 5)
    embedding_id: str | None = None  # reference into the vector store
    is_duplicate_of: str | None = None  # id of the original question, if flagged

    source_document: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
