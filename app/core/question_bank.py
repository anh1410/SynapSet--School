from functools import lru_cache

from app.core.config import get_settings
from app.core.db import connect, dump, load
from app.schemas.question import Question


def _row_to_question(row) -> Question:
    d = dict(row)
    d["topic_ids"] = load(d["topic_ids"]) or []
    d["co_ids"] = load(d["co_ids"]) or []
    d["options"] = load(d["options"])
    d["match_pairs"] = load(d["match_pairs"])
    d["match_right_order"] = load(d["match_right_order"])
    d["is_true"] = bool(d["is_true"]) if d["is_true"] is not None else None
    d["diagram"] = load(d.get("diagram"))
    d["grid_layout"] = load(d.get("grid_layout"))
    return Question.model_validate(d)


def _question_params(q: Question) -> tuple:
    return (
        q.id,
        q.subject_id,
        q.text,
        q.question_type.value,
        q.marks,
        int(q.bloom_level),
        dump(q.topic_ids),
        dump(q.co_ids),
        q.unit,
        dump(q.options) if q.options is not None else None,
        q.correct_answer,
        dump([p.model_dump(mode="json") for p in q.match_pairs]) if q.match_pairs is not None else None,
        dump(q.match_right_order) if q.match_right_order is not None else None,
        int(q.is_true) if q.is_true is not None else None,
        dump(q.diagram.model_dump(mode="json")) if q.diagram is not None else None,
        dump(q.grid_layout.model_dump(mode="json")) if q.grid_layout is not None else None,
        q.difficulty_score,
        q.embedding_id,
        q.is_duplicate_of,
        q.source_document,
        q.author_id,
        q.academic_year,
        q.term,
        q.created_at.isoformat(),
    )


class QuestionBank:
    """SQLite-backed store for generated questions, so duplicate detection
    and paper optimization have a persistent pool to work against."""

    def __init__(self, persist_path: str):
        self.persist_path = persist_path

    def add(self, question: Question) -> None:
        with connect(self.persist_path) as conn:
            conn.execute(
                """INSERT INTO questions (
                    id, subject_id, text, question_type, marks, bloom_level, topic_ids, co_ids,
                    unit, options, correct_answer, match_pairs, match_right_order, is_true,
                    diagram, grid_layout,
                    difficulty_score, embedding_id, is_duplicate_of, source_document, author_id,
                    academic_year, term, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    subject_id = excluded.subject_id, text = excluded.text,
                    question_type = excluded.question_type, marks = excluded.marks,
                    bloom_level = excluded.bloom_level, topic_ids = excluded.topic_ids,
                    co_ids = excluded.co_ids, unit = excluded.unit, options = excluded.options,
                    correct_answer = excluded.correct_answer, match_pairs = excluded.match_pairs,
                    match_right_order = excluded.match_right_order, is_true = excluded.is_true,
                    diagram = excluded.diagram, grid_layout = excluded.grid_layout,
                    difficulty_score = excluded.difficulty_score, embedding_id = excluded.embedding_id,
                    is_duplicate_of = excluded.is_duplicate_of, source_document = excluded.source_document,
                    author_id = excluded.author_id, academic_year = excluded.academic_year,
                    term = excluded.term, created_at = excluded.created_at""",
                _question_params(question),
            )

    def add_many(self, questions: list[Question]) -> None:
        for q in questions:
            self.add(q)

    def remove(self, question_id: str) -> bool:
        with connect(self.persist_path) as conn:
            cur = conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        return cur.rowcount > 0

    def list_all(self) -> list[Question]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT * FROM questions").fetchall()
        return [_row_to_question(r) for r in rows]

    def list_by_subject(self, subject_id: str) -> list[Question]:
        with connect(self.persist_path) as conn:
            rows = conn.execute("SELECT * FROM questions WHERE subject_id = ?", (subject_id,)).fetchall()
        return [_row_to_question(r) for r in rows]

    def get(self, question_id: str) -> Question | None:
        with connect(self.persist_path) as conn:
            row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        return _row_to_question(row) if row else None


@lru_cache
def get_question_bank() -> QuestionBank:
    settings = get_settings()
    return QuestionBank(settings.database_path)
