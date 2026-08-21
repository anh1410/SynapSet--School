from app.api.questions import _score_and_flag
from app.schemas.bloom import BloomLevel
from app.schemas.question import Question, QuestionType


def test_visual_worksheet_skips_real_scoring(graph_store, tmp_path):
    from app.core.question_bank import QuestionBank

    q = Question(
        id="1", subject_id="sub1", text="", question_type=QuestionType.VISUAL_WORKSHEET,
        marks=1, bloom_level=BloomLevel.REMEMBER,
    )
    bank = QuestionBank(str(tmp_path / "bank.db"))  # never actually queried for this path
    result = _score_and_flag(q, graph_store, bank, check_duplicates=True)

    assert result.difficulty.score == 0.0
    assert result.difficulty.method == "heuristic"
    assert result.duplicate_matches == []


def test_stem_diagram_gets_real_scoring(graph_store, sample_questions, tmp_path):
    from app.core.question_bank import QuestionBank

    q = Question(
        id="2", subject_id="sub1", text="Solve for x in $x^2 = 4$", question_type=QuestionType.STEM_DIAGRAM,
        marks=5, bloom_level=BloomLevel.APPLY, topic_ids=["virtualization"],
    )
    bank = QuestionBank(str(tmp_path / "bank.db"))
    for existing in sample_questions:
        bank.add(existing)

    result = _score_and_flag(q, graph_store, bank, check_duplicates=True)

    assert result.difficulty.method == "model"  # the real XGBoost path, not the heuristic skip
    assert 1.0 <= result.difficulty.score <= 10.0
