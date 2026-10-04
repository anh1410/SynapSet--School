import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.api.deps import require_admin
from app.core.credit_store import get_credit_store
from app.core.security import hash_password
from app.core.subject_store import get_subject_store
from app.core.submission_store import get_submission_store
from app.core.teacher_store import get_teacher_store
from app.schemas.teacher import Role, Teacher

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

MIN_PASSWORD_LENGTH = 8


def _nonempty(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("This field can't be empty")
    return value


def _valid_email(value: str) -> str:
    value = value.strip()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("Enter a valid email address")
    return value


def _valid_password(value: str | None) -> str | None:
    if value is not None and len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    return value


class TeacherAdminView(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    active: bool
    created_at: datetime
    subject_ids: list[str]
    credit_count: int = 0


def _view(teacher: Teacher, assignments: dict[str, list[str]], credits: dict[str, int] | None = None) -> TeacherAdminView:
    return TeacherAdminView(
        id=teacher.id,
        email=teacher.email,
        name=teacher.name,
        role=teacher.role,
        active=teacher.active,
        created_at=teacher.created_at,
        subject_ids=assignments.get(teacher.id, []),
        credit_count=(credits or {}).get(teacher.id, 0),
    )


def _require_subjects_exist(subject_ids: list[str]) -> None:
    known = {s.id for s in get_subject_store().list_all()}
    unknown = [sid for sid in subject_ids if sid not in known]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown subject(s): {', '.join(unknown)}")


def _get_target(teacher_id: str) -> Teacher:
    target = get_teacher_store().get(teacher_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return target


class CreateTeacherRequest(BaseModel):
    name: str
    email: str
    password: str
    subject_ids: list[str] = []

    _name = field_validator("name")(_nonempty)
    _email = field_validator("email")(_valid_email)
    _password = field_validator("password")(_valid_password)


class UpdateTeacherRequest(BaseModel):
    name: str | None = None
    role: Role | None = None
    active: bool | None = None
    password: str | None = None

    _name = field_validator("name")(_nonempty)
    _password = field_validator("password")(_valid_password)


class SetSubjectsRequest(BaseModel):
    subject_ids: list[str]


@router.get("/teachers", response_model=list[TeacherAdminView])
def list_teachers() -> list[TeacherAdminView]:
    assignments = get_subject_store().assignments_by_teacher()
    credits = get_credit_store().counts_by_teacher()
    return [_view(t, assignments, credits) for t in get_teacher_store().list()]


@router.post("/teachers", response_model=TeacherAdminView)
def create_teacher(request: CreateTeacherRequest) -> TeacherAdminView:
    """Admins create teacher accounts (there's no public signup after the first
    admin) and share the password with the teacher."""
    store = get_teacher_store()
    if store.get_by_email(request.email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    _require_subjects_exist(request.subject_ids)

    teacher = Teacher(
        id=str(uuid.uuid4()),
        email=request.email,
        name=request.name,
        password_hash=hash_password(request.password),
        role="teacher",
    )
    store.add(teacher)
    get_subject_store().set_teacher_subjects(teacher.id, request.subject_ids)
    return _view(teacher, get_subject_store().assignments_by_teacher())


@router.patch("/teachers/{teacher_id}", response_model=TeacherAdminView)
def update_teacher(
    teacher_id: str, request: UpdateTeacherRequest, admin: Teacher = Depends(require_admin)
) -> TeacherAdminView:
    target = _get_target(teacher_id)

    # An admin can't change their own role or active status. Because the caller
    # is always an active admin, this alone guarantees the school can never end
    # up with zero admins - no separate "last admin" bookkeeping needed.
    if target.id == admin.id and (request.role is not None or request.active is not None):
        raise HTTPException(status_code=400, detail="You can't change your own role or deactivate yourself")

    changes: dict = {}
    if request.name is not None:
        changes["name"] = request.name
    if request.role is not None:
        changes["role"] = request.role
    if request.active is not None:
        changes["active"] = request.active
    if request.password is not None:
        changes["password_hash"] = hash_password(request.password)

    updated = target.model_copy(update=changes)
    get_teacher_store().add(updated)
    return _view(updated, get_subject_store().assignments_by_teacher())


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: str, admin: Teacher = Depends(require_admin)) -> dict:
    target = _get_target(teacher_id)
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You can't delete your own account")
    if get_submission_store().count_for_teacher(target.id) > 0:
        # Their questions (and the credit for them) must stay attributable to someone.
        raise HTTPException(
            status_code=409,
            detail="This teacher has submitted questions, so the account can't be deleted. Deactivate it instead.",
        )
    get_teacher_store().remove(target.id)
    return {"deleted": target.id}


@router.put("/teachers/{teacher_id}/subjects", response_model=TeacherAdminView)
def set_teacher_subjects(teacher_id: str, request: SetSubjectsRequest) -> TeacherAdminView:
    """Replaces the full list of subjects this teacher is assigned to."""
    target = _get_target(teacher_id)
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Admins can already access every subject")
    _require_subjects_exist(request.subject_ids)
    get_subject_store().set_teacher_subjects(target.id, request.subject_ids)
    return _view(target, get_subject_store().assignments_by_teacher())
