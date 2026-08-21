from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_teacher, require_subject
from app.core.graph_store import get_graph_store
from app.core.question_bank import get_question_bank
from app.schemas.bloom import BloomLevel
from app.schemas.course_outcome import CourseOutcome
from app.schemas.difficulty import DifficultyScore
from app.schemas.duplicate import DuplicateMatch
from app.schemas.question import Question, QuestionType
from app.schemas.teacher import Teacher
from app.services.difficulty_scoring import score_difficulty
from app.services.duplicate_detection import find_duplicates
from app.services.question_generation import generate_questions, generate_section_questions

router = APIRouter(prefix="/api/v1/questions", tags=["questions"], dependencies=[Depends(get_current_teacher)])


class GenerateQuestionsRequest(BaseModel):
    subject_id: str
    topic: str
    num_questions: int = 3
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    marks: int = 5
    question_type: QuestionType = QuestionType.SHORT_ANSWER
    course_outcomes: list[CourseOutcome] | None = None
    check_duplicates: bool = True
    save_to_bank: bool = False


class GeneratedQuestionResult(BaseModel):
    question: Question
    difficulty: DifficultyScore
    duplicate_matches: list[DuplicateMatch] = []


class GenerateQuestionsResponse(BaseModel):
    results: list[GeneratedQuestionResult]


# Bloom/difficulty-scoring and duplicate-detection assume real gradable text.
# visual_worksheet questions have near-empty `text` (an instruction line at
# most), so those features are meaningless for them - skip rather than run
# word-count/embedding logic against almost nothing. stem_diagram content is
# real, topic-grounded text, so it keeps full scoring.
_SKIP_SCORING_TYPES = {QuestionType.VISUAL_WORKSHEET}


def _score_and_flag(q: Question, graph_store, bank, check_duplicates: bool) -> GeneratedQuestionResult:
    if q.question_type in _SKIP_SCORING_TYPES:
        difficulty = DifficultyScore(score=0.0, features={}, shap_contributions=None, method="heuristic")
        matches: list[DuplicateMatch] = []
    else:
        difficulty = score_difficulty(q, graph_store)
        q.difficulty_score = difficulty.score
        matches = find_duplicates(q, bank.list_by_subject(q.subject_id)) if check_duplicates else []
    return GeneratedQuestionResult(question=q, difficulty=difficulty, duplicate_matches=matches)


@router.post("/generate", response_model=GenerateQuestionsResponse)
def generate(request: GenerateQuestionsRequest, teacher: Teacher = Depends(get_current_teacher)) -> GenerateQuestionsResponse:
    """RAG-generate questions for a topic, score their difficulty, and flag duplicates
    against the existing question bank. Defaults to a preview (not saved) — pass
    save_to_bank=true, or POST the chosen question(s) to /questions afterward."""
    require_subject(request.subject_id, teacher)
    graph_store = get_graph_store(request.subject_id)
    bank = get_question_bank()

    questions = generate_questions(
        topic=request.topic,
        graph_store=graph_store,
        subject_id=request.subject_id,
        num_questions=request.num_questions,
        bloom_level=request.bloom_level,
        marks=request.marks,
        question_type=request.question_type,
        course_outcomes=request.course_outcomes,
    )

    results = []
    for q in questions:
        result = _score_and_flag(q, graph_store, bank, request.check_duplicates)
        results.append(result)
        if request.save_to_bank:
            bank.add(q)

    return GenerateQuestionsResponse(results=results)


class GenerateSectionRequest(BaseModel):
    subject_id: str
    topic_ids: list[str]
    question_type: QuestionType
    num_questions: int = 3
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    marks: int = 5
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    course_outcomes: list[CourseOutcome] | None = None
    check_duplicates: bool = True
    save_to_bank: bool = True


@router.post("/generate-section", response_model=GenerateQuestionsResponse)
def generate_section(request: GenerateSectionRequest, teacher: Teacher = Depends(get_current_teacher)) -> GenerateQuestionsResponse:
    """Generate questions for one Question Paper Builder section: one format,
    one difficulty, one or more topics. Primary entry point for the Builder."""
    require_subject(request.subject_id, teacher)
    graph_store = get_graph_store(request.subject_id)
    bank = get_question_bank()

    graph = graph_store.graph
    topic_names = [graph.nodes[tid].get("name", tid) for tid in request.topic_ids if tid in graph]

    questions = generate_section_questions(
        topics=topic_names,
        graph_store=graph_store,
        subject_id=request.subject_id,
        num_questions=request.num_questions,
        bloom_level=request.bloom_level,
        marks=request.marks,
        question_type=request.question_type,
        difficulty=request.difficulty,
        course_outcomes=request.course_outcomes,
    )

    results = []
    for q in questions:
        result = _score_and_flag(q, graph_store, bank, request.check_duplicates)
        results.append(result)
        if request.save_to_bank:
            bank.add(q)

    return GenerateQuestionsResponse(results=results)


class CheckDuplicatesRequest(BaseModel):
    question: Question
    threshold: float = 0.75


class CheckDuplicatesResponse(BaseModel):
    matches: list[DuplicateMatch]


@router.post("/check-duplicates", response_model=CheckDuplicatesResponse)
def check_duplicates(request: CheckDuplicatesRequest, teacher: Teacher = Depends(get_current_teacher)) -> CheckDuplicatesResponse:
    require_subject(request.question.subject_id, teacher)
    bank = get_question_bank()
    matches = find_duplicates(request.question, bank.list_by_subject(request.question.subject_id), threshold=request.threshold)
    return CheckDuplicatesResponse(matches=matches)


@router.get("", response_model=list[Question])
def list_questions(subject_id: str, teacher: Teacher = Depends(get_current_teacher)) -> list[Question]:
    require_subject(subject_id, teacher)
    return get_question_bank().list_by_subject(subject_id)


@router.post("", response_model=Question)
def save_question(question: Question, teacher: Teacher = Depends(get_current_teacher)) -> Question:
    """Persist a question the user has reviewed (e.g. a generation preview they approved)."""
    require_subject(question.subject_id, teacher)
    get_question_bank().add(question)
    return question


@router.delete("/{question_id}")
def delete_question(question_id: str, teacher: Teacher = Depends(get_current_teacher)) -> dict:
    bank = get_question_bank()
    question = bank.get(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    require_subject(question.subject_id, teacher)
    bank.remove(question_id)
    return {"deleted": question_id}
