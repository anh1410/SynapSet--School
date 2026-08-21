import random
import uuid
from typing import Literal

import httpx
from google.genai import errors, types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.graph_store import KnowledgeGraphStore, normalize_topic_name
from app.core.image_store import save_image
from app.core.llm import get_genai_client
from app.schemas.bloom import BloomLevel
from app.schemas.course_outcome import CourseOutcome
from app.schemas.generation import QuestionDraftBatch
from app.schemas.question import DiagramKind, Question, QuestionType
from app.services.diagram_execution import (
    DiagramTimeoutError,
    UnsafeDiagramCodeError,
    execute_matplotlib_diagram,
    execute_tikz_diagram,
)
from app.services.image_generation import generate_image
from app.services.vector_indexing import query_similar_chunks

Difficulty = Literal["easy", "medium", "hard"]

DIFFICULTY_INSTRUCTIONS: dict[Difficulty, str] = {
    "easy": "Test direct recall or a definition-level understanding. Single-step reasoning only.",
    "medium": "Require applying a concept to a new but similar scenario. One or two steps of reasoning.",
    "hard": "Require synthesizing multiple concepts, multi-step reasoning, or analyzing an unfamiliar scenario.",
}

QUESTION_TYPE_INSTRUCTIONS: dict[QuestionType, str] = {
    QuestionType.MCQ: "Include exactly 4 options in `options` and `correct_answer` must exactly match one option. Leave `match_pairs` and `is_true` empty.",
    QuestionType.SHORT_ANSWER: "Leave `options` empty. Put a model answer (or key points) in `correct_answer`. Leave `match_pairs` and `is_true` empty.",
    QuestionType.LONG_ANSWER: "Leave `options` empty. Put a model answer (or key points) in `correct_answer`. Leave `match_pairs` and `is_true` empty.",
    QuestionType.NUMERICAL: "Leave `options` empty. Put the numeric answer in `correct_answer`. Leave `match_pairs` and `is_true` empty.",
    QuestionType.FILL_IN_BLANK: 'Write the sentence in `text` with a literal "_____" placeholder marking the blank, and put the blank\'s correct text in `correct_answer`. Leave `options`, `match_pairs`, and `is_true` empty.',
    QuestionType.MATCH_FOLLOWING: "Write an instruction like \"Match the following\" in `text`, and provide 4-6 pairs in `match_pairs` (each with `left` and `right`). Leave `options`, `correct_answer`, and `is_true` empty.",
    QuestionType.TRUE_FALSE: "Write a single statement in `text` and set `is_true` to true or false accordingly. Leave `options`, `correct_answer`, and `match_pairs` empty.",
    QuestionType.STEM_DIAGRAM: (
        "Use strict LaTeX for ALL math/chemistry notation in `text` and `correct_answer`, delimited with "
        "single `$...$` for inline and `$$...$$` for display (e.g. `$E=mc^2$`, `$H_2SO_4$`). If the "
        "question needs a geometry/physics diagram, populate `diagram`: set `kind` to \"matplotlib\" "
        "(preferred) or \"tikz\", and put COMPLETE, SELF-CONTAINED, EXECUTABLE Python code in `source_code` "
        "using only `plt`/`np` (already imported) that draws into the current matplotlib figure — do NOT "
        "call plt.savefig, plt.show, or any file/network APIs. Leave `diagram` null if no visual is needed. "
        "Leave `options`, `match_pairs`, and `is_true` empty."
    ),
    QuestionType.VISUAL_WORKSHEET: (
        "This is for pre-literate LKG/UKG students: keep `text` to a single short instruction line "
        '(e.g. "Circle the sense organs") or empty. Populate `grid_layout`: pick `kind` '
        "(grid_2x4 / two_column_match / single_row) and `response_style` (circle_choice / blank_line / "
        "match_lines) fitting the instruction. For EACH grid item's `visual`, invent a FRESH, SPECIFIC, "
        "PARAMETERIZED image prompt varying style/action/background every time — never reuse a generic "
        'label as the prompt (e.g. for "frog" write "minimalist black line art of a frog sitting on a '
        'lily pad, white background", not just "frog"). Set `is_correct` on grid items that are the right '
        "answer(s) for choice-selection layouts. Leave `options`, `correct_answer`, `match_pairs`, `is_true` empty."
    ),
}

GENERATION_PROMPT = """You are an exam question writer for a school course. Write exam questions \
strictly grounded in the SYLLABUS CONTEXT below — do not introduce facts that aren't supported by it.

TOPIC(S): {topics}

SYLLABUS CONTEXT (retrieved passages):
{context}

RELATED TOPICS (from the course knowledge graph):
{related_topics}

{co_section}
Write {num_questions} {question_type} question(s) at Bloom's level "{bloom_level}" worth {marks} marks \
each, covering: {topics}.

DIFFICULTY TARGET ({difficulty}): {difficulty_instruction}

FORMAT RULES for {question_type}: {type_instruction}

- Ground every question in the syllabus context provided.
- Tag each question with the topic names it covers (topic_names): include the topic(s) above and any \
related topics from the list above that the question actually draws on.
- If Course Outcomes were given, tag applicable co_codes; otherwise leave co_codes empty.
"""


def _context_text(topics: list[str], subject_id: str, n_chunks: int = 5) -> str:
    seen: dict[str, dict] = {}
    for topic in topics:
        for hit in query_similar_chunks(topic, subject_id, n_results=n_chunks):
            key = f"{hit['metadata'].get('source_document')}::{hit['metadata'].get('chunk_index')}"
            seen[key] = hit
    if not seen:
        return "(no indexed syllabus content found for these topics)"
    return "\n\n".join(f"[{h['metadata'].get('source_document')}] {h['text']}" for h in seen.values())


def _related_topics_text(topics: list[str], graph_store: KnowledgeGraphStore) -> str:
    graph = graph_store.graph
    lines: list[str] = []
    for topic in topics:
        node_id = normalize_topic_name(topic)
        if node_id not in graph:
            continue
        for pred in graph.predecessors(node_id):
            rel = graph.edges[pred, node_id].get("relation_type")
            lines.append(f"- {graph.nodes[pred].get('name', pred)} --[{rel}]--> {topic}")
        for succ in graph.successors(node_id):
            rel = graph.edges[node_id, succ].get("relation_type")
            lines.append(f"- {topic} --[{rel}]--> {graph.nodes[succ].get('name', succ)}")

    return "\n".join(lines) if lines else "(no direct relations found)"


def _shuffled_match_order(n: int) -> list[int]:
    """A permutation of range(n) for displaying Column B, distinct from the
    identity order whenever possible so the layout isn't a giveaway."""
    if n <= 1:
        return list(range(n))
    order = list(range(n))
    rng = random.Random()
    for _ in range(10):
        rng.shuffle(order)
        if order != list(range(n)):
            break
    return order


def _resolve_diagram(diagram):
    """Executes a draft's diagram source server-side and returns a new
    DiagramSpec with image_id (success) or render_error (failure) set —
    never both, never raises: a bad diagram must not fail the whole
    generation request."""
    if diagram is None:
        return None
    try:
        if diagram.kind == DiagramKind.MATPLOTLIB:
            png = execute_matplotlib_diagram(diagram.source_code)
        else:
            png = execute_tikz_diagram(diagram.source_code)
            if png is None:
                return diagram.model_copy(update={"render_error": "TikZ rendering unavailable on this server"})
        return diagram.model_copy(update={"image_id": save_image(png)})
    except (UnsafeDiagramCodeError, DiagramTimeoutError) as exc:
        return diagram.model_copy(update={"render_error": str(exc)})


def _resolve_grid_layout(grid_layout):
    """Renders (currently: placeholder-renders) each grid item's image
    prompt and fills in image_id. A single failed item just gets left with
    image_id=None rather than aborting the whole worksheet."""
    if grid_layout is None:
        return None
    resolved_items = []
    for item in grid_layout.items:
        try:
            png = generate_image(item.visual.full_prompt)
            visual = item.visual.model_copy(update={"image_id": save_image(png)})
        except Exception:  # noqa: BLE001 - one bad prompt shouldn't sink the worksheet
            visual = item.visual
        resolved_items.append(item.model_copy(update={"visual": visual}))
    return grid_layout.model_copy(update={"items": resolved_items})


def _co_section(course_outcomes: list[CourseOutcome] | None) -> str:
    if not course_outcomes:
        return ""
    listed = "\n".join(f"- {co.code}: {co.description}" for co in course_outcomes)
    return f"COURSE OUTCOMES (tag co_codes from this list only):\n{listed}\n"


@retry(
    retry=retry_if_exception_type((errors.ServerError, errors.APIError, httpx.TransportError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def generate_section_questions(
    topics: list[str],
    graph_store: KnowledgeGraphStore,
    subject_id: str,
    num_questions: int = 3,
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND,
    marks: int = 5,
    question_type: QuestionType = QuestionType.SHORT_ANSWER,
    difficulty: Difficulty = "medium",
    course_outcomes: list[CourseOutcome] | None = None,
) -> list[Question]:
    """Generate exam questions covering one or more topics, grounded in retrieved
    syllabus context and augmented with the knowledge graph's prerequisite/CO
    relationships. Used by the section-based Question Paper Builder."""
    settings = get_settings()
    client = get_genai_client()

    topics_text = ", ".join(topics)
    prompt = GENERATION_PROMPT.format(
        topics=topics_text,
        context=_context_text(topics, subject_id),
        related_topics=_related_topics_text(topics, graph_store),
        co_section=_co_section(course_outcomes),
        num_questions=num_questions,
        question_type=question_type.value,
        bloom_level=bloom_level.name,
        marks=marks,
        difficulty=difficulty,
        difficulty_instruction=DIFFICULTY_INSTRUCTIONS[difficulty],
        type_instruction=QUESTION_TYPE_INSTRUCTIONS[question_type],
    )

    response = client.models.generate_content(
        model=settings.generation_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QuestionDraftBatch,
        ),
    )

    if response.parsed is None:
        return []

    graph = graph_store.graph
    questions: list[Question] = []
    for draft in response.parsed.questions:
        topic_ids = [
            normalize_topic_name(name)
            for name in draft.topic_names
            if normalize_topic_name(name) in graph
        ]
        match_right_order = (
            _shuffled_match_order(len(draft.match_pairs))
            if draft.question_type == QuestionType.MATCH_FOLLOWING and draft.match_pairs
            else None
        )
        # LKG/UKG content has no real cognitive level to ask Gemini for -
        # it's definitionally recall, so it's hardcoded rather than trusted
        # to the model's own (meaningless, for this type) Bloom choice.
        resolved_bloom_level = (
            BloomLevel.REMEMBER if draft.question_type == QuestionType.VISUAL_WORKSHEET else BloomLevel[draft.bloom_level]
        )
        questions.append(
            Question(
                id=str(uuid.uuid4()),
                subject_id=subject_id,
                text=draft.text,
                question_type=draft.question_type,
                marks=draft.marks,
                bloom_level=resolved_bloom_level,
                topic_ids=topic_ids,
                co_ids=draft.co_codes,
                options=draft.options,
                correct_answer=draft.correct_answer,
                match_pairs=draft.match_pairs,
                match_right_order=match_right_order,
                is_true=draft.is_true,
                diagram=_resolve_diagram(draft.diagram),
                grid_layout=_resolve_grid_layout(draft.grid_layout),
            )
        )

    return questions


def generate_questions(
    topic: str,
    graph_store: KnowledgeGraphStore,
    subject_id: str,
    num_questions: int = 3,
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND,
    marks: int = 5,
    question_type: QuestionType = QuestionType.SHORT_ANSWER,
    difficulty: Difficulty = "medium",
    course_outcomes: list[CourseOutcome] | None = None,
) -> list[Question]:
    """Single-topic convenience wrapper around generate_section_questions."""
    return generate_section_questions(
        topics=[topic],
        graph_store=graph_store,
        subject_id=subject_id,
        num_questions=num_questions,
        bloom_level=bloom_level,
        marks=marks,
        question_type=question_type,
        difficulty=difficulty,
        course_outcomes=course_outcomes,
    )
