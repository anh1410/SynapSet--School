import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_teacher
from app.core.template_store import get_template_store
from app.schemas.template import PaperTemplate, TemplateSection
from app.schemas.teacher import Teacher

router = APIRouter(prefix="/api/v1/templates", tags=["templates"], dependencies=[Depends(get_current_teacher)])


class CreateTemplateRequest(BaseModel):
    name: str
    duration_minutes: int | None = None
    sections: list[TemplateSection]


@router.post("", response_model=PaperTemplate)
def create_template(request: CreateTemplateRequest, teacher: Teacher = Depends(get_current_teacher)) -> PaperTemplate:
    template = PaperTemplate(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        name=request.name,
        duration_minutes=request.duration_minutes,
        sections=request.sections,
    )
    get_template_store().add(template)
    return template


@router.get("", response_model=list[PaperTemplate])
def list_templates(teacher: Teacher = Depends(get_current_teacher)) -> list[PaperTemplate]:
    return get_template_store().list_by_teacher(teacher.id)


@router.delete("/{template_id}")
def delete_template(template_id: str, teacher: Teacher = Depends(get_current_teacher)) -> dict:
    store = get_template_store()
    template = store.get(template_id)
    if template is None or template.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="Template not found")
    store.remove(template_id)
    return {"deleted": template_id}
