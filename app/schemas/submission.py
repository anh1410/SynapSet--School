from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.academic import check_term

from app.schemas.bloom import BloomLevel
from app.schemas.duplicate import DuplicateMatch
from app.schemas.question import GridLayoutKind, MatchPair, Question, QuestionType, ResponseStyle

SubmissionStatus = Literal["submitted", "changes_requested", "accepted", "rejected"]
EventKind = Literal["submitted", "edited", "resubmitted", "changes_requested", "accepted", "rejected"]


# ---------- what a teacher is allowed to send ----------
# Deliberately NOT the full Question model: a teacher must not be able to set the
# id, authorship, difficulty score, duplicate flags or source document.


class SubmittedDiagram(BaseModel):
    image_id: str  # from POST /api/v1/images
    caption: str | None = None


class SubmittedGridItem(BaseModel):
    image_id: str
    label: str | None = None
    is_correct: bool | None = None


class SubmittedGrid(BaseModel):
    kind: GridLayoutKind
    response_style: ResponseStyle
    items: list[SubmittedGridItem] = Field(default_factory=list)


class SubmittedQuestion(BaseModel):
    text: str
    question_type: QuestionType
    marks: int
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND  # ignored when `difficulty` is given
    difficulty: Literal["easy", "medium", "hard"] | None = None  # the teacher's own call
    term: str | None = None  # which term the question is for; the school year is automatic
    topic_ids: list[str] = Field(default_factory=list)
    options: list[str] | None = None
    correct_answer: str | None = None
    match_pairs: list[MatchPair] | None = None
    is_true: bool | None = None
    diagram: SubmittedDiagram | None = None
    grid_layout: SubmittedGrid | None = None

    _term = field_validator("term")(check_term)


class SubmissionCreate(BaseModel):
    subject_id: str
    question: SubmittedQuestion


class SubmissionUpdate(BaseModel):
    question: SubmittedQuestion


class ReviewRequest(BaseModel):
    decision: Literal["accept", "reject", "request_changes"]
    comment: str | None = None


# ---------- stored ----------


class SubmissionEvent(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: EventKind
    by: str  # account id
    by_name: str
    comment: str | None = None


class Submission(BaseModel):
    id: str
    subject_id: str
    teacher_id: str
    status: SubmissionStatus = "submitted"
    question: Question
    duplicates: list[DuplicateMatch] = Field(default_factory=list)  # kept server-side; only admins see them (as DuplicateHit)
    history: list[SubmissionEvent] = Field(default_factory=list)
    admin_comment: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    revision: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------- what the API returns ----------


class DuplicateHit(BaseModel):
    question_id: str
    text: str
    similarity: float  # 0..1 text similarity (semantic), the number an admin actually cares about
    where: Literal["bank", "pending"]


class SubmissionOut(BaseModel):
    id: str
    subject_id: str
    subject_name: str
    subject_grade: str | None
    teacher_id: str
    teacher_name: str
    status: SubmissionStatus
    question: Question
    admin_comment: str | None
    reviewed_at: datetime | None
    revision: int
    history: list[SubmissionEvent]
    created_at: datetime
    updated_at: datetime
    # Populated for admins only. A teacher must never see other questions' text
    # (bank questions may be future exam content).
    duplicate_hits: list[DuplicateHit] = Field(default_factory=list)


class SubmissionSummary(BaseModel):
    submitted: int = 0
    changes_requested: int = 0
    accepted: int = 0
    rejected: int = 0
