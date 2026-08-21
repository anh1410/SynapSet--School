import io

from app.core.image_store import save_image
from app.schemas.bloom import BloomLevel
from app.schemas.question import (
    DiagramKind,
    DiagramSpec,
    GridItem,
    GridLayout,
    GridLayoutKind,
    Question,
    QuestionType,
    ResponseStyle,
    VisualPrompt,
)
from app.services.paper_export import _rasterize_mathtext, _split_latex_segments


def _real_png_bytes() -> bytes:
    """A genuinely decodable small PNG - PIL needs to actually read
    dimensions from it, so a fake magic-number-only blob won't do."""
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (20, 20), color="blue").save(buf, format="PNG")
    return buf.getvalue()


def test_split_latex_segments_plain_text():
    assert _split_latex_segments("no math here") == [("no math here", False)]


def test_split_latex_segments_single_inline_math():
    segments = _split_latex_segments("Solve $x^2=4$ for x")
    assert segments == [("Solve ", False), ("x^2=4", True), (" for x", False)]


def test_split_latex_segments_display_math():
    segments = _split_latex_segments("$$E=mc^2$$")
    assert segments == [("E=mc^2", True)]


def test_split_latex_segments_multiple_math_chunks():
    segments = _split_latex_segments("$a$ and $b$")
    assert segments == [("a", True), (" and ", False), ("b", True)]


def test_rasterize_mathtext_returns_valid_png():
    png = _rasterize_mathtext("H_2SO_4")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 50


def _q(qtype, **kwargs) -> Question:
    return Question(
        id=kwargs.pop("id", "q1"), subject_id="sub1", text=kwargs.pop("text", "text"),
        question_type=qtype, marks=kwargs.pop("marks", 2),
        bloom_level=kwargs.pop("bloom_level", BloomLevel.UNDERSTAND), **kwargs,
    )


def test_export_stem_diagram_pdf_and_docx(api_client, tmp_path):
    from app.core.question_bank import get_question_bank

    image_id = save_image(_real_png_bytes())
    q = _q(
        QuestionType.STEM_DIAGRAM,
        id="stem1",
        text="Solve for x: $x^2 - 4 = 0$",
        marks=5,
        correct_answer="$x = \\pm 2$",
        diagram=DiagramSpec(kind=DiagramKind.MATPLOTLIB, source_code="plt.plot([0,1],[0,1])", image_id=image_id, caption="A line"),
    )
    get_question_bank().add(q)

    create = api_client.post(
        "/api/v1/paper/blueprints",
        json={
            "subject_id": api_client.subject_id,
            "name": "STEM Export Test",
            "total_marks": 5,
            "sections": [{"title": "Section A", "question_format": "stem_diagram", "question_ids": ["stem1"]}],
        },
    )
    blueprint_id = create.json()["id"]

    for fmt, magic in [("pdf", b"%PDF"), ("docx", b"PK")]:
        for variant in ["student", "answer_key"]:
            r = api_client.get(
                f"/api/v1/paper/blueprints/{blueprint_id}/export", params={"format": fmt, "variant": variant}
            )
            assert r.status_code == 200, r.text
            assert r.content[: len(magic)] == magic


def test_export_visual_worksheet_pdf_and_docx(api_client):
    from app.core.question_bank import get_question_bank

    image_id = save_image(_real_png_bytes())
    layout = GridLayout(
        kind=GridLayoutKind.GRID_2X4,
        response_style=ResponseStyle.CIRCLE_CHOICE,
        instruction="Circle the sense organs",
        items=[
            GridItem(visual=VisualPrompt(subject="eye", style="cartoon", full_prompt="cartoon eye", image_id=image_id), is_correct=True),
            GridItem(visual=VisualPrompt(subject="car", style="cartoon", full_prompt="cartoon car", image_id=image_id), is_correct=False),
        ],
    )
    q = _q(QuestionType.VISUAL_WORKSHEET, id="grid1", text="Circle the sense organs", marks=1, grid_layout=layout, bloom_level=BloomLevel.REMEMBER)
    get_question_bank().add(q)

    create = api_client.post(
        "/api/v1/paper/blueprints",
        json={
            "subject_id": api_client.subject_id,
            "name": "Grid Export Test",
            "total_marks": 1,
            "sections": [{"title": "Section A", "question_format": "visual_worksheet", "question_ids": ["grid1"]}],
        },
    )
    blueprint_id = create.json()["id"]

    for fmt, magic in [("pdf", b"%PDF"), ("docx", b"PK")]:
        for variant in ["student", "answer_key"]:
            r = api_client.get(
                f"/api/v1/paper/blueprints/{blueprint_id}/export", params={"format": fmt, "variant": variant}
            )
            assert r.status_code == 200, r.text
            assert r.content[: len(magic)] == magic
