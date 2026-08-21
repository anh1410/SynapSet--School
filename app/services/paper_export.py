import io
import re

from docx import Document
from docx.shared import Inches
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.image_store import image_path
from app.schemas.paper_blueprint import BlueprintSection, PaperBlueprint
from app.schemas.question import GridLayoutKind, Question, QuestionType, ResponseStyle

SectionWithQuestions = tuple[BlueprintSection, list[Question]]

# Types that need blank writing space on the student copy (no options/pairs to
# fill in). match_following/true_false/mcq already show something to mark up.
_FREE_RESPONSE_TYPES = {
    QuestionType.SHORT_ANSWER,
    QuestionType.LONG_ANSWER,
    QuestionType.NUMERICAL,
    QuestionType.FILL_IN_BLANK,
}

_ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]

# Matches $$...$$ or $...$, non-greedy, across the whole text.
_LATEX_SEGMENT_RE = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$", re.DOTALL)


def _roman(index: int) -> str:
    return f"({_ROMAN[index] if index < len(_ROMAN) else index + 1})"


def _letter(index: int) -> str:
    return chr(ord("A") + index)


def _match_columns(q: Question) -> tuple[list[str], list[str], dict[int, str]]:
    """Column A (left items, in original order) and Column B (right items,
    shuffled per match_right_order so it isn't a 1:1 giveaway), plus a
    left-index -> correct-letter map for the answer key."""
    pairs = q.match_pairs or []
    n = len(pairs)
    order = q.match_right_order if q.match_right_order and len(q.match_right_order) == n else list(range(n))

    column_a = [f"{_roman(i)} {p.left}" for i, p in enumerate(pairs)]
    column_b = [f"{_letter(pos)}) {pairs[orig_idx].right}" for pos, orig_idx in enumerate(order)]
    correct_letter = {orig_idx: _letter(pos) for pos, orig_idx in enumerate(order)}
    return column_a, column_b, correct_letter


def _render_answer(q: Question) -> str:
    if q.question_type == QuestionType.TRUE_FALSE:
        return "True" if q.is_true else "False"
    if q.question_type == QuestionType.MATCH_FOLLOWING and q.match_pairs:
        _, _, correct_letter = _match_columns(q)
        return ", ".join(f"{_roman(i)} → {correct_letter[i]}" for i in range(len(q.match_pairs)))
    # mcq / short_answer / long_answer / numerical / fill_in_blank / stem_diagram
    return q.correct_answer or "(no answer recorded)"


def _blank_lines_for(marks: int) -> int:
    """Simple heuristic: more marks, more writing space. Not configurable yet."""
    return min(6, max(1, marks // 2 + 1))


def _split_latex_segments(text: str) -> list[tuple[str, bool]]:
    """Splits `text` into (chunk, is_math) pieces along $...$/$$...$$
    boundaries. Plain text chunks are returned as-is; math chunks are the
    inner LaTeX source (delimiters stripped), ready for _rasterize_mathtext."""
    segments: list[tuple[str, bool]] = []
    pos = 0
    for m in _LATEX_SEGMENT_RE.finditer(text):
        if m.start() > pos:
            segments.append((text[pos : m.start()], False))
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        segments.append((inner, True))
        pos = m.end()
    if pos < len(text):
        segments.append((text[pos:], False))
    return segments or [(text, False)]


def _rasterize_mathtext(inner_latex: str, fontsize: int = 14) -> bytes:
    """PNG bytes for one LaTeX segment via Matplotlib's built-in mathtext
    renderer — no LaTeX toolchain needed. Covers common notation (exponents,
    subscripts, fractions, Greek letters — handles `H_2SO_4`, `E=mc^2`) but
    not arbitrary LaTeX packages/environments; accepted as a v1 limitation."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(0.1, 0.1))
    fig.text(0, 0, f"${inner_latex}$", fontsize=fontsize)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)
    return buf.getvalue()


def _has_latex(text: str) -> bool:
    return bool(_LATEX_SEGMENT_RE.search(text))


def _grid_cols(kind: GridLayoutKind, item_count: int) -> int:
    if kind == GridLayoutKind.GRID_2X4:
        return 4
    if kind == GridLayoutKind.TWO_COLUMN_MATCH:
        return 2
    return max(item_count, 1)  # single_row


def _response_glyph(response_style: ResponseStyle) -> str:
    if response_style == ResponseStyle.CIRCLE_CHOICE:
        return "◯"
    if response_style == ResponseStyle.BLANK_LINE:
        return "_______"
    return ""  # match_lines: no per-cell glyph, the grid layout itself implies pairing


class _CircleMarker(Flowable):
    """Draws a real vector circle instead of a text glyph: reportlab's base-14
    PDF fonts (WinAnsiEncoding) don't cover U+25EF (large circle) or U+2713
    (check mark), so embedding them as Paragraph text renders as a missing-glyph
    box in the exported PDF. python-docx's Word fonts don't have this problem,
    so _response_glyph's Unicode glyphs are kept for the DOCX path."""

    def __init__(self, diameter: float = 12, filled: bool = False):
        super().__init__()
        self.diameter = diameter
        self.filled = filled
        self.width = self.height = diameter + 4

    def draw(self) -> None:
        r = self.diameter / 2
        self.canv.circle(self.width / 2, self.height / 2, r, stroke=1, fill=1 if self.filled else 0)


def export_paper_pdf(
    blueprint: PaperBlueprint,
    sections: list[SectionWithQuestions],
    teacher_name: str,
    subject_name: str,
    include_answers: bool,
    output_path: str,
) -> str:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = [
        Paragraph(subject_name, styles["Normal"]),
        Paragraph(blueprint.name, styles["Title"]),
        Paragraph(f"Teacher: {teacher_name}", styles["Normal"]),
    ]
    if blueprint.duration_minutes is not None:
        story.append(Paragraph(f"Duration: {blueprint.duration_minutes} minutes", styles["Normal"]))
    story.append(Paragraph(f"Total Marks: {blueprint.total_marks}", styles["Normal"]))
    story.append(Paragraph("Answer Key" if include_answers else "Instructions: Answer all questions.", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    q_num = 0
    for section, questions in sections:
        if not questions:
            continue
        story.append(Paragraph(section.title, styles["Heading2"]))
        for q in questions:
            q_num += 1
            story.extend(_pdf_question_flowables(q, q_num, styles, include_answers))
            story.append(Spacer(1, 0.15 * inch))
        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    return output_path


def _pdf_text_flowable(text: str, prefix: str, styles) -> list:
    """One question's text/prefix, with any $...$ math segments rasterized
    and interleaved via a borderless single-row Table — reportlab has no
    native way to mix an inline Image into a Paragraph's text flow."""
    full_text = f"{prefix}{text}"
    if not _has_latex(full_text):
        return [Paragraph(full_text, styles["Normal"])]

    cells = []
    for chunk, is_math in _split_latex_segments(full_text):
        if is_math:
            png = _rasterize_mathtext(chunk)
            w, h = PILImage.open(io.BytesIO(png)).size
            scale = 14 / max(h, 1)  # normalize to ~body-text height
            cells.append(RLImage(io.BytesIO(png), width=w * scale, height=h * scale))
        elif chunk:
            cells.append(Paragraph(chunk, styles["Normal"]))
    if not cells:
        return [Paragraph(full_text, styles["Normal"])]
    table = Table([cells])
    table.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return [table]


def _pdf_question_flowables(q: Question, q_num: int, styles, include_answers: bool) -> list:
    flowables = _pdf_text_flowable(q.text, f"{q_num}. ", styles)
    flowables.append(Paragraph(f"[{q.marks} marks]", styles["Normal"]))

    if q.question_type == QuestionType.MCQ and q.options:
        for j, option in enumerate(q.options):
            letter = chr(ord("a") + j)
            flowables.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;({letter}) {option}", styles["Normal"]))

    if q.question_type == QuestionType.MATCH_FOLLOWING and q.match_pairs:
        column_a, column_b, _ = _match_columns(q)
        rows = [["Column A", "Column B"]]
        for i in range(max(len(column_a), len(column_b))):
            rows.append([column_a[i] if i < len(column_a) else "", column_b[i] if i < len(column_b) else ""])
        table = Table(rows, colWidths=[2.6 * inch, 2.6 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), "#fff3b0"),
                    ("BOX", (0, 0), (-1, -1), 0.5, "#999999"),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, "#cccccc"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        flowables.append(table)
        flowables.append(Spacer(1, 0.1 * inch))

    if q.question_type == QuestionType.STEM_DIAGRAM and q.diagram is not None:
        flowables.extend(_pdf_diagram_flowables(q, styles))

    if q.question_type == QuestionType.VISUAL_WORKSHEET and q.grid_layout is not None:
        flowables.append(_pdf_grid_table(q, styles, include_answers))

    if include_answers:
        flowables.extend(_pdf_answer_flowable(q, styles))
    elif q.question_type in _FREE_RESPONSE_TYPES:
        flowables.append(Spacer(1, _blank_lines_for(q.marks) * 0.25 * inch))

    return flowables


def _pdf_diagram_flowables(q: Question, styles) -> list:
    diagram = q.diagram
    if diagram.image_id is not None:
        path = image_path(diagram.image_id)
        if path is not None:
            w, h = PILImage.open(path).size
            max_w = 4.0 * inch
            scale = min(1.0, max_w / w)
            flowables = [RLImage(str(path), width=w * scale, height=h * scale)]
            if diagram.caption:
                flowables.append(Paragraph(diagram.caption, styles["Italic"]))
            return flowables
    # render_error, or a missing file - fall back to showing the source
    note = f" ({diagram.render_error})" if diagram.render_error else ""
    return [
        Paragraph(f"<i>Diagram rendering unavailable{note}:</i>", styles["Normal"]),
        Paragraph(diagram.source_code.replace("\n", "<br/>"), styles["Code"]),
    ]


def _pdf_grid_table(q: Question, styles, include_answers: bool) -> Table:
    layout = q.grid_layout
    cols = _grid_cols(layout.kind, len(layout.items))

    cells = []
    for item in layout.items:
        cell_parts = []
        path = image_path(item.visual.image_id) if item.visual.image_id else None
        if path is not None:
            w, h = PILImage.open(path).size
            side = 1.2 * inch
            scale = side / max(w, h)
            cell_parts.append(RLImage(str(path), width=w * scale, height=h * scale))
        if item.label:
            cell_parts.append(Paragraph(item.label, styles["Normal"]))
        marked_correct = include_answers and bool(item.is_correct)
        if layout.response_style == ResponseStyle.CIRCLE_CHOICE:
            cell_parts.append(_CircleMarker(filled=marked_correct))
        elif layout.response_style == ResponseStyle.BLANK_LINE:
            cell_parts.append(Paragraph("_______", styles["Normal"]))
            if marked_correct:
                cell_parts.append(Paragraph("Correct answer", styles["Normal"]))
        elif marked_correct:
            cell_parts.append(Paragraph("Correct answer", styles["Normal"]))
        cells.append(cell_parts)

    while len(cells) % cols != 0:
        cells.append([])
    rows = [cells[i : i + cols] for i in range(0, len(cells), cols)]

    table = Table(rows, colWidths=[1.5 * inch] * cols)
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, "#999999"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, "#cccccc"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _pdf_answer_flowable(q: Question, styles) -> list:
    if q.question_type == QuestionType.VISUAL_WORKSHEET:
        return []  # answers are already marked inline in the grid table above
    prefix = "<b>Answer:</b> "
    if not _has_latex(q.correct_answer or ""):
        return [Paragraph(f"{prefix}{_render_answer(q)}", styles["Normal"])]
    return [Paragraph(prefix, styles["Normal"]), *_pdf_text_flowable(q.correct_answer or "", "", styles)]


def export_paper_docx(
    blueprint: PaperBlueprint,
    sections: list[SectionWithQuestions],
    teacher_name: str,
    subject_name: str,
    include_answers: bool,
    output_path: str,
) -> str:
    doc = Document()
    doc.add_paragraph(subject_name)
    doc.add_heading(blueprint.name, level=1)
    doc.add_paragraph(f"Teacher: {teacher_name}")
    if blueprint.duration_minutes is not None:
        doc.add_paragraph(f"Duration: {blueprint.duration_minutes} minutes")
    doc.add_paragraph(f"Total Marks: {blueprint.total_marks}")
    doc.add_paragraph("Answer Key" if include_answers else "Instructions: Answer all questions.")

    q_num = 0
    for section, questions in sections:
        if not questions:
            continue
        doc.add_heading(section.title, level=2)
        for q in questions:
            q_num += 1
            _docx_question(doc, q, q_num, include_answers)

    doc.save(output_path)
    return output_path


def _docx_text_with_math(doc: Document, text: str, prefix: str) -> None:
    """python-docx has no inline-image-in-run support either, so a math
    segment becomes its own image-only paragraph rather than true inline
    splicing — an accepted v1 asymmetry vs. the PDF's tighter interleaving."""
    full_text = f"{prefix}{text}"
    if not _has_latex(full_text):
        doc.add_paragraph(full_text)
        return
    for chunk, is_math in _split_latex_segments(full_text):
        if is_math:
            png = _rasterize_mathtext(chunk)
            doc.add_picture(io.BytesIO(png), height=Inches(0.2))
        elif chunk.strip():
            doc.add_paragraph(chunk)


def _docx_question(doc: Document, q: Question, q_num: int, include_answers: bool) -> None:
    _docx_text_with_math(doc, q.text, f"{q_num}. ")
    doc.add_paragraph(f"[{q.marks} marks]")

    if q.question_type == QuestionType.MCQ and q.options:
        for j, option in enumerate(q.options):
            letter = chr(ord("a") + j)
            doc.add_paragraph(f"     ({letter}) {option}")

    if q.question_type == QuestionType.MATCH_FOLLOWING and q.match_pairs:
        column_a, column_b, _ = _match_columns(q)
        table = doc.add_table(rows=max(len(column_a), len(column_b)) + 1, cols=2)
        table.style = "Table Grid"
        table.rows[0].cells[0].text = "Column A"
        table.rows[0].cells[1].text = "Column B"
        for i in range(max(len(column_a), len(column_b))):
            table.rows[i + 1].cells[0].text = column_a[i] if i < len(column_a) else ""
            table.rows[i + 1].cells[1].text = column_b[i] if i < len(column_b) else ""

    if q.question_type == QuestionType.STEM_DIAGRAM and q.diagram is not None:
        _docx_diagram(doc, q.diagram)

    if q.question_type == QuestionType.VISUAL_WORKSHEET and q.grid_layout is not None:
        _docx_grid_table(doc, q, include_answers)

    if include_answers:
        if q.question_type == QuestionType.VISUAL_WORKSHEET:
            pass  # answers already marked inline in the grid table above
        elif q.correct_answer and _has_latex(q.correct_answer):
            _docx_text_with_math(doc, q.correct_answer, "Answer: ")
        else:
            doc.add_paragraph(f"Answer: {_render_answer(q)}")
    elif q.question_type in _FREE_RESPONSE_TYPES:
        for _ in range(_blank_lines_for(q.marks)):
            doc.add_paragraph("")


def _docx_diagram(doc: Document, diagram) -> None:
    if diagram.image_id is not None:
        path = image_path(diagram.image_id)
        if path is not None:
            doc.add_picture(str(path), width=Inches(4))
            if diagram.caption:
                doc.add_paragraph(diagram.caption)
            return
    note = f" ({diagram.render_error})" if diagram.render_error else ""
    doc.add_paragraph(f"Diagram rendering unavailable{note}:")
    doc.add_paragraph(diagram.source_code)


def _docx_grid_table(doc: Document, q: Question, include_answers: bool) -> None:
    layout = q.grid_layout
    cols = _grid_cols(layout.kind, len(layout.items))
    glyph = _response_glyph(layout.response_style)
    rows = (len(layout.items) + cols - 1) // cols

    table = doc.add_table(rows=rows, cols=cols)
    table.style = "Table Grid"
    for i, item in enumerate(layout.items):
        cell = table.rows[i // cols].cells[i % cols]
        path = image_path(item.visual.image_id) if item.visual.image_id else None
        paragraph = cell.paragraphs[0]
        if path is not None:
            run = paragraph.add_run()
            run.add_picture(str(path), width=Inches(1.2))
        label_bits = [b for b in [item.label, glyph] if b]
        if include_answers and item.is_correct:
            label_bits.append("✓")
        if label_bits:
            cell.add_paragraph(" ".join(label_bits))
