from app.schemas.bloom import BloomLevel
from app.schemas.question import MatchPair, Question, QuestionType
from app.services.paper_export import _blank_lines_for, _render_answer


def _q(qtype, **kwargs) -> Question:
    return Question(
        id="q1", subject_id="sub1", text="text", question_type=qtype, marks=kwargs.pop("marks", 2),
        bloom_level=BloomLevel.UNDERSTAND, **kwargs,
    )


def test_render_answer_mcq():
    q = _q(QuestionType.MCQ, options=["a", "b", "c", "d"], correct_answer="b")
    assert _render_answer(q) == "b"


def test_render_answer_true_false():
    assert _render_answer(_q(QuestionType.TRUE_FALSE, is_true=True)) == "True"
    assert _render_answer(_q(QuestionType.TRUE_FALSE, is_true=False)) == "False"


def test_render_answer_match_following():
    # No match_right_order set -> falls back to identity order (Column B in original order).
    q = _q(QuestionType.MATCH_FOLLOWING, match_pairs=[MatchPair(left="A", right="1"), MatchPair(left="B", right="2")])
    assert _render_answer(q) == "(i) → A, (ii) → B"


def test_render_answer_match_following_uses_shuffled_order():
    q = _q(
        QuestionType.MATCH_FOLLOWING,
        match_pairs=[MatchPair(left="A", right="1"), MatchPair(left="B", right="2")],
        match_right_order=[1, 0],  # Column B shows right[1] then right[0]
    )
    # left index 0 ("A") now correctly matches whichever Column B slot holds right[0], i.e. slot 1 -> letter B
    assert _render_answer(q) == "(i) → B, (ii) → A"


def test_render_answer_fill_in_blank():
    assert _render_answer(_q(QuestionType.FILL_IN_BLANK, correct_answer="chloroplasts")) == "chloroplasts"


def test_render_answer_missing_falls_back():
    assert _render_answer(_q(QuestionType.SHORT_ANSWER, correct_answer=None)) == "(no answer recorded)"


def test_blank_lines_scale_with_marks():
    assert _blank_lines_for(1) == 1
    assert _blank_lines_for(10) == 6  # capped


def test_export_pdf_variant_differs(api_client):
    from app.core.question_bank import get_question_bank

    bank = get_question_bank()
    bank.add(
        Question(
            id="tf1", subject_id=api_client.subject_id, text="The sky is blue.",
            question_type=QuestionType.TRUE_FALSE, marks=1, bloom_level=BloomLevel.REMEMBER, is_true=True,
        )
    )

    create = api_client.post(
        "/api/v1/paper/blueprints",
        json={
            "subject_id": api_client.subject_id,
            "name": "TF Export Test",
            "total_marks": 1,
            "sections": [{"title": "Section A", "question_format": "true_false", "question_ids": ["tf1"]}],
        },
    )
    blueprint_id = create.json()["id"]

    student = api_client.get(f"/api/v1/paper/blueprints/{blueprint_id}/export", params={"format": "pdf", "variant": "student"})
    answer_key = api_client.get(f"/api/v1/paper/blueprints/{blueprint_id}/export", params={"format": "pdf", "variant": "answer_key"})

    assert student.status_code == 200
    assert answer_key.status_code == 200
    assert "answer_key" in answer_key.headers["content-disposition"]
    assert "answer_key" not in student.headers["content-disposition"]
    # The answer key file must be a strict superset of content (the "Answer:" line), so its byte size differs.
    assert len(answer_key.content) != len(student.content)
