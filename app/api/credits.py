from fastapi import APIRouter, Depends

from app.api.deps import get_current_teacher
from app.core.credit_store import get_credit_store
from app.core.subject_store import get_subject_store
from app.schemas.credit import CreditList, CreditOut
from app.schemas.teacher import Teacher

router = APIRouter(prefix="/api/v1/credits", tags=["credits"], dependencies=[Depends(get_current_teacher)])


@router.get("", response_model=CreditList)
def my_credits(teacher: Teacher = Depends(get_current_teacher)) -> CreditList:
    """The caller's own credits: one per question of theirs used in an exported paper."""
    subjects = {s.id: s for s in get_subject_store().list_all()}
    items = []
    for c in get_credit_store().list_for_teacher(teacher.id):
        subject = subjects.get(c.subject_id)
        items.append(
            CreditOut(
                id=c.id,
                question_id=c.question_id,
                question_text=c.question_text,
                question_type=c.question_type,
                marks=c.marks,
                exam_name=c.exam_name,
                subject_name=subject.name if subject else "(deleted subject)",
                subject_grade=subject.grade if subject else None,
                earned_at=c.earned_at,
            )
        )
    return CreditList(total=len(items), items=items)
