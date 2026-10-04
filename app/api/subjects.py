import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.api.deps import get_current_teacher, require_admin, require_subject
from app.core.graph_store import get_graph_store
from app.core.subject_store import get_subject_store
from app.schemas.subject import GRADES, Subject
from app.schemas.teacher import Teacher

router = APIRouter(prefix="/api/v1/subjects", tags=["subjects"], dependencies=[Depends(get_current_teacher)])


def _clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Subject name can't be empty")
    return value


def _check_grade(value: str | None) -> str | None:
    if value is not None and value not in GRADES:
        raise ValueError(f"Grade must be one of: {', '.join(GRADES)}")
    return value


class CreateSubjectRequest(BaseModel):
    name: str
    grade: str

    _name = field_validator("name")(_clean_name)
    _grade = field_validator("grade")(_check_grade)


class UpdateSubjectRequest(BaseModel):
    name: str | None = None
    grade: str | None = None

    _name = field_validator("name")(_clean_name)
    _grade = field_validator("grade")(_check_grade)


def _ensure_unique(name: str, grade: str | None, ignore_id: str | None = None) -> None:
    for existing in get_subject_store().list_all():
        if existing.id != ignore_id and existing.grade == grade and existing.name.lower() == name.lower():
            raise HTTPException(status_code=409, detail="That subject already exists for this grade")


@router.post("", response_model=Subject)
def create_subject(request: CreateSubjectRequest, admin: Teacher = Depends(require_admin)) -> Subject:
    _ensure_unique(request.name, request.grade)
    subject = Subject(id=str(uuid.uuid4()), teacher_id=admin.id, name=request.name, grade=request.grade)
    get_subject_store().add(subject)
    return subject


@router.get("", response_model=list[Subject])
def list_subjects(teacher: Teacher = Depends(get_current_teacher)) -> list[Subject]:
    """Admins see every subject in the school; a teacher sees only the ones an admin assigned to them."""
    store = get_subject_store()
    return store.list_all() if teacher.role == "admin" else store.list_for_teacher(teacher.id)


@router.get("/{subject_id}/topics")
def list_subject_topics(subject_id: str, teacher: Teacher = Depends(get_current_teacher)) -> list[dict]:
    """Topic names for the question form's topic picker. Names only: this is the one
    window into a subject's knowledge graph a teacher gets (the graph API itself is admin-only)."""
    require_subject(subject_id, teacher)
    graph = get_graph_store(subject_id).graph
    topics = [{"id": node_id, "name": data.get("name", node_id)} for node_id, data in graph.nodes(data=True)]
    return sorted(topics, key=lambda t: t["name"].casefold())


@router.patch("/{subject_id}", response_model=Subject)
def update_subject(
    subject_id: str, request: UpdateSubjectRequest, admin: Teacher = Depends(require_admin)
) -> Subject:
    store = get_subject_store()
    subject = store.get(subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")

    updated = subject.model_copy(
        update={
            "name": request.name if request.name is not None else subject.name,
            "grade": request.grade if request.grade is not None else subject.grade,
        }
    )
    _ensure_unique(updated.name, updated.grade, ignore_id=subject_id)
    store.add(updated)
    return updated


@router.delete("/{subject_id}")
def delete_subject(subject_id: str, admin: Teacher = Depends(require_admin)) -> dict:
    store = get_subject_store()
    if store.get(subject_id) is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    store.remove(subject_id)
    return {"deleted": subject_id}
