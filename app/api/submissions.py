import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api.deps import get_current_teacher, require_admin, require_subject
from app.core.audit_store import record, snippet
from app.core.graph_store import get_graph_store
from app.core.question_bank import get_question_bank
from app.core.subject_store import get_subject_store
from app.core.submission_store import OPEN_STATUSES, get_submission_store
from app.core.teacher_store import get_teacher_store
from app.schemas.duplicate import DuplicateMatch
from app.schemas.question import Question, QuestionType
from app.schemas.submission import (
    DuplicateHit,
    ReviewRequest,
    Submission,
    SubmissionCreate,
    SubmissionEvent,
    SubmissionOut,
    SubmissionStatus,
    SubmissionSummary,
    SubmissionUpdate,
    SubmittedQuestion,
)
from app.schemas.teacher import Teacher
from app.services.difficulty_scoring import score_difficulty
from app.services.duplicate_detection import find_duplicates
from app.services.submission_validation import SubmissionValidationError, build_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/submissions", tags=["submissions"], dependencies=[Depends(get_current_teacher)])

# Same reasoning as _SKIP_SCORING_TYPES in app/api/questions.py: a picture worksheet
# has almost no text, so text-similarity and difficulty scoring mean nothing for it.
_NO_ANALYSIS = {QuestionType.VISUAL_WORKSHEET}
_MAX_HITS = 3

# find_duplicates blends text similarity (50%), shared topics (30%) and same
# type/level/marks (20%) and defaults to a 0.75 cut-off. Topics are optional on a
# submission, so with none tagged even two IDENTICAL questions top out at 0.70 and
# would never be flagged. 0.60 catches near-identical text (semantic >= ~0.8 with
# the same type/level/marks) while leaving unrelated questions (~0.25) well clear.
_DUPLICATE_THRESHOLD = 0.60


# ---------- helpers ----------


def _build_question(payload: SubmittedQuestion, subject_id: str, author_id: str, question_id: str | None = None) -> Question:
    valid_topics = set(get_graph_store(subject_id).graph.nodes)
    try:
        return build_question(
            payload, subject_id=subject_id, author_id=author_id, valid_topic_ids=valid_topics, question_id=question_id
        )
    except SubmissionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _duplicates_for(question: Question) -> list[DuplicateMatch]:
    """Near-duplicates among the subject's bank and its other undecided submissions.
    Best-effort: a failure here must never stop a teacher from submitting."""
    if question.question_type in _NO_ANALYSIS:
        return []
    try:
        pool = [q for q in get_question_bank().list_by_subject(question.subject_id) if q.question_type not in _NO_ANALYSIS]
        pool += [
            s.question
            for s in get_submission_store().list_open_for_subject(question.subject_id)
            if s.question.id != question.id and s.question.question_type not in _NO_ANALYSIS
        ]
        return find_duplicates(question, pool, threshold=_DUPLICATE_THRESHOLD)
    except Exception:  # noqa: BLE001 - see docstring
        logger.exception("Duplicate check failed for a submission; saving it without one")
        return []


def _refresh_duplicates(submission_id: str) -> None:
    """Runs after the response is sent. The similarity model can take many seconds to
    load on a small machine, and the teacher shouldn't sit on "Sending…" for that."""
    sub = get_submission_store().get(submission_id)
    if sub is None or sub.status not in OPEN_STATUSES:
        return
    get_submission_store().set_duplicates(submission_id, _duplicates_for(sub.question))


def _rebuilt(question: Question, original: Submission) -> Question:
    """An edit keeps the question's original timestamp and school year."""
    return question.model_copy(
        update={"created_at": original.question.created_at, "academic_year": original.question.academic_year}
    )


def _difficulty_for(question: Question) -> float | None:
    if question.question_type in _NO_ANALYSIS:
        return None
    try:
        return score_difficulty(question, get_graph_store(question.subject_id)).score
    except Exception:  # noqa: BLE001 - scoring is a nicety, not a reason to block accepting
        logger.exception("Difficulty scoring failed; accepting without a score")
        return None


class _Context:
    """Per-request lookups so listing many submissions doesn't re-query per row."""

    def __init__(self) -> None:
        self.teachers = {t.id: t for t in get_teacher_store().list()}
        self.subjects = {s.id: s for s in get_subject_store().list_all()}
        self._open_questions: dict[str, dict[str, Question]] = {}

    def open_questions(self, subject_id: str) -> dict[str, Question]:
        if subject_id not in self._open_questions:
            self._open_questions[subject_id] = {
                s.question.id: s.question for s in get_submission_store().list_open_for_subject(subject_id)
            }
        return self._open_questions[subject_id]


def _hits(sub: Submission, ctx: _Context) -> list[DuplicateHit]:
    bank = get_question_bank()
    hits: list[DuplicateHit] = []
    for match in sorted(sub.duplicates, key=lambda m: -m.final_score)[:_MAX_HITS]:
        banked = bank.get(match.existing_question_id)
        if banked is not None:
            hits.append(DuplicateHit(question_id=banked.id, text=banked.text, similarity=match.semantic_score, where="bank"))
            continue
        pending = ctx.open_questions(sub.subject_id).get(match.existing_question_id)
        if pending is not None:  # still undecided; a rejected/deleted one is no longer relevant
            hits.append(DuplicateHit(question_id=pending.id, text=pending.text, similarity=match.semantic_score, where="pending"))
    return hits


def _out(sub: Submission, ctx: _Context, *, include_hits: bool) -> SubmissionOut:
    subject = ctx.subjects.get(sub.subject_id)
    author = ctx.teachers.get(sub.teacher_id)
    return SubmissionOut(
        id=sub.id,
        subject_id=sub.subject_id,
        subject_name=subject.name if subject else "(deleted subject)",
        subject_grade=subject.grade if subject else None,
        teacher_id=sub.teacher_id,
        teacher_name=author.name if author else "(deleted account)",
        status=sub.status,
        question=sub.question,
        admin_comment=sub.admin_comment,
        reviewed_at=sub.reviewed_at,
        revision=sub.revision,
        history=sub.history,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        duplicate_hits=_hits(sub, ctx) if include_hits else [],
    )


def _load_visible(submission_id: str, viewer: Teacher) -> Submission:
    """404 (not 403) when it isn't yours, so ids of other teachers' submissions aren't confirmable."""
    sub = get_submission_store().get(submission_id)
    if sub is None or (viewer.role != "admin" and sub.teacher_id != viewer.id):
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


# ---------- teacher & admin ----------


@router.post("", response_model=SubmissionOut)
def create_submission(
    request: SubmissionCreate, background: BackgroundTasks, teacher: Teacher = Depends(get_current_teacher)
) -> SubmissionOut:
    """Propose a question for a subject. Teachers can only do this for subjects an admin assigned to them."""
    require_subject(request.subject_id, teacher)
    question = _build_question(request.question, request.subject_id, author_id=teacher.id)
    sub = Submission(
        id=str(uuid.uuid4()),
        subject_id=request.subject_id,
        teacher_id=teacher.id,
        question=question,
        history=[SubmissionEvent(kind="submitted", by=teacher.id, by_name=teacher.name)],
    )
    get_submission_store().add(sub)
    background.add_task(_refresh_duplicates, sub.id)
    return _out(sub, _Context(), include_hits=teacher.role == "admin")


@router.get("", response_model=list[SubmissionOut])
def list_submissions(
    subject_id: str | None = None,
    grade: str | None = None,
    teacher_id: str | None = None,
    status: SubmissionStatus | None = None,
    question_type: QuestionType | None = None,
    q: str | None = None,
    limit: int = Query(300, ge=1, le=1000),
    teacher: Teacher = Depends(get_current_teacher),
) -> list[SubmissionOut]:
    """Admins see every submission and can filter by grade/subject/teacher/type/status/text.
    A teacher only ever sees their own (the teacher_id filter is forced)."""
    is_admin = teacher.role == "admin"
    ctx = _Context()
    subs = get_submission_store().find(
        subject_id=subject_id, teacher_id=teacher_id if is_admin else teacher.id, status=status
    )
    if grade is not None:
        subs = [s for s in subs if (subj := ctx.subjects.get(s.subject_id)) is not None and subj.grade == grade]
    if question_type is not None:
        subs = [s for s in subs if s.question.question_type == question_type]
    if q and q.strip():
        needle = q.strip().casefold()
        subs = [s for s in subs if needle in s.question.text.casefold()]
    return [_out(s, ctx, include_hits=is_admin) for s in subs[:limit]]


@router.get("/summary", response_model=SubmissionSummary)
def submission_summary(teacher: Teacher = Depends(get_current_teacher)) -> SubmissionSummary:
    """Counts by status: school-wide for admins (drives the pending badge), own for teachers."""
    return get_submission_store().summary(None if teacher.role == "admin" else teacher.id)


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: str, teacher: Teacher = Depends(get_current_teacher)) -> SubmissionOut:
    sub = _load_visible(submission_id, teacher)
    return _out(sub, _Context(), include_hits=teacher.role == "admin")


@router.put("/{submission_id}", response_model=SubmissionOut)
def update_submission(
    submission_id: str,
    request: SubmissionUpdate,
    background: BackgroundTasks,
    teacher: Teacher = Depends(get_current_teacher),
) -> SubmissionOut:
    """The author edits a question that hasn't been decided yet. Editing one the admin sent
    back for changes resubmits it for review."""
    sub = get_submission_store().get(submission_id)
    if sub is None or sub.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status not in OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="This question has already been reviewed and can't be edited")

    question = _rebuilt(_build_question(request.question, sub.subject_id, author_id=sub.teacher_id, question_id=sub.question.id), sub)
    resubmitting = sub.status == "changes_requested"
    event = SubmissionEvent(kind="resubmitted" if resubmitting else "edited", by=teacher.id, by_name=teacher.name)
    updated = sub.model_copy(
        update={
            "question": question,
            "duplicates": [],  # the old hits were for the old text; recomputed below
            "status": "submitted",
            "revision": sub.revision + 1 if resubmitting else sub.revision,
            "admin_comment": None if resubmitting else sub.admin_comment,
            "reviewed_by": None if resubmitting else sub.reviewed_by,
            "reviewed_at": None if resubmitting else sub.reviewed_at,
            "history": [*sub.history, event],
            "updated_at": datetime.now(UTC),
        }
    )
    get_submission_store().add(updated)
    background.add_task(_refresh_duplicates, updated.id)
    return _out(updated, _Context(), include_hits=teacher.role == "admin")


@router.delete("/{submission_id}")
def delete_submission(submission_id: str, teacher: Teacher = Depends(get_current_teacher)) -> dict:
    sub = _load_visible(submission_id, teacher)
    if sub.status == "accepted":
        raise HTTPException(status_code=409, detail="An accepted question is part of the question bank and can't be deleted here")
    get_submission_store().delete(sub.id)
    if sub.teacher_id != teacher.id:
        record(teacher, "submission.delete", f"Deleted {get_teacher_store().get(sub.teacher_id).name if get_teacher_store().get(sub.teacher_id) else 'a teacher'}'s submission: {snippet(sub.question.text)}", "submission", sub.id)
    return {"deleted": sub.id}


# ---------- admin review ----------

_DECISION_STATUS: dict[str, SubmissionStatus] = {
    "accept": "accepted",
    "reject": "rejected",
    "request_changes": "changes_requested",
}


@router.post("/{submission_id}/review", response_model=SubmissionOut)
def review_submission(
    submission_id: str, request: ReviewRequest, admin: Teacher = Depends(require_admin)
) -> SubmissionOut:
    """Accept (the question joins the bank, credited to its author), reject, or send back
    with a comment. Only a submission that is waiting for review can be reviewed."""
    sub = get_submission_store().get(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status != "submitted":
        raise HTTPException(status_code=409, detail="This submission isn't waiting for review")

    comment = (request.comment or "").strip() or None
    if request.decision == "request_changes" and not comment:
        raise HTTPException(status_code=422, detail="Tell the teacher what to change")

    question = sub.question
    if request.decision == "accept":
        if get_subject_store().get(sub.subject_id) is None:
            raise HTTPException(status_code=409, detail="This submission's subject no longer exists")
        if question.difficulty_score is None:  # the teacher's own easy/medium/hard wins over the estimate
            question = question.model_copy(update={"difficulty_score": _difficulty_for(question)})
        get_question_bank().add(question)  # same id as the submission's question, author_id already set

    now = datetime.now(UTC)
    status = _DECISION_STATUS[request.decision]
    updated = sub.model_copy(
        update={
            "question": question,
            "status": status,
            "admin_comment": comment,
            "reviewed_by": admin.id,
            "reviewed_at": now,
            "history": [*sub.history, SubmissionEvent(kind=status, by=admin.id, by_name=admin.name, comment=comment)],
            "updated_at": now,
        }
    )
    get_submission_store().add(updated)
    author = get_teacher_store().get(sub.teacher_id)
    record(
        admin,
        f"submission.{request.decision}",
        f"{ {'accept': 'Accepted', 'reject': 'Rejected', 'request_changes': 'Sent back'}[request.decision] } {author.name if author else 'a teacher'}'s question: {snippet(question.text)}",
        "submission",
        sub.id,
    )
    return _out(updated, _Context(), include_hits=True)


@router.patch("/{submission_id}/question", response_model=SubmissionOut)
def admin_edit_question(
    submission_id: str, request: SubmissionUpdate, background: BackgroundTasks, admin: Teacher = Depends(require_admin)
) -> SubmissionOut:
    """An admin fixes a typo or tidies a waiting submission instead of bouncing it back.
    The author, id and status are untouched; the history records who edited it."""
    sub = get_submission_store().get(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status != "submitted":
        raise HTTPException(status_code=409, detail="Only a submission that is waiting for review can be edited")

    question = _rebuilt(
        _build_question(request.question, sub.subject_id, author_id=sub.teacher_id, question_id=sub.question.id), sub
    )
    updated = sub.model_copy(
        update={
            "question": question,
            "duplicates": [],  # recomputed below
            "history": [*sub.history, SubmissionEvent(kind="edited", by=admin.id, by_name=admin.name)],
            "updated_at": datetime.now(UTC),
        }
    )
    get_submission_store().add(updated)
    background.add_task(_refresh_duplicates, updated.id)
    author = get_teacher_store().get(sub.teacher_id)
    record(
        admin,
        "submission.edit",
        f"Edited {author.name if author else 'a teacher'}'s waiting question: {snippet(question.text)}",
        "submission",
        sub.id,
    )
    return _out(updated, _Context(), include_hits=True)
