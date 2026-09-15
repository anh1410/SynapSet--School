from app.core.question_bank import QuestionBank
from app.schemas.bloom import BloomLevel
from app.schemas.question import (
    GridItem,
    GridLayout,
    GridLayoutKind,
    Question,
    QuestionType,
    ResponseStyle,
    VisualPrompt,
)
from app.services.question_generation import _used_visuals_section, used_visual_subjects


def _worksheet(id_: str, subject_id: str, subjects: list[str]) -> Question:
    return Question(
        id=id_,
        subject_id=subject_id,
        text="Circle the correct picture",
        question_type=QuestionType.VISUAL_WORKSHEET,
        marks=1,
        bloom_level=BloomLevel.REMEMBER,
        grid_layout=GridLayout(
            kind=GridLayoutKind.SINGLE_ROW,
            response_style=ResponseStyle.CIRCLE_CHOICE,
            items=[
                GridItem(visual=VisualPrompt(subject=s, style="line art", full_prompt=f"a {s}"), is_correct=True)
                for s in subjects
            ],
        ),
    )


def test_used_visual_subjects_collects_and_dedupes(tmp_path):
    bank = QuestionBank(str(tmp_path / "bank.db"))
    bank.add(_worksheet("1", "evs", ["Frog", "Cat"]))
    bank.add(_worksheet("2", "evs", ["frog", "Sun"]))  # "frog" repeats case-insensitively

    used = used_visual_subjects("evs", bank)

    assert {s.lower() for s in used} == {"frog", "cat", "sun"}
    assert len(used) == 3  # the second "frog" didn't get double-counted


def test_used_visual_subjects_ignores_other_subjects_and_types(tmp_path):
    bank = QuestionBank(str(tmp_path / "bank.db"))
    bank.add(_worksheet("1", "evs", ["Frog"]))
    bank.add(_worksheet("2", "other_subject", ["Cat"]))
    other_type = Question(
        id="3", subject_id="evs", text="Define photosynthesis",
        question_type=QuestionType.SHORT_ANSWER, marks=3, bloom_level=BloomLevel.UNDERSTAND,
    )
    bank.add(other_type)

    assert used_visual_subjects("evs", bank) == ["Frog"]


def test_used_visual_subjects_respects_limit(tmp_path):
    bank = QuestionBank(str(tmp_path / "bank.db"))
    for i in range(5):
        bank.add(_worksheet(str(i), "evs", [f"animal{i}"]))

    assert len(used_visual_subjects("evs", bank, limit=3)) == 3


def test_used_visuals_section_empty_for_non_visual_types(tmp_path):
    bank = QuestionBank(str(tmp_path / "bank.db"))
    bank.add(_worksheet("1", "evs", ["Frog"]))

    assert _used_visuals_section(QuestionType.SHORT_ANSWER, "evs", bank) == ""
    assert _used_visuals_section(QuestionType.VISUAL_WORKSHEET, "evs", None) == ""


def test_used_visuals_section_lists_subjects_when_present(tmp_path):
    bank = QuestionBank(str(tmp_path / "bank.db"))
    bank.add(_worksheet("1", "evs", ["Frog", "Cat"]))

    section = _used_visuals_section(QuestionType.VISUAL_WORKSHEET, "evs", bank)

    assert "Frog" in section
    assert "Cat" in section
    assert "do NOT reuse" in section


def test_used_visuals_section_empty_when_no_history(tmp_path):
    bank = QuestionBank(str(tmp_path / "bank.db"))
    assert _used_visuals_section(QuestionType.VISUAL_WORKSHEET, "evs", bank) == ""
