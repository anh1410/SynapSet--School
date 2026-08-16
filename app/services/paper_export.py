from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.paper_blueprint import BlueprintSection, PaperBlueprint
from app.schemas.question import Question, QuestionType

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
    # mcq / short_answer / long_answer / numerical / fill_in_blank
    return q.correct_answer or "(no answer recorded)"


def _blank_lines_for(marks: int) -> int:
    """Simple heuristic: more marks, more writing space. Not configurable yet."""
    return min(6, max(1, marks // 2 + 1))


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
            story.append(Paragraph(f"{q_num}. {q.text} [{q.marks} marks]", styles["Normal"]))
            if q.question_type == QuestionType.MCQ and q.options:
                for j, option in enumerate(q.options):
                    letter = chr(ord("a") + j)
                    story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;({letter}) {option}", styles["Normal"]))
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
                story.append(table)
                story.append(Spacer(1, 0.1 * inch))

            if include_answers:
                story.append(Paragraph(f"<b>Answer:</b> {_render_answer(q)}", styles["Normal"]))
            elif q.question_type in _FREE_RESPONSE_TYPES:
                story.append(Spacer(1, _blank_lines_for(q.marks) * 0.25 * inch))

            story.append(Spacer(1, 0.15 * inch))
        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    return output_path


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
            doc.add_paragraph(f"{q_num}. {q.text} [{q.marks} marks]")
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

            if include_answers:
                doc.add_paragraph(f"Answer: {_render_answer(q)}")
            elif q.question_type in _FREE_RESPONSE_TYPES:
                for _ in range(_blank_lines_for(q.marks)):
                    doc.add_paragraph("")

    doc.save(output_path)
    return output_path
