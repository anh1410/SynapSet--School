from fastapi import APIRouter, Depends

from app.api.deps import get_current_teacher, require_admin, require_subject
from app.core.draft_store import get_draft_store
from app.schemas.draft import BuilderDraft
from app.schemas.teacher import Teacher

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"], dependencies=[Depends(require_admin)])


@router.get("", response_model=BuilderDraft | None)
def get_draft(subject_id: str, teacher: Teacher = Depends(get_current_teacher)) -> BuilderDraft | None:
    require_subject(subject_id, teacher)
    return get_draft_store().get_for_subject(teacher.id, subject_id)


@router.put("", response_model=BuilderDraft)
def put_draft(draft: BuilderDraft, teacher: Teacher = Depends(get_current_teacher)) -> BuilderDraft:
    require_subject(draft.subject_id, teacher)
    draft.teacher_id = teacher.id
    get_draft_store().upsert(draft)
    return draft


@router.delete("")
def delete_draft(subject_id: str, teacher: Teacher = Depends(get_current_teacher)) -> dict:
    require_subject(subject_id, teacher)
    cleared = get_draft_store().clear(teacher.id, subject_id)
    return {"cleared": cleared}
