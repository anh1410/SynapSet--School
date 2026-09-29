"""Devanagari/Kannada text in exported PDFs must go through the
HarfBuzz-shaped raster path (reportlab.Paragraph can't shape those scripts
correctly - see indic_text.py). These tests check the routing decision and
that full paper export doesn't crash on multilingual content; the actual
shaping correctness is covered by tests/test_indic_text.py and was verified
visually against a real generated PDF during development."""

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph

from app.schemas.bloom import BloomLevel
from app.schemas.paper_blueprint import BlueprintSection, PaperBlueprint
from app.schemas.question import MatchPair, Question, QuestionType
from app.services.paper_export import _rich_text_flowable, export_paper_docx, export_paper_pdf


def test_rich_text_flowable_uses_paragraph_for_latin():
    styles = getSampleStyleSheet()
    assert isinstance(_rich_text_flowable("What is the capital of India?", styles), Paragraph)


def test_rich_text_flowable_uses_image_for_devanagari():
    styles = getSampleStyleSheet()
    assert isinstance(_rich_text_flowable("प्रकाश संश्लेषण किसे कहते हैं?", styles), RLImage)


def test_rich_text_flowable_uses_image_for_kannada():
    styles = getSampleStyleSheet()
    assert isinstance(_rich_text_flowable("ಕರ್ನಾಟಕ ರಾಜ್ಯದ ರಾಜಧಾನಿ ಯಾವುದು?", styles), RLImage)


def _multilingual_blueprint_and_sections():
    hindi_q = Question(
        id="1", subject_id="s", text="प्रकाश संश्लेषण किसे कहते हैं?",
        question_type=QuestionType.SHORT_ANSWER, marks=3, bloom_level=BloomLevel.UNDERSTAND,
        correct_answer="पौधे सूर्य के प्रकाश से भोजन बनाते हैं।",
    )
    kannada_mcq = Question(
        id="2", subject_id="s", text="ಕರ್ನಾಟಕ ರಾಜ್ಯದ ರಾಜಧಾನಿ ಯಾವುದು?",
        question_type=QuestionType.MCQ, marks=1, bloom_level=BloomLevel.REMEMBER,
        options=["ಮೈಸೂರು", "ಬೆಂಗಳೂರು", "ಹುಬ್ಬಳ್ಳಿ", "ಮಂಗಳೂರು"], correct_answer="ಬೆಂಗಳೂರು",
    )
    match_q = Question(
        id="3", subject_id="s", text="निम्नलिखित का मिलान कीजिए।",
        question_type=QuestionType.MATCH_FOLLOWING, marks=4, bloom_level=BloomLevel.UNDERSTAND,
        match_pairs=[MatchPair(left="सूर्य", right="तारा"), MatchPair(left="चाँद", right="उपग्रह")],
        match_right_order=[1, 0],
    )
    english_q = Question(
        id="4", subject_id="s", text="What is the capital of India?",
        question_type=QuestionType.SHORT_ANSWER, marks=2, bloom_level=BloomLevel.REMEMBER,
        correct_answer="New Delhi",
    )
    blueprint = PaperBlueprint(
        id="bp1", teacher_id="t1", subject_id="s", name="हिंदी एवं कन्नड़ परीक्षा", total_marks=10,
        sections=[
            BlueprintSection(id="sec1", title="Hindi Section - हिंदी खंड", question_format=QuestionType.SHORT_ANSWER, question_ids=["1", "3"]),
            BlueprintSection(id="sec2", title="Kannada Section - ಕನ್ನಡ ವಿಭಾಗ", question_format=QuestionType.MCQ, question_ids=["2"]),
            BlueprintSection(id="sec3", title="English Section", question_format=QuestionType.SHORT_ANSWER, question_ids=["4"]),
        ],
    )
    sections = [
        (blueprint.sections[0], [hindi_q, match_q]),
        (blueprint.sections[1], [kannada_mcq]),
        (blueprint.sections[2], [english_q]),
    ]
    return blueprint, sections


def test_export_multilingual_pdf_student_and_answer_key(tmp_path):
    blueprint, sections = _multilingual_blueprint_and_sections()
    for include_answers in (False, True):
        suffix = "_key" if include_answers else ""
        path = str(tmp_path / f"paper{suffix}.pdf")
        export_paper_pdf(blueprint, sections, "Priya Sharma", "Hindi & Kannada", include_answers, path)
        with open(path, "rb") as f:
            content = f.read()
        assert content[:4] == b"%PDF"
        assert len(content) > 1000


def test_export_multilingual_docx(tmp_path):
    blueprint, sections = _multilingual_blueprint_and_sections()
    path = str(tmp_path / "paper.docx")
    export_paper_docx(blueprint, sections, "Priya Sharma", "Hindi & Kannada", include_answers=True, output_path=path)
    with open(path, "rb") as f:
        content = f.read()
    assert content[:2] == b"PK"  # docx is a zip container
