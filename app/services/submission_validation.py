"""Turns what a teacher typed into a clean, trustworthy Question.

A teacher's form is free-form (add/remove options, pairs, pictures...), so every
rule that makes a question usable on an exam lives here, on the server, rather
than being trusted to the browser."""

import uuid

from app.core.image_store import image_path
from app.schemas.bloom import BloomLevel
from app.schemas.question import (
    DiagramKind,
    DiagramSpec,
    GridItem,
    GridLayout,
    MatchPair,
    Question,
    QuestionType,
    ResponseStyle,
    VisualPrompt,
)
from app.schemas.submission import SubmittedQuestion
from app.services.question_generation import _shuffled_match_order

MAX_TEXT = 4000
MAX_MARKS = 100
MIN_OPTIONS, MAX_OPTIONS = 2, 8
MIN_PAIRS, MAX_PAIRS = 2, 10
MIN_GRID_ITEMS, MAX_GRID_ITEMS = 2, 8
MAX_LABEL = 100
MAX_CAPTION = 200

# A teacher picks easy/medium/hard. The paper builder still wants a Bloom level and a
# 0-10 score, so derive both. Scores sit mid-bucket for the UI's thresholds (<=4 easy, <=7 medium).
_BLOOM_FOR_DIFFICULTY = {"easy": BloomLevel.REMEMBER, "medium": BloomLevel.APPLY, "hard": BloomLevel.ANALYZE}
_SCORE_FOR_DIFFICULTY = {"easy": 2.5, "medium": 5.5, "hard": 8.5}

# Types whose answer is free text the admin needs for the answer key.
_NEEDS_TEXT_ANSWER = {
    QuestionType.SHORT_ANSWER,
    QuestionType.LONG_ANSWER,
    QuestionType.NUMERICAL,
    QuestionType.FILL_IN_BLANK,
    QuestionType.STEM_DIAGRAM,
}


class SubmissionValidationError(ValueError):
    """The submission isn't acceptable; the message is written for the teacher."""


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _require_image(image_id: str) -> str:
    if image_path(image_id) is None:
        raise SubmissionValidationError("A picture you attached couldn't be found. Please upload it again.")
    return image_id


def _topics(payload: SubmittedQuestion, valid_topic_ids: set[str]) -> list[str]:
    topic_ids = list(dict.fromkeys(payload.topic_ids))
    unknown = [t for t in topic_ids if t not in valid_topic_ids]
    if unknown:
        raise SubmissionValidationError("One of the topics you picked doesn't exist for this subject any more")
    return topic_ids


def _mcq_fields(payload: SubmittedQuestion) -> dict:
    options = [_clean(o) for o in (payload.options or [])]
    if any(not o for o in options):
        raise SubmissionValidationError("Fill in every option, or remove the empty ones")
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise SubmissionValidationError(f"A multiple-choice question needs {MIN_OPTIONS} to {MAX_OPTIONS} options")
    if len({o.casefold() for o in options}) != len(options):
        raise SubmissionValidationError("Two options are the same; each option must be different")
    answer = _clean(payload.correct_answer)
    if answer not in options:
        raise SubmissionValidationError("Mark which option is the correct answer")
    return {"options": options, "correct_answer": answer}


def _match_fields(payload: SubmittedQuestion) -> dict:
    pairs = [MatchPair(left=_clean(p.left), right=_clean(p.right)) for p in (payload.match_pairs or [])]
    if any(not p.left or not p.right for p in pairs):
        raise SubmissionValidationError("Fill in both sides of every pair, or remove the empty rows")
    if not MIN_PAIRS <= len(pairs) <= MAX_PAIRS:
        raise SubmissionValidationError(f"A match-the-following question needs {MIN_PAIRS} to {MAX_PAIRS} pairs")
    # Column B is shown shuffled so it isn't just the answers in order.
    return {"match_pairs": pairs, "match_right_order": _shuffled_match_order(len(pairs))}


def _text_answer_fields(payload: SubmittedQuestion, text: str) -> dict:
    answer = _clean(payload.correct_answer)
    if not answer:
        raise SubmissionValidationError("Write the answer, so it can go in the answer key")
    if len(answer) > MAX_TEXT:
        raise SubmissionValidationError("The answer is too long")
    if payload.question_type == QuestionType.FILL_IN_BLANK and "___" not in text:
        raise SubmissionValidationError('Put a blank (____) in the sentence where the missing word goes')
    return {"correct_answer": answer}


def _worksheet_fields(payload: SubmittedQuestion, text: str) -> dict:
    grid = payload.grid_layout
    if grid is None:
        raise SubmissionValidationError("Add the pictures for this worksheet")
    if not MIN_GRID_ITEMS <= len(grid.items) <= MAX_GRID_ITEMS:
        raise SubmissionValidationError(f"A picture worksheet needs {MIN_GRID_ITEMS} to {MAX_GRID_ITEMS} pictures")

    items = []
    for item in grid.items:
        label = _clean(item.label)[:MAX_LABEL] or None
        image_id = _require_image(item.image_id)
        items.append(
            GridItem(
                visual=VisualPrompt(
                    subject=label or "picture",
                    style="uploaded",
                    full_prompt=label or "uploaded picture",
                    image_id=image_id,
                ),
                label=label,
                is_correct=item.is_correct,
            )
        )
    if grid.response_style == ResponseStyle.CIRCLE_CHOICE and not any(i.is_correct for i in items):
        raise SubmissionValidationError("Tick which picture(s) the child should circle")

    # instruction = the question text, exactly like generated worksheets (see _resolve_grid_layout)
    return {
        "grid_layout": GridLayout(
            kind=grid.kind, items=items, response_style=grid.response_style, instruction=text
        )
    }


def build_question(
    payload: SubmittedQuestion,
    *,
    subject_id: str,
    author_id: str,
    valid_topic_ids: set[str],
    question_id: str | None = None,
) -> Question:
    """Validates `payload` and returns the Question it describes.

    Fields that don't belong to the chosen type are discarded, so changing the
    type mid-edit can't leave stray options or pairs behind."""
    qtype = payload.question_type
    text = _clean(payload.text)
    if not text:
        raise SubmissionValidationError("Write the question")
    if len(text) > MAX_TEXT:
        raise SubmissionValidationError(f"The question is too long (max {MAX_TEXT} characters)")
    if not 1 <= payload.marks <= MAX_MARKS:
        raise SubmissionValidationError(f"Marks must be between 1 and {MAX_MARKS}")

    fields: dict = {}
    bloom = payload.bloom_level
    difficulty_score: float | None = None
    if payload.difficulty is not None:
        bloom = _BLOOM_FOR_DIFFICULTY[payload.difficulty]
        difficulty_score = _SCORE_FOR_DIFFICULTY[payload.difficulty]
    if qtype == QuestionType.MCQ:
        fields = _mcq_fields(payload)
    elif qtype == QuestionType.MATCH_FOLLOWING:
        fields = _match_fields(payload)
    elif qtype == QuestionType.TRUE_FALSE:
        if payload.is_true is None:
            raise SubmissionValidationError("Choose whether the statement is True or False")
        fields = {"is_true": payload.is_true}
    elif qtype == QuestionType.VISUAL_WORKSHEET:
        fields = _worksheet_fields(payload, text)
        bloom = BloomLevel.REMEMBER  # same as generated LKG/UKG worksheets: definitionally recall
        difficulty_score = None  # worksheets are never scored
    elif qtype in _NEEDS_TEXT_ANSWER:
        fields = _text_answer_fields(payload, text)
    else:  # pragma: no cover - every QuestionType is handled above
        raise SubmissionValidationError("Unsupported question type")

    if payload.diagram is not None:
        if qtype == QuestionType.VISUAL_WORKSHEET:
            raise SubmissionValidationError("A picture worksheet uses its own pictures, not a separate diagram")
        fields["diagram"] = DiagramSpec(
            kind=DiagramKind.IMAGE,
            source_code="",
            image_id=_require_image(payload.diagram.image_id),
            caption=_clean(payload.diagram.caption)[:MAX_CAPTION] or None,
        )

    return Question(
        id=question_id or str(uuid.uuid4()),
        subject_id=subject_id,
        author_id=author_id,
        text=text,
        question_type=qtype,
        marks=payload.marks,
        bloom_level=bloom,
        difficulty_score=difficulty_score,
        term=payload.term,
        topic_ids=_topics(payload, valid_topic_ids),
        **fields,
    )
