from datetime import datetime

from pydantic import BaseModel

from app.schemas.question import QuestionType


class Credit(BaseModel):
    id: str
    teacher_id: str
    question_id: str
    blueprint_id: str
    subject_id: str
    exam_name: str
    question_text: str
    question_type: QuestionType
    marks: int
    earned_at: datetime


class CreditOut(BaseModel):
    """What a teacher sees: their own question and the NAME of the exam it was used in.
    Nothing about the exam's other questions, and no way to open the paper."""

    id: str
    question_id: str
    question_text: str
    question_type: QuestionType
    marks: int
    exam_name: str
    subject_name: str
    subject_grade: str | None
    earned_at: datetime


class CreditList(BaseModel):
    total: int
    items: list[CreditOut]
