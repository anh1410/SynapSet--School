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
    STEM_DIAGRAM = "stem_diagram"
    VISUAL_WORKSHEET = "visual_worksheet"


class MatchPair(BaseModel):
    left: str
    right: str


class DiagramKind(str, Enum):
    MATPLOTLIB = "matplotlib"
    TIKZ = "tikz"
    IMAGE = "image"  # a picture a teacher uploaded; never produced by generation


class DiagramSpec(BaseModel):
    """A geometry/physics diagram for a stem_diagram question. `source_code`
    is always kept (for transparency/re-render); `image_id` is set only
    after successful server-side execution, `render_error` only after a
    failed one — never both."""

    kind: DiagramKind
    source_code: str
    image_id: str | None = None
    caption: str | None = None
    render_error: str | None = None


class VisualPrompt(BaseModel):
    """One parameterized image request for a visual_worksheet grid item.
    `full_prompt` is what's actually sent to the image generator; the other
    fields are kept so the prompt's variety is visible/debuggable, not just
    a single opaque string."""

    subject: str
    style: str
    action: str | None = None
    background: str | None = None
    full_prompt: str
    image_id: str | None = None


class GridItem(BaseModel):
    visual: VisualPrompt
    label: str | None = None
    is_correct: bool | None = None  # for choice-selection grids, marks the right answer(s)


class GridLayoutKind(str, Enum):
    GRID_2X4 = "grid_2x4"
    TWO_COLUMN_MATCH = "two_column_match"
    SINGLE_ROW = "single_row"


class ResponseStyle(str, Enum):
    CIRCLE_CHOICE = "circle_choice"
    BLANK_LINE = "blank_line"
    MATCH_LINES = "match_lines"


class GridLayout(BaseModel):
    kind: GridLayoutKind
    items: list[GridItem] = Field(default_factory=list)
    response_style: ResponseStyle
    instruction: str | None = None


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
    diagram: DiagramSpec | None = None  # stem_diagram only
    grid_layout: GridLayout | None = None  # visual_worksheet only

    difficulty_score: float | None = None  # 1-10, set by difficulty scorer (Phase 5)
    embedding_id: str | None = None  # reference into the vector store
    is_duplicate_of: str | None = None  # id of the original question, if flagged

    source_document: str | None = None
    author_id: str | None = None  # the account that submitted it (None for AI-generated questions)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
